"""Tests for realmlib.db: `python3 -m unittest test_realm_db` from this directory. No network, no sleeps."""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from realmlib import db

KEY = "/test/realm"
T0 = 1_800_000_000.0


def iso(ts):
    return db.iso(ts).replace("Z", ".000000Z")


class Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "realm.db"
        self.conn = db.connect(self.path)
        db.init_realm(self.conn, KEY, "Queen", "p0", T0)
        db.add_worker(self.conn, KEY, "Ann", "p1", "t1", "/b/ann.md", T0)
        db.add_worker(self.conn, KEY, "Bob", "p2", "t2", "/b/bob.md", T0)

    def tearDown(self):
        self.conn.close()
        self.dir.cleanup()

    def worker(self, name, now):
        return next(w for w in db.list_workers(self.conn, KEY, now, True) if w["name"] == name)


class Schema(Base):
    def test_wal_and_version(self):
        self.assertEqual(self.conn.execute("PRAGMA journal_mode").fetchone()[0], "wal")
        self.assertEqual(self.conn.execute("PRAGMA user_version").fetchone()[0], len(db.MIGRATIONS))

    def test_reopen_does_not_remigrate(self):
        db.add_subject(self.conn, KEY, "s", "", "Ann", None, None, None, T0)
        again = db.connect(self.path)
        self.addCleanup(again.close)
        self.assertEqual(again.execute("SELECT COUNT(*) FROM subjects").fetchone()[0], 1)

    def test_state_check_constraint(self):
        db.add_subject(self.conn, KEY, "s", "", "Ann", None, None, None, T0)
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("UPDATE subjects SET state='bogus'")

    def test_realms_are_isolated(self):
        db.init_realm(self.conn, "/other", "Q2", None, T0)
        db.add_worker(self.conn, "/other", "Ann", "p9", None, None, T0)
        db.add_subject(self.conn, "/other", "s", "", "Ann", None, None, None, T0)
        self.assertEqual(db.list_subjects(self.conn, KEY), [])
        self.assertEqual(self.worker("Ann", T0)["pane"], "p1")


