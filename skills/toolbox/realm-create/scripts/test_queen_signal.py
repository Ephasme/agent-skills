"""Tests for `realm signal-queen`: python3 -m unittest test_queen_signal (from this directory). No network, no sleeps."""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from realmlib import daemon, db, herdr, mail, queen_signal, state
from realmlib.db import Refused

KEY = "/test/realm"
OTHER = "/test/other"
T0 = 1_800_000_000.0


class SignalTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.conn = db.connect(tmp / "realm.db")
        self.addCleanup(self.conn.close)
        db.init_realm(self.conn, KEY, "Queen", "q1", T0)
        db.add_worker(self.conn, KEY, "Ann", "p1", "t1", "/b/ann.md", T0)
        db.init_realm(self.conn, OTHER, "Other", "q2", T0)
        db.add_worker(self.conn, OTHER, "Zed", "p9", "t9", "/b/zed.md", T0)
        self.tabs = {"q1": "👑 queen", "q2": "👑 queen", "p1": "🛠️ subject-ann"}
        self.calls = []
        self.unread = set()
        self.now = T0
        for module, target, value in (
            (state, "STATE_DIR", tmp),
            (state, "STATE_FILE", tmp / "state.json"),
            (state, "LOCK_FILE", tmp / "state.lock"),
            (state, "LOG_FILE", tmp / "realm.log"),
            (herdr, "herdr", self.herdr),
            (queen_signal, "herdr", self.herdr),
            (daemon, "herdr", self.herdr),
            (daemon, "clock", lambda: self.now),
            (mail, "mail_endpoint", lambda: ("http://mail", {})),
            (mail, "fetch_events", lambda *_a: ([], 0)),
            (mail, "unread_ids", lambda *_a: set(self.unread)),
        ):
            patcher = mock.patch.object(module, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        with state.locked_state() as s:
            s["subscriptions"]["q1"] = {"agent": "Queen", "project": KEY, "mode": "aside", "cursor": 0,
                                        "pending": [], "last_wake": 0, "last_unread": 0}

    def herdr(self, *args):
        self.calls.append(args)
        if args[:2] == ("pane", "get"):
            if args[2] not in self.tabs:
                return {"error": {"code": "pane_not_found"}}
            return {"result": {"pane": {"pane_id": args[2], "tab_id": args[2], "agent_status": "idle"}}}
        if args[:2] == ("tab", "get"):
            return {"result": {"tab": {"label": self.tabs[args[2]]}}}
        return {}

    def signal(self, sender="Ann", slug="s1", text=None, key=KEY):
        return queen_signal.signal_queen(self.conn, key, sender, slug, text, self.now)

    def token(self):
        """The last value the signal token was set to on q1; None once cleared."""
        last = [c for c in self.calls if c[:3] == ("pane", "report-metadata", "q1")][-1]
        return None if "--clear-token" in last else last[-1]

    def typed(self):
        return [c for c in self.calls if c[:2] in (("pane", "send-text"), ("pane", "send-keys"), ("pane", "run"))]

    def test_signal_shows_token_and_never_types(self):
        out = self.signal(text="done, see reply")
        self.assertEqual(self.token(), "signal=🔔 Ann:s1 done, see reply")
        self.assertEqual(self.typed(), [])
        self.assertEqual((out["pane"], out["queen"], out["repeat"]), ("q1", "Queen", False))

    def test_repeat_replaces_instead_of_stacking(self):
        self.signal()
        out = self.signal()
        self.assertTrue(out["repeat"])
        self.signal(slug="s2")
        self.assertEqual(self.token(), "signal=🔔 Ann:s2")

    def test_two_workers_both_show(self):
        db.add_worker(self.conn, KEY, "Bob", "p2", "t2", "/b/bob.md", T0)
        self.signal()
        self.signal(sender="Bob", slug="s3")
        self.assertEqual(self.token(), "signal=🔔 Ann:s1, Bob:s3")

    def test_text_is_one_short_line(self):
        out = self.signal(text="a\nb  " + "x" * 200)
        self.assertNotIn("\n", out["text"])
        self.assertEqual(len(out["text"]), queen_signal.TEXT_MAX)

    def test_worker_of_another_realm_is_refused(self):
        with self.assertRaises(Refused):
            self.signal(sender="Zed")
        self.assertEqual(self.calls, [])

    def test_unknown_realm_is_refused(self):
        with self.assertRaises(Refused):
            self.signal(key="/nope")

    def test_queen_pane_without_queen_label_is_refused(self):
        self.tabs["q1"] = "🛠️ subject-impostor"
        with self.assertRaises(Refused):
            self.signal()
        self.assertFalse([c for c in self.calls if c[1] == "report-metadata"])

    def test_queen_pane_gone_is_refused(self):
        del self.tabs["q1"]
        with self.assertRaises(Refused):
            self.signal()

    def test_queen_pane_subscribed_for_another_key_is_refused(self):
        with state.locked_state() as s:
            s["subscriptions"]["q1"]["project"] = OTHER
        with self.assertRaises(Refused):
            self.signal()

    def test_tick_clears_signals_once_queen_read_her_mail(self):
        self.signal()
        self.unread = {7}
        self.now += 15
        daemon.cmd_tick(None)
        self.assertEqual(self.token(), "signal=🔔 Ann:s1")
        self.unread = set()
        self.now += 15
        daemon.cmd_tick(None)
        self.assertIsNone(self.token())
        self.assertEqual(self.typed(), [])

    def test_signal_rung_during_tick_survives_the_clear(self):
        self.now += 15
        with mock.patch.object(daemon, "clock", side_effect=[self.now]):
            self.now += 1
            self.signal()  # rung after the tick started: its mail may not be counted yet
            self.now -= 1
            with state.locked_state() as s:
                queen_signal.clear(s, KEY, "q1", before=self.now)
        self.assertEqual(self.token(), "signal=🔔 Ann:s1")

    def test_signals_are_per_realm(self):
        db.add_worker(self.conn, OTHER, "Yan", "p8", "t8", "/b/yan.md", T0)
        self.signal()
        self.signal(sender="Yan", slug="o1", key=OTHER)
        with state.locked_state() as s:
            self.assertEqual(sorted(s["signals"]), sorted([KEY, OTHER]))
            queen_signal.clear(s, KEY, "q1", before=self.now + 1)
            self.assertEqual(sorted(s["signals"]), [OTHER])


if __name__ == "__main__":
    unittest.main()
