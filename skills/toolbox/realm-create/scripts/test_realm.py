"""Wake logic of realmlib against a fake Agent Mail server and fake herdr panes: no network, no sleeps.

Run: python3 -m unittest test_realm (from this directory).
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from realmlib import backup, bind, cli, daemon, herdr, mail, state, swarm
from realmlib.mail import MailToolError


class FakeMail:
    """Delivery events and read state for one agent, as fetch_inbox_events and the inbox snapshot see them."""

    def __init__(self):
        self.events = []  # (cursor, message_id)
        self.read = set()

    def deliver(self, message_id):
        self.events.append((len(self.events) + 1, message_id))

    def fetch_events(self, _endpoint, _agent, _project, cursor):
        tail = len(self.events)
        if cursor is None:
            return [], tail
        if cursor > tail:
            raise MailToolError("CURSOR_AHEAD", f"after={cursor} tail_cursor={tail}")
        return [m for c, m in self.events if c > cursor], tail

    def unread_ids(self, _endpoint, _agent, _project):
        return {m for _, m in self.events} - self.read


class Harness(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.mail = FakeMail()
        self.status = {"wC:p2": "idle", "wC:p1": "idle"}
        self.tabs = {"wC:p2": "🛠️ subject-w", "wC:p1": "👑 queen"}
        # Each pane sits alone in a tab and a workspace named after it.
        self.workspaces = {"wC:p2": "🛠️ realm · w", "wC:p1": "home"}
        self.typed = []
        self.texts = []
        self.due = False
        self.now = 1_800_000_000.0
        self.scan_checks = []
        self.tokens = []
        for module, target, value in (
            (state, "STATE_DIR", tmp),
            (state, "STATE_FILE", tmp / "state.json"),
            (state, "LOCK_FILE", tmp / "state.lock"),
            (state, "LOG_FILE", tmp / "realm.log"),
            (mail, "mail_endpoint", lambda: ("http://mail", {})),
            (mail, "fetch_events", self.mail.fetch_events),
            (mail, "unread_ids", self.mail.unread_ids),
            (herdr, "herdr", self.herdr),
            (daemon, "clock", lambda: self.now),
            (daemon, "scan_due", self.scan_due),
            (daemon, "herdr", self.herdr),
            (backup, "due_backup", lambda now: None),
            (swarm, "call", lambda tool, args: {"tail_cursor": 700}),
        ):
            patcher = mock.patch.object(module, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def herdr(self, *args):
        if args[:2] == ("pane", "get"):
            pane = args[2]
            if pane not in self.status:
                return {"error": {"code": "pane_not_found"}}
            return {"result": {"pane": {"pane_id": pane, "tab_id": pane, "workspace_id": pane,
                                        "agent_status": self.status[pane]}}}
        if args[:2] == ("tab", "get"):
            return {"result": {"tab": {"label": self.tabs[args[2]]}}}
        if args[:2] == ("workspace", "get"):
            return {"result": {"workspace": {"label": self.workspaces[args[2]]}}}
        if args[:2] == ("pane", "send-text"):
            self.typed.append(args[2])
            self.texts.append((args[2], args[3]))
        if args[:2] == ("pane", "report-metadata"):
            self.tokens.append((args[2], args[-1]))
        return {}

    def subscribe(self, pane, aside=False, scout=False, wake_text=daemon.WAKE_TEXT):
        cli.cmd_subscribe(
            mock.Mock(pane_id=pane, agent="W", project="/p", aside=aside, scout=scout, wake_text=wake_text)
        )

    def scan_due(self, key, now):
        self.scan_checks.append((key, now))
        if self.due == "raise":
            raise RuntimeError("scout broken")
        return self.due

    def tick(self):
        daemon.cmd_tick(None)


class WakeTest(Harness):
    def test_new_mail_to_idle_pane_wakes_once(self):
        self.subscribe("wC:p2")
        self.tick()
        self.mail.deliver(101)
        self.tick()
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])

    def test_busy_pane_is_woken_when_it_goes_idle(self):
        self.subscribe("wC:p2")
        self.tick()
        self.status["wC:p2"] = "working"
        self.mail.deliver(101)
        self.tick()
        self.status["wC:p2"] = "blocked"
        self.tick()
        self.assertEqual(self.typed, [])
        self.status["wC:p2"] = "done"
        self.tick()
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])

    def test_mail_read_while_busy_needs_no_wake(self):
        self.subscribe("wC:p2")
        self.tick()
        self.status["wC:p2"] = "working"
        self.mail.deliver(101)
        self.tick()
        self.mail.read.add(101)
        self.status["wC:p2"] = "idle"
        self.tick()
        self.assertEqual(self.typed, [])

    def test_same_event_twice_wakes_once(self):
        self.subscribe("wC:p2")
        self.tick()
        self.mail.deliver(101)
        self.tick()
        # The worker woke but has not read yet; the delivery is not seen again.
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])
        self.mail.deliver(102)
        self.tick()
        self.assertEqual(self.typed, ["wC:p2", "wC:p2"])

    def test_unread_mail_at_subscribe_time_wakes(self):
        self.mail.deliver(101)
        self.subscribe("wC:p2")
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])

    def test_aside_pane_is_never_typed_into(self):
        self.subscribe("wC:p1", aside=True)
        self.tick()
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.typed, [])
        self.assertEqual(self.tokens, [("wC:p1", "mail=📬 1")])
        self.mail.read.add(101)
        self.tick()
        self.assertEqual(self.tokens[-1], ("wC:p1", "mail"))

    def test_subscribe_binds_every_pane_the_queen_aside_included_and_unsubscribe_unbinds(self):
        """realm-wake wakes a bound pane with an aside, never typed: the queen's pane is bound like a worker's."""
        self.subscribe("wC:p1", aside=True)
        self.subscribe("wC:p2")
        self.assertEqual({k: bind.read("wC:p1")[k] for k in ("agent", "project", "cursor")},
                         {"agent": "W", "project": "/p", "cursor": 700})
        self.assertIsNotNone(bind.read("wC:p2"))
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])  # the tick still never types into the queen's pane
        cli.cmd_unsubscribe(mock.Mock(pane_id=None, project="/p"))
        self.assertEqual(list(bind.bind_dir().glob("*")), [])

    def test_queen_tab_is_never_typed_into_even_if_subscribed_prompt(self):
        # A state file edited by hand: the queen's pane as a prompt subscriber.
        self.subscribe("wC:p2")
        with state.locked_state() as s:
            s["subscriptions"]["wC:p1"] = s["subscriptions"].pop("wC:p2")
        self.tick()
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.typed, [])

    def test_pane_in_a_queen_workspace_is_never_typed_into(self):
        self.subscribe("wC:p2")
        self.workspaces["wC:p2"] = "👑 other realm"
        self.tick()
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.typed, [])

    def test_lost_cursor_restarts_from_tail_without_losing_unread(self):
        self.subscribe("wC:p2")
        self.tick()
        with state.locked_state() as s:
            s["subscriptions"]["wC:p2"]["cursor"] = 999
        self.status["wC:p2"] = "working"
        self.mail.deliver(101)
        self.tick()
        self.status["wC:p2"] = "idle"
        self.tick()
        self.assertEqual(self.typed, ["wC:p2"])


class ScoutWakeTest(Harness):
    """A scout pane is also woken with its wake_text when scout.scan_due says a scan is due."""

    def subscribe_scout(self):
        self.subscribe("wC:p2", scout=True, wake_text="scan")
        self.tick()  # seeds the mail cursor: an empty inbox, nothing typed while nothing is due
        self.texts.clear()
        self.scan_checks.clear()

    def test_due_and_idle_types_wake_text_once(self):
        self.subscribe_scout()
        self.due = True
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", "scan")])
        self.assertEqual(self.scan_checks, [("/p", self.now)])

    def test_not_due_types_nothing(self):
        self.subscribe_scout()
        self.tick()
        self.assertEqual(self.texts, [])

    def test_busy_scout_is_not_scanned_nor_asked(self):
        self.subscribe_scout()
        self.due = True
        for status in ("working", "blocked"):
            self.status["wC:p2"] = status
            self.tick()
        self.assertEqual(self.texts, [])
        self.assertEqual(self.scan_checks, [])

    def test_mail_wins_one_line_per_tick(self):
        self.subscribe_scout()
        self.due = True
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", daemon.WAKE_TEXT)])
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", daemon.WAKE_TEXT), ("wC:p2", "scan")])

    def test_mail_held_while_busy_still_goes_first_once_idle(self):
        self.subscribe_scout()
        self.due = True
        self.status["wC:p2"] = "working"
        self.mail.deliver(101)
        self.tick()
        self.status["wC:p2"] = "idle"
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", daemon.WAKE_TEXT)])

    def test_unrecorded_scan_is_retyped_only_after_retry_window(self):
        self.subscribe_scout()
        self.due = True
        self.tick()
        self.now += daemon.SCAN_RETRY_SECONDS - 1
        self.tick()
        self.assertEqual(len(self.texts), 1)
        self.now += 1
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", "scan")] * 2)

    def test_broken_scout_never_blocks_mail(self):
        self.subscribe_scout()
        self.due = "raise"
        self.tick()
        self.mail.deliver(101)
        self.tick()
        self.assertEqual(self.texts, [("wC:p2", daemon.WAKE_TEXT)])

    def test_worker_subscription_is_never_scanned(self):
        self.subscribe("wC:p2")
        self.due = True
        self.tick()
        self.tick()
        self.assertEqual(self.texts, [])
        self.assertEqual(self.scan_checks, [])

    def test_queen_tab_refuses_scan_wake(self):
        self.subscribe_scout()
        with state.locked_state() as s:
            s["subscriptions"]["wC:p1"] = s["subscriptions"].pop("wC:p2")
        self.due = True
        self.tick()
        self.assertEqual(self.texts, [])

    def test_scout_and_aside_exclude_each_other(self):
        with self.assertRaises(SystemExit):
            self.subscribe("wC:p2", aside=True, scout=True)

    def test_resubscribe_keeps_last_scan_wake(self):
        self.subscribe_scout()
        self.due = True
        self.tick()
        self.subscribe("wC:p2", scout=True, wake_text="scan")
        self.tick()
        self.assertEqual(len(self.texts), 1)


if __name__ == "__main__":
    unittest.main()