class Subjects(Base):
    def test_add_with_worker_is_assigned_else_queued(self):
        self.assertEqual(db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)["state"], "assigned")
        self.assertEqual(db.add_subject(self.conn, KEY, "b", "", None, None, None, None, T0)["state"], "queued")
        self.assertEqual(db.add_subject(self.conn, KEY, "c", "", "Ann", "a", None, None, T0)["state"], "queued")

    def test_duplicate_and_unknown_refused(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        for call in (
            lambda: db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0),
            lambda: db.add_subject(self.conn, KEY, "x", "", "Nobody", None, None, None, T0),
            lambda: db.add_subject(self.conn, KEY, "x", "", "Ann", "missing", None, None, T0),
            lambda: db.set_state(self.conn, KEY, "missing", "done", None, None, T0),
            lambda: db.add_subject(self.conn, "/nope", "x", "", None, None, None, None, T0),
        ):
            with self.assertRaises(db.Refused):
                call()

    def test_history_records_each_change(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        db.set_state(self.conn, KEY, "a", "blocked", "needs key", None, T0 + 60)
        db.set_state(self.conn, KEY, "a", "assigned", None, None, T0 + 120)
        db.set_state(self.conn, KEY, "a", "done", "shipped", "42", T0 + 180)
        s = db.show_subject(self.conn, KEY, "a")
        self.assertEqual([e["state"] for e in s["history"]], ["assigned", "blocked", "assigned", "done"])
        self.assertEqual(s["history"][2]["status"], "needs key")  # status kept when omitted
        self.assertEqual((s["status"], s["thread_id"], s["state_changed"]), ("shipped", "42", db.iso(T0 + 180)))

    def test_status_only_update_keeps_state_time(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        s = db.set_state(self.conn, KEY, "a", "assigned", "halfway", None, T0 + 60)
        self.assertEqual((s["status"], s["state_changed"]), ("halfway", db.iso(T0)))

    def test_assigned_needs_worker(self):
        db.add_subject(self.conn, KEY, "a", "", None, None, None, None, T0)
        with self.assertRaises(db.Refused):
            db.set_state(self.conn, KEY, "a", "assigned", None, None, T0)
        self.assertEqual(db.assign_subject(self.conn, KEY, "a", "Bob", "7", T0 + 1)["state"], "assigned")

    def test_retired_worker_cannot_take_work(self):
        db.retire_worker(self.conn, KEY, "Bob", T0)
        with self.assertRaises(db.Refused):
            db.add_subject(self.conn, KEY, "a", "", "Bob", None, None, None, T0)

    def test_list_orders_open_first(self):
        db.add_subject(self.conn, KEY, "d", "", "Ann", None, None, None, T0)
        db.set_state(self.conn, KEY, "d", "done", None, None, T0 + 1)
        db.add_subject(self.conn, KEY, "q", "", None, None, None, None, T0 + 2)
        db.add_subject(self.conn, KEY, "b", "", "Bob", None, None, None, T0 + 3)
        db.set_state(self.conn, KEY, "b", "blocked", None, None, T0 + 4)
        self.assertEqual([s["slug"] for s in db.list_subjects(self.conn, KEY)], ["b", "q", "d"])
        self.assertEqual([s["slug"] for s in db.list_subjects(self.conn, KEY, ["done"])], ["d"])


class Workers(Base):
    def test_idle_and_scale_in(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0 + 60)
        self.assertFalse(self.worker("Ann", T0 + 3600)["idle"])
        bob = self.worker("Bob", T0 + 29 * 60)
        self.assertTrue(bob["idle"])
        self.assertFalse(bob["scale_in"])
        self.assertTrue(self.worker("Bob", T0 + 30 * 60)["scale_in"])
        db.set_state(self.conn, KEY, "a", "done", None, None, T0 + 600)
        ann = self.worker("Ann", T0 + 600 + 30 * 60 - 1)
        self.assertEqual((ann["idle"], ann["scale_in"], ann["idle_since"]), (True, False, db.iso(T0 + 600)))

    def test_paused_and_queued_hold_the_worker(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        db.set_state(self.conn, KEY, "a", "paused", None, None, T0)
        db.add_subject(self.conn, KEY, "b", "", "Bob", "a", None, None, T0)
        later = T0 + 7200
        self.assertFalse(self.worker("Ann", later)["scale_in"])
        self.assertFalse(self.worker("Bob", later)["scale_in"])

    def test_retire_refused_while_holding(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        with self.assertRaises(db.Refused):
            db.retire_worker(self.conn, KEY, "Ann", T0)
        db.set_state(self.conn, KEY, "a", "done", None, None, T0)
        self.assertIsNotNone(db.retire_worker(self.conn, KEY, "Ann", T0)["retired"])
        self.assertNotIn("Ann", [w["name"] for w in db.list_workers(self.conn, KEY, T0)])

    def test_re_add_unretires_and_keeps_fields(self):
        db.retire_worker(self.conn, KEY, "Bob", T0)
        w = db.add_worker(self.conn, KEY, "Bob", "p7", None, None, T0 + 1)
        self.assertEqual((w["retired"], w["pane"], w["tab"]), (None, "p7", "t2"))


class Table(Base):
    def test_markdown(self):
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, "a|b", T0)
        db.add_subject(self.conn, KEY, "b", "", "Ann", "a", None, None, T0)
        out = db.render_table(self.conn, KEY, False, T0 + 3600)
        self.assertIn("| a | Ann | p1 | assigned |", out)
        self.assertIn("a\\|b", out)
        self.assertIn("queued (after a)", out)
        self.assertIn("Idle: Bob (p2, scale in)", out)


class FakeMail:
    def __init__(self):
        self.agents = []
        self.topics = {}

    def __call__(self, tool, args):
        if tool == "list_agents":
            return self.agents
        if tool == "fetch_topic":
            return list(reversed(self.topics.get(args["topic_name"], [])))  # newest first, like the server
        raise AssertionError(tool)

    def msg(self, topic, mid, sender, subject, ts, thread=None):
        self.topics.setdefault(topic, []).append(
            {"id": mid, "from": sender, "subject": subject, "created_ts": iso(ts), "thread_id": thread})


class Sync(Base):
    def test_join_thread_reply_and_queue_release(self):
        mail = FakeMail()
        mail.agents = [
            {"name": "Ann", "inception_ts": iso(T0), "last_active_ts": iso(T0 + 30)},
            {"name": "Bob", "inception_ts": iso(T0), "last_active_ts": iso(T0)},  # never joined
        ]
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0 + 40)
        db.add_subject(self.conn, KEY, "b", "", "Ann", "a", None, None, T0 + 41)
        mail.msg("a", 10, "Queen", "[a] do it", T0 + 40)
        out = db.sync(self.conn, KEY, T0 + 50, mail)
        self.assertEqual(self.worker("Ann", T0 + 50)["joined"], db.iso(T0 + 30))
        self.assertIsNone(self.worker("Bob", T0 + 50)["joined"])
        self.assertEqual(db.subject_row(self.conn, KEY, "a")["thread_id"], "10")
        self.assertEqual(db.subject_row(self.conn, KEY, "b")["state"], "queued")
        self.assertEqual(len(out["changes"]), 2)

        mail.msg("a", 12, "Ann", "[a] side question to Bob", T0 + 90)  # same topic, own thread: not a reply
        mail.msg("a", 13, "Ann", "Re: [a] side question to Bob", T0 + 95, thread="12")
        db.sync(self.conn, KEY, T0 + 96, mail)
        self.assertIsNone(db.subject_row(self.conn, KEY, "a")["last_reply_id"])
        mail.msg("a", 11, "Ann", "Re: [a] do it", T0 + 100, thread="10")
        db.sync(self.conn, KEY, T0 + 110, mail)
        a = db.subject_row(self.conn, KEY, "a")
        self.assertEqual((a["state"], a["unread_reply"], a["last_reply_id"]), ("assigned", True, 11))
        b = db.show_subject(self.conn, KEY, "b")
        self.assertEqual((b["state"], b["history"][-1]["source"]), ("assigned", "sync"))

        db.set_state(self.conn, KEY, "a", "done", None, None, T0 + 120)
        self.assertFalse(db.subject_row(self.conn, KEY, "a")["unread_reply"])
        self.assertEqual(db.sync(self.conn, KEY, T0 + 130, mail)["changes"], [])

    def test_reply_older_than_assignment_releases_nothing(self):
        mail = FakeMail()
        db.add_subject(self.conn, KEY, "a", "", "Ann", None, None, None, T0)
        mail.msg("a", 10, "Queen", "[a] do it", T0)
        mail.msg("a", 11, "Ann", "Re: [a]", T0 + 10, thread="10")
        db.sync(self.conn, KEY, T0 + 20, mail)
        db.set_state(self.conn, KEY, "a", "assigned", "redirected", None, T0 + 30)
        db.set_state(self.conn, KEY, "a", "blocked", None, None, T0 + 31)
        db.set_state(self.conn, KEY, "a", "assigned", None, None, T0 + 32)
        db.add_subject(self.conn, KEY, "b", "", "Ann", "a", None, None, T0 + 33)
        db.sync(self.conn, KEY, T0 + 40, mail)
        self.assertEqual(db.subject_row(self.conn, KEY, "b")["state"], "queued")


class Cli(unittest.TestCase):
    def test_verbs_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "REALM_DB": str(Path(d) / "realm.db"), "HOME": d}
            script = Path(__file__).with_name("realm.py")

            def run(*args, ok=True):
                p = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=env)
                self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
                return p.stdout

            run("init", "--key", KEY, "--queen", "Queen", "--pane", "p0")
            run("worker", "add", "--key", KEY, "--name", "Ann", "--pane", "p1")
            run("subject", "add", "--key", KEY, "--slug", "a", "--worker", "Ann", "--status", "go")
            run("subject", "set-state", "--key", KEY, "--slug", "a", "--state", "nope", ok=False)
            self.assertIn('"error"', run("subject", "show", "--key", KEY, "--slug", "zz", ok=False))
            self.assertIn("| a | Ann | p1 | assigned |", run("table", "--key", KEY))


if __name__ == "__main__":
    unittest.main()
