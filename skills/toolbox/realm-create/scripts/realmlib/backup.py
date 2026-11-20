"""`realm backup`: hourly snapshot of the realm state to Loup's NAS, with retention and restore.

A snapshot is one `realm-<UTC stamp>.tar.gz` holding `realm.db` (taken with SQLite's online backup API, never a
raw copy of the live file), `state.json` and `bind/`. It passes `PRAGMA integrity_check` before it leaves the
Mac, and the NAS copy's SHA-256 must match the local one. Transport: rsync over ssh to the `loup-nas` ssh alias,
whose key is in ~/.ssh/config. A target without `host:` is a local directory (tests, manual copies).

The tick runs `due_backup` after its wake pass: a backup when the last success is older than INTERVAL, retried
no sooner than RETRY after a failure, so a NAS outage costs one ssh timeout per RETRY, not per tick.
"""

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from . import db
from .state import STATE_DIR, locked_state, log

TARGET = os.environ.get("REALM_BACKUP_TARGET") or "loup-nas:/mnt/tank/backup/realm"
INTERVAL = 3600
RETRY = 600
KEEP_HOURLY = 48
KEEP_DAILY = 30
PREFIX, SUFFIX = "realm-", ".tar.gz"
STAMP = "%Y%m%dT%H%M%SZ"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]


class BackupError(RuntimeError):
    pass


def _split(target):
    """`host:/path` → (host, path); a plain path → (None, path)."""
    host, sep, path = target.partition(":")
    return (host, path) if sep and "/" not in host else (None, target)


def _run(cmd, timeout=120):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise BackupError(f"{cmd[0]} exited {p.returncode}: {(p.stderr or p.stdout).strip()[:300]}")
    return p.stdout


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def integrity(path):
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        return conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()


def snapshot(out_dir, now, db_file=None, state_dir=None):
    """Write realm-<stamp>.tar.gz into out_dir and return its path. Raises BackupError on a corrupt snapshot."""
    db_file = Path(db_file or db.db_path())
    state_dir = Path(state_dir or STATE_DIR)
    stage = Path(tempfile.mkdtemp(dir=out_dir, prefix=".stage."))
    try:
        src = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        dst = sqlite3.connect(stage / "realm.db")
        try:
            src.backup(dst)
            # Rollback-journal mode: a single self-contained file, no -wal/-shm beside it once opened.
            dst.execute("PRAGMA journal_mode=DELETE")
        finally:
            dst.close()
            src.close()
        result = integrity(stage / "realm.db")
        if result != "ok":
            raise BackupError(f"integrity_check on snapshot: {result}")
        name = PREFIX + datetime.fromtimestamp(now, timezone.utc).strftime(STAMP) + SUFFIX
        out = Path(out_dir) / name
        with tarfile.open(out, "w:gz") as tar:
            tar.add(stage / "realm.db", arcname="realm.db")
            for extra in ("state.json", "bind"):
                if (state_dir / extra).exists():
                    tar.add(state_dir / extra, arcname=extra)
        return out
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def _stamp(name):
    return datetime.strptime(name[len(PREFIX):-len(SUFFIX)], STAMP).replace(tzinfo=timezone.utc)


def to_prune(names):
    """Snapshot names outside retention: the newest KEEP_HOURLY, plus the newest of each of KEEP_DAILY UTC days."""
    snaps = sorted((n for n in names if n.startswith(PREFIX) and n.endswith(SUFFIX)), reverse=True)
    keep = set(snaps[:KEEP_HOURLY])
    days = []
    for n in snaps:
        day = _stamp(n).date()
        if day not in days:
            days.append(day)
            if len(days) <= KEEP_DAILY:
                keep.add(n)
    return [n for n in snaps if n not in keep]


def _list(target):
    host, path = _split(target)
    if host:
        out = _run(SSH + [host, f"ls -1 {path}"], timeout=60)
        return out.split()
    return os.listdir(path)


def _upload(local, target):
    host, path = _split(target)
    if host:
        _run(["rsync", "-t", "--timeout=60", "-e", " ".join(SSH), str(local), f"{host}:{path}/"], timeout=300)
        remote = _run(SSH + [host, f"sha256sum {path}/{local.name}"], timeout=60).split()[0]
    else:
        shutil.copy2(local, Path(path) / local.name)
        remote = _sha256(Path(path) / local.name)
    if remote != _sha256(local):
        raise BackupError(f"checksum mismatch on {target}/{local.name}")


def _delete(target, names):
    if not names:
        return
    host, path = _split(target)
    if host:
        _run(SSH + [host, "rm -f -- " + " ".join(f"{path}/{n}" for n in names)], timeout=60)
    else:
        for n in names:
            (Path(path) / n).unlink(missing_ok=True)


