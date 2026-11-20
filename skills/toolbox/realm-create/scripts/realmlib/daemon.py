"""The wake pass launchd runs every TICK_SECONDS: type into idle worker panes, show the queen an aside."""

import subprocess
import time
import urllib.error

from .herdr import herdr, is_queen_pane, pane_info
from .mail import mail_endpoint, unread_count
from .state import locked_state, log

TICK_SECONDS = 15
WAKE_TEXT = "check your mail"
TOKEN_SOURCE = "realm"


def wake(pane_id, mode):
    # Hard guard: the only call site of send-text/send-keys. An aside pane or a queen pane is never typed
    # into, whatever the state file says.
    pane = pane_info(pane_id)
    if mode != "prompt" or not isinstance(pane, dict) or is_queen_pane(pane):
        raise RuntimeError(f"refused to type into {pane_id}: aside or queen pane")
    for args in (("send-text", pane_id, WAKE_TEXT), ("send-keys", pane_id, "enter")):
        out = herdr("pane", *args)
        if out.get("error"):
            raise RuntimeError(f"herdr pane {args[0]} {pane_id}: {out['error']}")


def aside(pane_id, n):
    """Show unread mail beside the pane, never in it: a pane token, cleared at zero."""
    token = ["--token", f"mail=📬 {n}"] if n else ["--clear-token", "mail"]
    out = herdr("pane", "report-metadata", pane_id, "--source", TOKEN_SOURCE, *token)
    if out.get("error"):
        raise RuntimeError(f"herdr pane report-metadata {pane_id}: {out['error']}")


def cmd_tick(_a):
    now = time.time()
    with locked_state() as s:
        subs = s["subscriptions"]
        due = [p for p, v in subs.items() if now - v["last_wake"] >= v["every"]]
        if not due:
            return
        endpoint = None
        for pane in due:
            v = subs[pane]
            # Entries written before modes existed are prompt subscribers; wake() still guards them.
            mode = v.get("mode", "prompt")
            info = pane_info(pane)
            if info == "gone":
                del subs[pane]
                log(f"{pane} ({v['agent']}): pane gone, unsubscribed")
                continue
            if info is None:
                continue
            status = info.get("agent_status") or "unknown"
            # `blocked` panes show a question form: typed text would answer it. Asides type nothing.
            if mode == "prompt" and status in ("working", "blocked"):
                log(f"{pane} ({v['agent']}): {status}, skip")
                continue
            try:
                endpoint = endpoint or mail_endpoint()
                n = unread_count(endpoint, v["agent"], v["project"])
            except (OSError, urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
                log(f"{pane} ({v['agent']}): mail check failed, skip: {e}")
                continue
            if mode == "aside":
                last = v.get("last_unread", 0)
                if n == last:
                    continue
                try:
                    aside(pane, n)
                except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                    log(f"{pane} ({v['agent']}): aside failed: {e}")
                    continue
                v["last_unread"] = n
                v["last_wake"] = now
                log(f"{pane} ({v['agent']}): {n} unread, aside shown")
                continue
            if n == 0:
                log(f"{pane} ({v['agent']}): no unread mail, skip")
                continue
            try:
                wake(pane, mode)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                log(f"{pane} ({v['agent']}): wake failed: {e}")
                continue
            v["last_wake"] = now
            log(f"{pane} ({v['agent']}): {n} unread, woken")
