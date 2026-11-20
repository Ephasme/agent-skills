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
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": ["a", "b"]}, T0)
        c = scout.cursors(self.conn, KEY, "slack", T0)
        self.assertEqual((c["first"], c["cursors"]), (False, {"all": "100"}))
        self.assertEqual(scout.unseen(self.conn, KEY, "slack", ["a", "c", "b"]), ["c"])

    def test_cursor_never_moves_back(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": []}, T0)
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "90"}, "ids": []}, T0)
        self.assertEqual(scout.cursors(self.conn, KEY, "slack", T0)["cursors"], {"all": "100"})

    def test_realms_isolated(self):
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "100"}, "ids": ["a"]}, T0)
        self.assertTrue(scout.cursors(self.conn, OTHER, "slack", T0)["first"])
        self.assertEqual(scout.unseen(self.conn, OTHER, "slack", ["a"]), ["a"])

    def test_unknown_source(self):
        with self.assertRaises(Refused):
            scout.ack(self.conn, KEY, {"source": "fax", "ids": []}, T0)


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
            scout.ack(self.conn, KEY, b, 2000)
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
        scout.ack(self.conn, KEY, {"source": "slack", "cursors": {"all": "1000"}, "ids": []}, T0)
        pages = {1: [{"ts": "999.0", "channel": {"id": "C1"}}, {"ts": "1001.0", "channel": {"id": "C1"}, "text": "hi"},
                     {"ts": "1002.0", "channel": {"id": "C1"}, "bot_id": "B1"}],
                 2: [{"ts": "1003.0", "channel": {"id": "C2"}, "text": "yo"}]}

        class Api:
            def get(self, method, **p):
                return {"messages": {"matches": pages[p["page"]], "paging": {"pages": 2}}}

        b = scout.fetch_slack(self.conn, KEY, T0, api=Api())
        self.assertEqual((b["ids"], b["cursors"], b["more"]), (["C1:1001.0", "C2:1003.0"], {"all": "1003.0"}, False))

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

    def test_render(self):
        scout.propose(self.conn, KEY, [self.prop()], T0)
        md = scout.render(scout.list_proposals(self.conn, KEY))
        self.assertIn("**P1** `task.add` Send deck", md)
        self.assertIn("> send the deck by Friday ([link](https://x/1))", md)


class Brief(unittest.TestCase):
    def test_fill_keeps_json_braces(self):
        text = scout.fill(scout.BRIEF_TEMPLATE.read_text(), S="Scout", KEY="/k", QUEEN="Q", LABEL="L")
        self.assertNotIn("{S}", text)
        self.assertIn('{"source"', text)


if __name__ == "__main__":
    unittest.main()
