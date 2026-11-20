"""Wake logic of realmlib against a fake Agent Mail server and fake herdr panes: no network, no sleeps.

Run: python3 -m unittest test_realm (from this directory).
"""

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from realmlib import cli, daemon, herdr, mail, state
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


class WakeTest(unittest.TestCase):
    def setUp(self):
        tmp = Path(tempfile.mkdtemp())
        self.mail = FakeMail()
        self.status = {"wC:p2": "idle", "wC:p1": "idle"}
        self.tabs = {"wC:p2": "🛠️ subject-w", "wC:p1": "👑 queen"}
        self.typed = []
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
            (daemon, "herdr", self.herdr),
        ):
            patcher = mock.patch.object(module, target, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def herdr(self, *args):
        if args[:2] == ("pane", "get"):
            pane = args[2]
            if pane not in self.status:
                return {"error": {"code": "pane_not_found"}}
            return {"result": {"pane": {"pane_id": pane, "tab_id": pane, "agent_status": self.status[pane]}}}
        if args[:2] == ("tab", "get"):
            return {"result": {"tab": {"label": self.tabs[args[2]]}}}
        if args[:2] == ("pane", "send-text"):
            self.typed.append(args[2])
        if args[:2] == ("pane", "report-metadata"):
            self.tokens.append((args[2], args[-1]))
        return {}

    def subscribe(self, pane, aside=False):
        cli.cmd_subscribe(mock.Mock(pane_id=pane, agent="W", project="/p", aside=aside))

    def tick(self):
        daemon.cmd_tick(None)

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

    def test_queen_tab_is_never_typed_into_even_if_subscribed_prompt(self):
        # A state file edited by hand: the queen's pane as a prompt subscriber.
        self.subscribe("wC:p2")
        with state.locked_state() as s:
            s["subscriptions"]["wC:p1"] = s["subscriptions"].pop("wC:p2")
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


if __name__ == "__main__":
    unittest.main()
