"""Tests for realmlib.db: `python3 -m unittest test_realm_db` from this directory. No network, no sleeps."""

import json
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

    def test_migration_8_renames_obsolete_to_stale_and_allows_unclear(self):
        with tempfile.TemporaryDirectory() as d:
            conn = sqlite3.connect(Path(d) / "v7.db", isolation_level=None)
            for n, sql in enumerate(db.MIGRATIONS[:7], start=1):
                for stmt in sql.split(";"):
                    if stmt.strip():
                        conn.execute(stmt)
                conn.execute(f"PRAGMA user_version={n}")
            conn.execute("INSERT INTO realms (key, queen, created_ts, updated_ts) VALUES (?, 'Queen', ?, ?)", (KEY, T0, T0))
            for ref, state, reason in (("a", "rejected", "obsolete"), ("b", "rejected", "mistake"), ("c", "proposed", None)):
                conn.execute("INSERT INTO proposals (realm, source, ref, action, payload, confidence, state, created_ts,"
                             " reason, note) VALUES (?, 'slack', ?, 'task.add', '{}', 'high', ?, ?, ?, 'n')",
                             (KEY, ref, state, T0, reason))
            conn.close()
            conn = db.connect(Path(d) / "v7.db")
            self.addCleanup(conn.close)
            rows = conn.execute("SELECT ref, state, reason, note FROM proposals ORDER BY ref").fetchall()
            self.assertEqual([tuple(r) for r in rows], [("a", "rejected", "stale", "n"), ("b", "rejected", "mistake", "n"),
                                                        ("c", "proposed", None, "n")])
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE proposals SET reason='obsolete' WHERE ref='b'")
            conn.execute("UPDATE proposals SET state='unclear' WHERE ref='c'")
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("UPDATE proposals SET state='bogus' WHERE ref='c'")
            self.assertIn("proposals_by_state", [r[1] for r in conn.execute("PRAGMA index_list(proposals)")])


class Isolation(Base):
    """Two realms in one db, with the same worker name and the same slug: neither sees the other."""

    OTHER = "/other/realm"

    def setUp(self):
        super().setUp()
        db.init_realm(self.conn, self.OTHER, "Queen2", "q0", T0)
        db.add_worker(self.conn, self.OTHER, "Ann", "p9", "t9", None, T0)
        db.add_subject(self.conn, self.OTHER, "s", "theirs", "Ann", None, None, "B", T0)
        db.add_subject(self.conn, KEY, "s", "ours", "Ann", None, None, "A", T0)

    def other(self):
        return (db.list_subjects(self.conn, self.OTHER), db.list_workers(self.conn, self.OTHER, T0 + 9999, True),
                db.show_subject(self.conn, self.OTHER, "s")["history"], db.realm_row(self.conn, self.OTHER))

    def test_every_verb_on_a_leaves_b_untouched(self):
        before = self.other()
        db.init_realm(self.conn, KEY, "QueenX", "p00", T0 + 1)
        db.add_worker(self.conn, KEY, "Ann", "p11", None, None, T0 + 1)
        db.set_state(self.conn, KEY, "s", "blocked", "stuck", "77", T0 + 2)
        db.assign_subject(self.conn, KEY, "s", "Bob", None, T0 + 3)
        db.add_subject(self.conn, KEY, "t", "", "Ann", "s", None, None, T0 + 4)
        db.set_state(self.conn, KEY, "t", "done", None, None, T0 + 5)
        db.retire_worker(self.conn, KEY, "Ann", T0 + 6)
        mail = FakeMail()
        mail.agents = [{"name": "Ann", "inception_ts": iso(T0), "last_active_ts": iso(T0 + 50)}]
        mail.msg("s", 1, "QueenX", "[s] go", T0)
        mail.msg("s", 2, "Bob", "Re: [s] go", T0 + 8, thread="1")
        db.sync(self.conn, KEY, T0 + 9, mail)
        self.assertEqual(self.other(), before)

    def test_reads_are_scoped(self):
        self.assertEqual([s["title"] for s in db.list_subjects(self.conn, KEY)], ["ours"])
        self.assertEqual(db.subject_row(self.conn, KEY, "s")["pane"], "p1")
        self.assertEqual(db.subject_row(self.conn, self.OTHER, "s")["pane"], "p9")
        self.assertNotIn("p9", db.render_table(self.conn, KEY, True, T0))
        self.assertEqual([w["name"] for w in db.list_workers(self.conn, self.OTHER, T0)], ["Ann"])
        self.assertEqual([r["key"] for r in db.list_realms(self.conn)], [self.OTHER, KEY])

    def test_unknown_key_refused(self):
        with self.assertRaises(db.Refused):
            db.list_subjects(self.conn, "/nope")


