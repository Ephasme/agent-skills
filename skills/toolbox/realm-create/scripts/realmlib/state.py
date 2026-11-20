"""Subscription state file, under an exclusive lock, and realm's log."""

import fcntl
import json
import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

HOME = Path.home()
STATE_DIR = HOME / ".local/state/realm"
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "state.lock"
LOG_FILE = HOME / "Library/Logs/realm.log"


def log(msg):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"{stamp} {msg}"
    print(line, file=sys.stderr)
    if os.environ.get("REALM_LAUNCHD") != "1":
        # Under launchd stderr already goes to LOG_FILE.
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")


@contextmanager
def locked_state():
    """Yield the state dict under an exclusive lock; write it back atomically on exit."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with LOCK_FILE.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            state = json.loads(STATE_FILE.read_text())
        except FileNotFoundError:
            state = {"subscriptions": {}}
        before = json.dumps(state, sort_keys=True)
        yield state
        if json.dumps(state, sort_keys=True) != before:
            fd, tmp = tempfile.mkstemp(dir=STATE_DIR, prefix=".state.")
            with os.fdopen(fd, "w") as f:
                json.dump(state, f, indent=2, sort_keys=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, STATE_FILE)