def run_backup(target=None, now=None, db_file=None, state_dir=None):
    """Snapshot, upload, verify, prune. Returns {file, bytes, integrity, pruned}; raises BackupError on failure."""
    target = target or TARGET
    now = time.time() if now is None else now
    with tempfile.TemporaryDirectory() as tmp:
        snap = snapshot(tmp, now, db_file, state_dir)
        size = snap.stat().st_size
        _upload(snap, target)
        pruned = to_prune(_list(target))
        _delete(target, pruned)
    return {"file": f"{target.rstrip('/')}/{snap.name}", "bytes": size, "integrity": "ok", "pruned": pruned}


def _record(ok, now, detail):
    with locked_state() as s:
        b = s.setdefault("backup", {})
        b["last_attempt"] = now
        if ok:
            b["last_ok"], b["last_file"] = now, detail
            b.pop("last_error", None)
        else:
            b["last_error"] = detail


def backup_logged(now=None):
    """run_backup plus its state record and one log line. Returns the result, or None after a logged failure."""
    now = time.time() if now is None else now
    try:
        out = run_backup(now=now)
    except (BackupError, OSError, sqlite3.Error, subprocess.SubprocessError) as e:
        _record(False, now, str(e))
        log(f"backup: FAILED to {TARGET}: {e}")
        return None
    _record(True, now, out["file"])
    log(f"backup: ok {out['file']} {out['bytes']} B, pruned {len(out['pruned'])}")
    return out


def is_due(b, now):
    if now - b.get("last_ok", 0) < INTERVAL:
        return False
    return "last_error" not in b or now - b.get("last_attempt", 0) >= RETRY


def due_backup(now):
    """The tick's hook: back up when is_due says so. Never raises."""
    try:
        with locked_state() as s:
            due = is_due(s.get("backup", {}), now)
        if due:
            backup_logged(now)
    except Exception as e:  # noqa: BLE001 - a backup problem must never stop the mail wake
        log(f"backup: check failed: {e}")


def restore(source, to_dir=None):
    """Unpack a snapshot (local path or host:/path) into to_dir (default STATE_DIR) after an integrity check.

    Files it replaces are kept beside it as <name>.pre-restore-<stamp>. Stop the tick first (`realm uninstall`).
    """
    to_dir = Path(to_dir or STATE_DIR)
    stamp = time.strftime("%Y%m%dT%H%M%S")
    with tempfile.TemporaryDirectory() as tmp:
        host, path = _split(source)
        local = Path(tmp) / Path(path).name
        if host:
            _run(["rsync", "-t", "--timeout=60", "-e", " ".join(SSH), f"{host}:{path}", str(local)], timeout=300)
        else:
            shutil.copy2(path, local)
        out = Path(tmp) / "x"
        with tarfile.open(local) as tar:
            tar.extractall(out, filter="data")
        result = integrity(out / "realm.db")
        if result != "ok":
            raise BackupError(f"integrity_check on {source}: {result}")
        to_dir.mkdir(parents=True, exist_ok=True)
        for name in ("realm.db-wal", "realm.db-shm"):
            if (to_dir / name).exists():
                (to_dir / name).rename(to_dir / f"{name}.pre-restore-{stamp}")
        restored = []
        for item in sorted(out.iterdir()):
            dest = to_dir / item.name
            if dest.exists():
                dest.rename(to_dir / f"{item.name}.pre-restore-{stamp}")
            shutil.move(str(item), dest)
            restored.append(item.name)
    return {"restored": restored, "to": str(to_dir), "integrity": "ok", "previous_suffix": f".pre-restore-{stamp}"}


def _print(obj):
    db._emit(obj)


def cmd_backup(a):
    if a.bcmd == "run":
        out = backup_logged()
        if out is None:
            sys.exit(1)
        _print(out)
    elif a.bcmd == "list":
        _print(sorted((n for n in _list(TARGET) if n.startswith(PREFIX)), reverse=True))
    elif a.bcmd == "status":
        with locked_state() as s:
            b = dict(s.get("backup", {}))
        b["due"] = is_due(b, time.time())
        b["target"] = TARGET
        _print(b)
    elif a.bcmd == "restore":
        try:
            _print(restore(a.source, a.to))
        except (BackupError, OSError, tarfile.TarError) as e:
            log(f"backup: restore FAILED from {a.source}: {e}")
            sys.exit(1)


def register(sub):
    b = sub.add_parser("backup", help=f"backup: realm state to {TARGET} (the tick runs it hourly)")
    bs = b.add_subparsers(dest="bcmd", required=True)
    bs.add_parser("run", help="snapshot, upload, verify, prune now; exit 1 on failure").set_defaults(fn=cmd_backup)
    bs.add_parser("list", help="snapshots on the target, newest first").set_defaults(fn=cmd_backup)
    bs.add_parser("status", help="last success, last error, due").set_defaults(fn=cmd_backup)
    p = bs.add_parser("restore", help="unpack a snapshot over the state dir (run `realm uninstall` first)")
    p.add_argument("--from", dest="source", required=True, help="snapshot path, local or host:/path")
    p.add_argument("--to", help=f"directory to restore into (default {STATE_DIR})")
    p.set_defaults(fn=cmd_backup)