class ResolveKey(unittest.TestCase):
    def test_project_then_subscription_then_refuse(self):
        with tempfile.TemporaryDirectory() as d:
            state = Path(d) / "state.json"
            state.write_text('{"subscriptions": {"wX:p1": {"project": "/from/pane"}}}')
            self.assertEqual(db.resolve_key("/explicit", "wX:p1", state), "/explicit")
            self.assertEqual(db.resolve_key(None, "wX:p1", state), "/from/pane")
            for pane in ("wX:p2", None):
                with self.assertRaises(db.Refused):
                    env = os.environ.pop("HERDR_PANE_ID", None)
                    try:
                        db.resolve_key(None, pane, state)
                    finally:
                        if env is not None:
                            os.environ["HERDR_PANE_ID"] = env


class Names(Base):
    def test_name_is_unique_and_resolves_to_key(self):
        db.init_realm(self.conn, "/other", "Q2", None, T0, name="secret garden")
        self.assertEqual(db.resolve_key("secret garden", conn=self.conn), "/other")
        self.assertEqual(db.resolve_key(KEY, conn=self.conn), KEY)
        with self.assertRaises(db.Refused):
            db.rename_realm(self.conn, KEY, "secret garden", T0)
        with self.assertRaises(db.Refused):
            db.resolve_key("no such realm", conn=self.conn)
        for bad in ("", " ", "/looks-like-a-key"):
            with self.assertRaises(db.Refused):
                db.rename_realm(self.conn, KEY, bad, T0)

    def test_rename_and_init_keep_name(self):
        db.rename_realm(self.conn, KEY, "garden", T0)
        db.init_realm(self.conn, KEY, "Queen", "p9", T0 + 1)  # restart: no name given
        self.assertEqual(db.realm_row(self.conn, KEY)["name"], "garden")
        self.assertIn("Realm `garden` (/test/realm), queen Queen", db.render_table(self.conn, KEY, False, T0))
        self.assertEqual(db.list_realms(self.conn), [{"key": KEY, "name": "garden"}])


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

            run("init", "--project", KEY, "--queen", "Queen", "--pane", "p0")
            run("worker", "add", "--project", KEY, "--name", "Ann", "--pane", "p1")
            run("subject", "add", "--project", KEY, "--slug", "a", "--worker", "Ann", "--status", "go")
            run("subject", "set-state", "--project", KEY, "--slug", "a", "--state", "nope", ok=False)
            self.assertIn('"error"', run("subject", "show", "--project", KEY, "--slug", "zz", ok=False))
            self.assertIn("| a | Ann | p1 | assigned |", run("table", "--project", KEY))
            env.pop("HERDR_PANE_ID", None)
            self.assertIn("no realm key", run("table", ok=False))
            self.assertIn(KEY, run("realms"))

    def test_proposal_reason_choices(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "realm.db"
            env = {**os.environ, "REALM_DB": str(path), "HOME": d}
            script = Path(__file__).with_name("realm.py")
            conn = db.connect(path)
            db.init_realm(conn, KEY, "Queen", None, T0)
            conn.execute("INSERT INTO proposals (realm, source, ref, action, payload, confidence, state, created_ts)"
                         " VALUES (?, 'slack', 'm1', 'task.add', '{}', 'high', 'proposed', ?)", (KEY, T0))
            conn.close()

            def run(*args, ok=True):
                p = subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, env=env)
                self.assertEqual(p.returncode == 0, ok, p.stdout + p.stderr)
                return p.stdout

            run("proposal", "decide", "--project", KEY, "--reject", "P1", "--reason", "obsolete", ok=False)
            run("proposal", "decide", "--project", KEY, "--reject", "P1", "--reason", "stale")
            self.assertEqual([p["id"] for p in json.loads(run("proposal", "list", "--project", KEY, "--reason", "stale"))],
                             [1])
            run("proposal", "decide", "--project", KEY, "--reject", "P1", "--unclear", "P1", ok=False)
            conn = db.connect(path)
            conn.execute("INSERT INTO proposals (realm, source, ref, action, payload, confidence, state, created_ts)"
                         " VALUES (?, 'slack', 'm2', 'task.add', '{}', 'high', 'proposed', ?)", (KEY, T0))
            conn.close()
            run("proposal", "decide", "--project", KEY, "--unclear", "P2")
            self.assertEqual([(p["id"], p["state"]) for p in json.loads(run("proposal", "list", "--project", KEY))],
                             [(2, "unclear")])


if __name__ == "__main__":
    unittest.main()
