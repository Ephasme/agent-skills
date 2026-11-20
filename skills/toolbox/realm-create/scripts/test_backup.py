"""Tests for realmlib.backup: `python3 -m unittest test_backup` from this directory. Local targets only, no ssh."""

import json
import sqlite3
import tarfile
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from realmlib import backup, db, state

KEY = "/test/realm"
T0 = 1_800_000_000.0


def name_at(dt):
    return backup.PREFIX + dt.strftime(backup.STAMP) + backup.SUFFIX


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.state_dir = self.tmp / "state"
        self.target = self.tmp / "nas"
        self.target.mkdir()
        self.db_file = self.state_dir / "realm.db"
        conn = db.connect(self.db_file)
        db.init_realm(conn, KEY, "Queen", "p0", T0)
        # Left open: the snapshot must read a live WAL database, as the tick sees it.
        self.addCleanup(conn.close)
        self.conn = conn
        (self.state_dir / "state.json").write_text(json.dumps({"subscriptions": {"p1": {"agent": "A"}}}))
        (self.state_dir / "bind").mkdir()
        (self.state_dir / "bind" / "p1.json").write_text("{}")
        for module, target, value in (
            (state, "STATE_DIR", self.state_dir), (state, "STATE_FILE", self.state_dir / "state.json"),
            (state, "LOCK_FILE", self.state_dir / "state.lock"), (state, "LOG_FILE", self.tmp / "realm.log"),
            # Never the NAS, never the live state dir or db.
            (backup, "TARGET", str(self.target)), (backup, "STATE_DIR", self.state_dir),
            (db, "db_path", lambda: self.db_file),
        ):
            p = mock.patch.object(module, target, value)
            p.start()
            self.addCleanup(p.stop)

    def run_backup(self, now=T0):
        return backup.run_backup(str(self.target), now, self.db_file, self.state_dir)


class RunBackup(Base):
    def test_snapshot_lands_verified_with_all_parts(self):
        out = self.run_backup()
        f = self.target / Path(out["file"]).name
        self.assertTrue(f.exists())
        with tarfile.open(f) as tar:
            self.assertEqual(sorted(tar.getnames()), ["bind", "bind/p1.json", "realm.db", "state.json"])
            tar.extractall(self.tmp / "x", filter="data")
        self.assertEqual(backup.integrity(self.tmp / "x" / "realm.db"), "ok")
        rows = sqlite3.connect(self.tmp / "x" / "realm.db").execute("SELECT key FROM realms").fetchall()
        self.assertEqual(rows, [(KEY,)])

    def test_uncommitted_wal_rows_are_in_the_snapshot(self):
        self.conn.execute("UPDATE realms SET queen='Later'")
        self.run_backup()
        f = next(self.target.iterdir())
        with tarfile.open(f) as tar:
            tar.extractall(self.tmp / "x", filter="data")
        q = sqlite3.connect(self.tmp / "x" / "realm.db").execute("SELECT queen FROM realms").fetchone()[0]
        self.assertEqual(q, "Later")

    def test_unreachable_target_raises(self):
        with self.assertRaises((backup.BackupError, OSError)):
            backup.run_backup(str(self.tmp / "missing"), T0, self.db_file, self.state_dir)


class Retention(unittest.TestCase):
    def test_hourly_then_daily(self):
        start = datetime(2026, 11, 20, 23, tzinfo=timezone.utc)
        names = [name_at(start - timedelta(hours=h)) for h in range(24 * 40)]
        prune = set(backup.to_prune(names))
        keep = [n for n in names if n not in prune]
        self.assertTrue(set(names[:48]) <= set(keep))
        days = {backup._stamp(n).date() for n in keep}
        self.assertEqual(len(days), 30)
        # From 23:00 the 48 hourlies cover exactly 2 UTC days, whose newest snapshots are already kept as dailies.
        self.assertEqual(len(keep), 48 + 30 - 2)
        self.assertEqual(len(keep) + len(prune), len(names))


class PruneOnTarget(Base):
    def test_prune_applied_on_target(self):
        start = datetime.fromtimestamp(T0, timezone.utc)
        for h in range(1, 24 * 35):
            (self.target / name_at(start - timedelta(hours=h))).write_bytes(b"x")
        (self.target / "unrelated.txt").write_text("keep")
        out = self.run_backup()
        left = {p.name for p in self.target.iterdir()}
        self.assertIn("unrelated.txt", left)
        self.assertIn(Path(out["file"]).name, left)
        # T0 is 08:00 UTC: the 48 hourlies span 3 UTC days, whose newest snapshots double as dailies.
        self.assertEqual(len(left - {"unrelated.txt"}), 48 + 30 - 3)
        self.assertEqual(len(left) - 1 + len(out["pruned"]), 24 * 35)


class Schedule(Base):
    def test_due_after_an_hour_and_retry_after_failure(self):
        self.assertTrue(backup.is_due({}, T0))
        self.assertFalse(backup.is_due({"last_ok": T0}, T0 + 3599))
        self.assertTrue(backup.is_due({"last_ok": T0}, T0 + 3600))
        failed = {"last_ok": T0, "last_attempt": T0 + 3600, "last_error": "x"}
        self.assertFalse(backup.is_due(failed, T0 + 3600 + 599))
        self.assertTrue(backup.is_due(failed, T0 + 3600 + 600))

    def test_failure_is_logged_and_recorded_not_raised(self):
        with mock.patch.object(backup, "TARGET", str(self.tmp / "missing")):
            backup.due_backup(T0)
        s = json.loads((self.state_dir / "state.json").read_text())
        self.assertIn("last_error", s["backup"])
        self.assertNotIn("last_ok", s["backup"])
        self.assertIn("backup: FAILED", (self.tmp / "realm.log").read_text())

    def test_success_records_last_ok(self):
        backup.due_backup(T0)
        backup.due_backup(T0 + 60)
        s = json.loads((self.state_dir / "state.json").read_text())
        self.assertEqual(s["backup"]["last_ok"], T0)
        self.assertEqual(len(list(self.target.iterdir())), 1)


class Restore(Base):
    def test_restore_replaces_and_keeps_previous(self):
        out = self.run_backup()
        dest = self.tmp / "restored"
        dest.mkdir()
        (dest / "realm.db").write_text("old")
        r = backup.restore(str(self.target / Path(out["file"]).name), dest)
        self.assertEqual(sorted(r["restored"]), ["bind", "realm.db", "state.json"])
        self.assertEqual(backup.integrity(dest / "realm.db"), "ok")
        self.assertEqual((dest / f"realm.db{r['previous_suffix']}").read_text(), "old")
        self.assertEqual(json.loads((dest / "state.json").read_text())["subscriptions"]["p1"]["agent"], "A")

    def test_corrupt_snapshot_refused_before_touching_dest(self):
        bad = self.tmp / "bad"
        bad.mkdir()
        (bad / "realm.db").write_bytes(b"not a database" * 100)
        f = self.target / name_at(datetime.fromtimestamp(T0, timezone.utc))
        with tarfile.open(f, "w:gz") as tar:
            tar.add(bad / "realm.db", arcname="realm.db")
        dest = self.tmp / "restored"
        dest.mkdir()
        (dest / "realm.db").write_text("old")
        with self.assertRaises((backup.BackupError, sqlite3.DatabaseError)):
            backup.restore(str(f), dest)
        self.assertEqual((dest / "realm.db").read_text(), "old")


if __name__ == "__main__":
    unittest.main()
