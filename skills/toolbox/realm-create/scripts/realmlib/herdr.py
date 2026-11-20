"""herdr CLI adapter: JSON replies, pane lookup, the queen-tab check."""

import json
import os
import shutil
import subprocess

from .state import log

QUEEN_TAB_MARK = "👑"


def herdr_bin():
    return os.environ.get("REALM_HERDR") or shutil.which("herdr") or "herdr"


def herdr(*args):
    """Run herdr; return its JSON reply, `{}` for a silent success, or `{"error": …}`."""
    p = subprocess.run([herdr_bin(), *args], capture_output=True, text=True, timeout=20)
    try:
        out = json.loads(p.stdout or p.stderr or "{}")
    except json.JSONDecodeError:
        out = {}
    if p.returncode != 0 and "error" not in out:
        out = {"error": {"code": f"exit {p.returncode}", "message": (p.stdout + p.stderr).strip()}}
    return out


def pane_info(pane_id):
    """Return the pane dict, "gone" if herdr says it no longer exists, None on other errors."""
    out = herdr("pane", "get", pane_id)
    err = out.get("error")
    if err:
        if err.get("code") == "pane_not_found":
            return "gone"
        log(f"herdr pane get {pane_id} failed: {err}")
        return None
    return out["result"]["pane"]


def is_queen_pane(pane):
    """True when the pane's tab carries the queen label realm-create sets, or herdr cannot say.

    Unknown counts as queen: a failed lookup must never let a prompt through.
    """
    out = herdr("tab", "get", pane.get("tab_id", ""))
    try:
        return QUEEN_TAB_MARK in out["result"]["tab"]["label"]
    except (KeyError, TypeError):
        return True
