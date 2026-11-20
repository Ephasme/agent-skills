"""Tests for realmlib.scout: `python3 -m unittest test_scout` from this directory. No network, no sleeps."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from realmlib import db, scout
from realmlib.db import Refused

KEY = "/test/realm"
OTHER = "/test/other"


def paris(y, mo, d, h, mi=0):
    return datetime(y, mo, d, h, mi, tzinfo=scout.TZ).timestamp()


T0 = paris(2026, 11, 20, 12)


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.conn = db.connect(Path(self.dir.name) / "realm.db")
        for k in (KEY, OTHER):
            db.init_realm(self.conn, k, "Queen", None, T0)
            self.conn.execute("INSERT INTO scouts (realm, agent, created_ts) VALUES (?, 'Scout', ?)", (k, T0))

    def tearDown(self):
        self.conn.close()
        self.dir.cleanup()

    def prop(self, ref="m1", action="task.add", **kw):
        return {"source": "slack", "ref": ref, "permalink": "https://x/1", "excerpt": "send the deck by Friday",
                "action": action, "payload": kw.pop("payload", {"title": "Send deck", "due": "2026-11-27"}),
                "confidence": "high", "why": "asked directly", **kw}


class Schedule(Base):
    def test_never_scanned_is_due(self):
        self.assertTrue(scout.scan_due(self.conn, KEY, T0))
        self.assertTrue(scout.scan_due(self.conn, "/no/scout", T0))

    def test_day_hourly(self):
        scout.scan_start(self.conn, KEY, T0)
        scout.scan_end(self.conn, KEY, T0, push=lambda *a: "off")
        self.assertFalse(scout.scan_due(self.conn, KEY, T0 + 3599))
        self.assertTrue(scout.scan_due(self.conn, KEY, T0 + 3600))

    def test_night_every_three_hours(self):
        t = paris(2026, 11, 20, 23)
        scout.scan_end(self.conn, KEY, t, push=lambda *a: "off")
        self.assertFalse(scout.scan_due(self.conn, KEY, t + 2 * 3600))
        self.assertTrue(scout.scan_due(self.conn, KEY, t + 3 * 3600))

    def test_boundaries_local_time(self):
        self.assertEqual(scout.interval(paris(2026, 11, 20, 7, 59)), scout.NIGHT_INTERVAL)
        self.assertEqual(scout.interval(paris(2026, 11, 20, 8)), scout.DAY_INTERVAL)
        self.assertEqual(scout.interval(paris(2026, 11, 20, 21, 59)), scout.DAY_INTERVAL)
        self.assertEqual(scout.interval(paris(2026, 11, 20, 22)), scout.NIGHT_INTERVAL)
        # summer time: 08:00 Paris is 06:00 UTC
        self.assertEqual(scout.interval(paris(2026, 7, 1, 8)), scout.DAY_INTERVAL)


class Tracker(Base):
    def test_first_then_ack(self):
        c = scout.cursors(self.conn, KEY, "slack", T0)
        self.assertTrue(c["first"])
        self.assertEqual(c["default"], T0 - scout.BACKFILL_SECONDS)
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": ["a", "b"], "proposed": []}, T0)
        c = scout.cursors(self.conn, KEY, "slack", T0)
        self.assertEqual((c["first"], c["cursors"]), (False, {"all": "100"}))
        self.assertEqual(scout.unseen(self.conn, KEY, "slack", ["a", "c", "b"]), ["c"])

    def test_cursor_never_moves_back(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": [], "proposed": []}, T0)
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "90"}, "ids": [], "proposed": []}, T0)
        self.assertEqual(scout.cursors(self.conn, KEY, "slack", T0)["cursors"], {"all": "100"})

    def test_realms_isolated(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": ["a"], "proposed": []}, T0)
        self.assertTrue(scout.cursors(self.conn, OTHER, "slack", T0)["first"])
        self.assertEqual(scout.unseen(self.conn, OTHER, "slack", ["a"]), ["a"])

    def test_unknown_source(self):
        with self.assertRaises(Refused):
            scout.ack(self.conn, KEY, {"source": "fax", "ids": [], "proposed": []}, T0)

    def test_ack_refuses_until_proposals_recorded(self):
        batch = {"source": "slack", "cursors": {"all": "100"}, "ids": ["m1", "m2"], "proposed": ["m1"]}
        with self.assertRaises(Refused):
            scout.ack(self.conn, KEY, batch, T0)
        with self.assertRaises(Refused):
            scout.ack(self.conn, KEY, {**batch, "proposed": None}, T0)
        self.assertTrue(scout.cursors(self.conn, KEY, "slack", T0)["first"])  # nothing moved
        pid = scout.propose(self.conn, OTHER, [self.prop(ref="m1")], T0)[0]["id"]
        with self.assertRaises(Refused):
            scout.ack(self.conn, KEY, batch, T0)  # another realm's proposal doesn't count
        pid = scout.propose(self.conn, KEY, [self.prop(ref="m1")], T0)[0]["id"]
        scout.ack(self.conn, KEY, batch, T0)
        self.assertEqual(scout.unseen(self.conn, KEY, "slack", ["m1", "m2", "m3"]), ["m3"])
        self.assertEqual(self.conn.execute("SELECT proposal_id FROM scout_seen WHERE realm=? AND msg_id='m1'",
                                           (KEY,)).fetchone()[0], pid)


class Fetch(Base):
    CFG = {"whatsapp": {"chats": {"c1@s": "Ann", "c2@s": "Bea"}}}

    def client(self, items):
        class C:
            calls = []

            def call(self, tool, args):
                C.calls.append((tool, args))
                rows = [m for m in items[args["chat"]] if m["ts"] >= args["after"]]
                return [{"items": rows, "next_cursor": None}]

        return C()

    def test_limit_pages_oldest_first_and_cursor_follows(self):
        items = {"c1@s": [{"id": f"a{i}", "ts": 1000 + 2 * i, "from_me": False, "text": "x"} for i in range(3)],
                 "c2@s": [{"id": f"b{i}", "ts": 1001 + 2 * i, "from_me": True, "text": "y"} for i in range(3)]}
        with mock.patch.object(scout, "config", return_value=self.CFG):
            b = scout.fetch_whatsapp(self.conn, KEY, 2000, limit=4, client=self.client(items))
            self.assertTrue(b["more"])
            self.assertEqual(b["ids"], ["a0", "b0", "a1", "b1"])
            self.assertEqual(b["cursors"], {"c1@s": "1002.0", "c2@s": "1003.0"})
            scout.ack(self.conn, KEY, {**b, "proposed": []}, 2000)
            b = scout.fetch_whatsapp(self.conn, KEY, 2000, limit=4, client=self.client(items))
            self.assertFalse(b["more"])
            self.assertEqual(b["ids"], ["a2", "b2"])

    def test_backfill_starts_a_month_back(self):
        client = self.client({"c1@s": [], "c2@s": []})
        with mock.patch.object(scout, "config", return_value=self.CFG):
            scout.fetch_whatsapp(self.conn, KEY, T0, client=client)
        self.assertEqual({a["after"] for _, a in client.calls}, {int(T0 - scout.BACKFILL_SECONDS)})

    def test_unreadable_source_is_skipped_not_failed(self):
        with mock.patch.object(scout, "config", return_value={}):
            out = scout.fetch(self.conn, KEY, "whatsapp", T0, 10)
        self.assertEqual(out["source"], "whatsapp")
        self.assertIn("allowlisted", out["skipped"])
        with mock.patch.object(scout, "secret", side_effect=scout.Skipped("secret X not available")):
            self.assertIn("not available", scout.fetch(self.conn, KEY, "slack", T0, 10)["skipped"])

    def test_slack_drops_bots_and_pre_cursor_and_pages(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "1000"}, "ids": [], "proposed": []}, T0)
        pages = {1: [{"ts": "999.0", "channel": {"id": "C1"}}, {"ts": "1001.0", "channel": {"id": "C1"}, "text": "hi"},
                     {"ts": "1002.0", "channel": {"id": "C1"}, "bot_id": "B1"}],
                 2: [{"ts": "1003.0", "channel": {"id": "C2"}, "text": "yo", "user": "U_ME"}]}

        class Api:
            def get(self, method, **p):
                return {"messages": {"matches": pages[p["page"]], "paging": {"pages": 2}}}

            def me(self):
                return "U_ME"

        b = scout.fetch_slack(self.conn, KEY, T0, api=Api())
        self.assertEqual((b["ids"], b["cursors"], b["more"]), (["C1:1001.0", "C2:1003.0"], {"all": "1003.0"}, False))
        self.assertEqual([m["from_me"] for m in b["messages"]], [False, True])

    def test_slack_waits_out_rate_limit(self):
        import io
        import urllib.error

        limited = urllib.error.HTTPError("u", 429, "Too Many Requests", {"Retry-After": "7"}, io.BytesIO())
        with mock.patch.object(scout, "_http_json", side_effect=[limited, {"ok": True, "x": 1}]), \
                mock.patch.object(scout.time, "sleep") as sleep:
            self.assertEqual(scout.SlackApi(token="t").get("search.messages")["x"], 1)
        sleep.assert_called_once_with(7)
        with mock.patch.object(scout, "_http_json", side_effect=limited), mock.patch.object(scout.time, "sleep"):
            with self.assertRaises(urllib.error.HTTPError):
                scout.SlackApi(token="t").get("search.messages")

    def test_gmail_oldest_first_limit_and_cursor(self):
        import base64

        msgs = {f"m{i}": {"internalDate": str((1000 + i) * 1000), "labelIds": [],
                          "payload": {"mimeType": "text/plain", "headers": [{"name": "Subject", "value": f"s{i}"}],
                                      "body": {"data": base64.urlsafe_b64encode(f"body {i}".encode()).decode()}}}
                for i in range(3)}

        class Api:
            def get(self, path, **p):
                if path == "messages":
                    return {"messages": [{"id": f"m{i}"} for i in (2, 1, 0)]}  # Gmail lists newest first
                return msgs[path.split("/")[1]]

        b = scout.fetch_gmail(self.conn, KEY, T0, "perso", limit=2, api=Api())
        self.assertEqual((b["ids"], b["more"], b["cursors"]), (["m0", "m1"], True, {"all": "1001.0"}))
        self.assertEqual(b["messages"][0]["text"], "body 0")
        self.assertEqual(b["source"], "gmail-perso")


class Proposals(Base):
    def test_propose_dedup_and_excerpt_cap(self):
        out = scout.propose(self.conn, KEY, [self.prop(excerpt="x" * 500)], T0)
        self.assertFalse(out[0]["duplicate"])
        again = scout.propose(self.conn, KEY, [self.prop()], T0)
        self.assertEqual(again, [{"id": out[0]["id"], "duplicate": True}])
        self.assertEqual(len(scout.list_proposals(self.conn, KEY)[0]["excerpt"]), scout.EXCERPT_MAX)

    def test_propose_validates(self):
        for bad in (self.prop(action="calendar.accept"), self.prop(confidence="sure"),
                    self.prop(payload={}), self.prop(ref="")):
            with self.assertRaises(Refused):
                scout.propose(self.conn, KEY, [bad], T0)

    def test_scan_end_refuses_unmailed_then_pushes_titles(self):
        scout.scan_start(self.conn, KEY, T0)
        pid = scout.propose(self.conn, KEY, [self.prop()], T0 + 1)[0]["id"]
        with self.assertRaises(Refused):
            scout.scan_end(self.conn, KEY, T0 + 2, push=lambda *a: "off")
        scout.mailed(self.conn, KEY, [pid], 77)
        pushes = []
        out = scout.scan_end(self.conn, KEY, T0 + 2, push=lambda t, m: pushes.append((t, m)) or "sent")
        self.assertEqual(out["pushed"], "sent")
        self.assertEqual(pushes, [("scout: 1 proposal(s)", "P1 task.add Send deck")])
        self.assertEqual(scout.list_proposals(self.conn, KEY)[0]["mail_id"], 77)
        self.assertFalse(scout.scan_due(self.conn, KEY, T0 + 3))

    def test_mailed_other_realm_refused(self):
        pid = scout.propose(self.conn, KEY, [self.prop()], T0)[0]["id"]
        with self.assertRaises(Refused):
            scout.mailed(self.conn, OTHER, [pid], 1)

    def test_decide_apply_task(self):
        a, b, c = (scout.propose(self.conn, KEY, [self.prop(ref=r)], T0)[0]["id"] for r in "abc")
        scout.decide(self.conn, KEY, [a, b], [c], T0)
        with self.assertRaises(Refused):
            scout.decide(self.conn, KEY, [c], [], T0)  # already decided
        out = scout.apply_tasks(self.conn, KEY, [a], T0)
        tasks = scout.list_tasks(self.conn, KEY, ["open"])
        self.assertEqual([(t["title"], t["due"], t["proposal"]) for t in tasks], [("Send deck", "2026-11-27", a)])
        self.assertEqual(scout.list_proposals(self.conn, KEY, ids=[a])[0]["applied_ref"], f"task:{out[0]['task']}")
        with self.assertRaises(Refused):
            scout.apply_tasks(self.conn, KEY, [c], T0)  # rejected

    def test_calendar_goes_through_applied_only(self):
        cal = self.prop(action="calendar.create", payload={"calendar": "perso", "title": "Dinner",
                                                            "start": "2026-11-21T20:00", "tz": "Europe/Paris"})
        pid = scout.propose(self.conn, KEY, [cal], T0)[0]["id"]
        with self.assertRaises(Refused):
            scout.applied(self.conn, KEY, pid, "ev1", False, T0)  # not approved yet
        scout.decide(self.conn, KEY, [pid], [], T0)
        with self.assertRaises(Refused):
            scout.apply_tasks(self.conn, KEY, [pid], T0)
        self.assertEqual(scout.applied(self.conn, KEY, pid, "ev1", False, T0)["state"], "applied")

    def test_decide_other_realm_refused(self):
        pid = scout.propose(self.conn, KEY, [self.prop()], T0)[0]["id"]
        with self.assertRaises(Refused):
            scout.decide(self.conn, OTHER, [pid], [], T0)

    def test_decide_remembers_approved_only_and_never_fails_on_memory(self):
        from realmlib import hindsight
        a, b = (scout.propose(self.conn, KEY, [self.prop(ref=r)], T0)[0]["id"] for r in "ab")
        calls = []
        with mock.patch.object(hindsight, "hooks_enabled", return_value=True), \
                mock.patch.object(hindsight, "retain", side_effect=lambda k, items: calls.append((k, items))):
            scout.decide(self.conn, KEY, [a], [b], T0)
        self.assertEqual(len(calls), 1)
        (key, items), = calls
        self.assertEqual((key, [i["document_id"] for i in items]), (KEY, [f"proposal/P{a}"]))
        self.assertEqual(items[0]["tags"], ["source:slack", "kind:channel-fact"])
        self.assertIn("Send deck", items[0]["content"])
        self.assertIn("2026-11-27", items[0]["content"])
        self.assertNotIn("send the deck by Friday", items[0]["content"])  # never the excerpt
        c = scout.propose(self.conn, KEY, [self.prop(ref="c")], T0)[0]["id"]
        with mock.patch.object(hindsight, "hooks_enabled", return_value=True), \
                mock.patch.object(hindsight, "retain", side_effect=OSError("down")):
            scout.decide(self.conn, KEY, [c], [], T0)
        self.assertEqual(scout.list_proposals(self.conn, KEY, ids=[c])[0]["state"], "approved")

    def test_reject_reason_kept_and_exported(self):
        a, b, c = (scout.propose(self.conn, KEY, [self.prop(ref=r)], T0)[0]["id"] for r in "abc")
        scout.decide(self.conn, KEY, [], [a, b], T0)
        # A rejection recorded before reasons existed gets its reason later; its decision time stays.
        scout.decide(self.conn, KEY, [], [a], T0 + 60, reason="mistake", note="misread the message")
        scout.decide(self.conn, KEY, [], [c], T0, reason="obsolete")
        mistakes = scout.list_proposals(self.conn, KEY, ["rejected"], reasons=["mistake"])
        self.assertEqual([(p["id"], p["note"], p["decided"]) for p in mistakes],
                         [(a, "misread the message", db.iso(T0))])
        self.assertEqual((mistakes[0]["excerpt"], mistakes[0]["why"], mistakes[0]["payload"]["title"]),
                         ("send the deck by Friday", "asked directly", "Send deck"))
        self.assertIsNone(scout.list_proposals(self.conn, KEY, ids=[b])[0]["reason"])
        for bad in (dict(approve=[], reject=[b], reason="wrong"), dict(approve=[b], reject=[], reason="done")):
            with self.assertRaises(Refused):
                scout.decide(self.conn, KEY, now=T0, **bad)
        p = scout.propose(self.conn, KEY, [self.prop(ref="d")], T0)[0]["id"]
        scout.decide(self.conn, KEY, [p], [], T0)
        with self.assertRaises(Refused):
            scout.decide(self.conn, KEY, [], [p], T0, reason="done")  # approved: no longer a rejection to explain

    def test_render(self):
        scout.propose(self.conn, KEY, [self.prop()], T0)
        md = scout.render(scout.list_proposals(self.conn, KEY))
        self.assertIn("**P1** `task.add` Send deck", md)
        self.assertIn("> send the deck by Friday ([link](https://x/1))", md)


class Tasks(Base):
    def test_priority_add_set_and_urgent_first(self):
        a = scout.add_task(self.conn, KEY, "later", None, "2026-11-21", T0)
        b = scout.add_task(self.conn, KEY, "now", None, None, T0, priority="urgent")
        self.assertEqual((a["priority"], b["priority"]), ("normal", "urgent"))
        self.assertEqual([t["id"] for t in scout.list_tasks(self.conn, KEY, ["open"])], [b["id"], a["id"]])
        self.assertEqual(scout.set_priority(self.conn, KEY, a["id"], "urgent")["priority"], "urgent")
        with self.assertRaises(Refused):
            scout.set_priority(self.conn, KEY, a["id"], "high")
        with self.assertRaises(Refused):
            scout.set_priority(self.conn, OTHER, a["id"], "normal")


class Adopt(Base):
    def test_history_moves_whole_and_scan_resumes(self):
        scout.propose(self.conn, OTHER, [self.prop("m1"), self.prop("m2")], T0)
        scout.ack(self.conn, OTHER, {"source": "slack", "cursors": {"all": "100"}, "ids": ["m1", "m2", "m3"],
                                     "proposed": ["m1", "m2"]}, T0)
        p1, p2 = sorted(p["id"] for p in scout.list_proposals(self.conn, OTHER))
        scout.mailed(self.conn, OTHER, [p1, p2], 7)
        scout.decide(self.conn, OTHER, [p1], [], T0)
        scout.apply_tasks(self.conn, OTHER, [p1], T0)
        scout.add_task(self.conn, OTHER, "by hand", None, None, T0)  # not the scout's: stays
        scout.scan_end(self.conn, OTHER, T0, push=lambda *a: "off")
        # KEY's fresh scout proposed m2 again (deleted) and m9 (kept)
        scout.propose(self.conn, KEY, [self.prop("m2"), self.prop("m9")], T0)
        out = scout.adopt(self.conn, OTHER, KEY)
        self.assertEqual(out["moved"], {"tasks": 1, "scout_cursors": 1, "scout_seen": 3, "proposals": 2})
        self.assertEqual(len(out["deleted_duplicates"]), 1)
        self.assertEqual(sorted(p["ref"] for p in scout.list_proposals(self.conn, KEY)), ["m1", "m2", "m9"])
        self.assertEqual(scout.cursors(self.conn, KEY, "slack", T0)["cursors"], {"all": "100"})
        self.assertEqual(scout.unseen(self.conn, KEY, "slack", ["m1", "m3", "m4"]), ["m4"])
        self.assertEqual([t["title"] for t in scout.list_tasks(self.conn, KEY, ["open"])], ["Send deck"])
        self.assertEqual([t["title"] for t in scout.list_tasks(self.conn, OTHER, ["open"])], ["by hand"])
        self.assertFalse(scout.scan_due(self.conn, KEY, T0 + 60))
        self.assertTrue(scout.cursors(self.conn, OTHER, "slack", T0)["first"])

    def test_refuses_onto_a_scout_with_its_own_history(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "5"}, "ids": ["x"], "proposed": []}, T0)
        with self.assertRaises(Refused):
            scout.adopt(self.conn, OTHER, KEY)
        with self.assertRaises(Refused):
            scout.adopt(self.conn, KEY, KEY)


class Brief(unittest.TestCase):
    def test_fill_keeps_json_braces(self):
        text = scout.fill(scout.BRIEF_TEMPLATE.read_text(), S="Scout", KEY="/k", QUEEN="Q", LABEL="L")
        self.assertNotIn("{S}", text)
        self.assertIn('{"source"', text)


if __name__ == "__main__":
    unittest.main()
