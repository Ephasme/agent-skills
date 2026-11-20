"""The wake pass launchd runs every TICK_SECONDS: wake idle worker panes on new mail, show the queen an aside."""

import subprocess
import time
import urllib.error

from .herdr import herdr, is_queen_pane, pane_info
from . import mail
from .mail import MailToolError
from .state import locked_state, log

TICK_SECONDS = 15
WAKE_TEXT = "check your mail"
TOKEN_SOURCE = "realm"


def wake(pane_id, mode, text=WAKE_TEXT):
    # Hard guard: the only call site of send-text/send-keys. An aside pane or a queen pane is never typed
    # into, whatever the state file says.
    pane = pane_info(pane_id)
    if mode != "prompt" or not isinstance(pane, dict) or is_queen_pane(pane):
        raise RuntimeError(f"refused to type into {pane_id}: aside or queen pane")
    for args in (("send-text", pane_id, text), ("send-keys", pane_id, "enter")):
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
    with locked_state() as s:
        subs = s["subscriptions"]
        endpoint = None
        for pane in list(subs):
            v = subs[pane]
            info = pane_info(pane)
            if info == "gone":
                del subs[pane]
                log(f"{pane} ({v['agent']}): pane gone, unsubscribed")
                continue
            if info is None:
                continue
            status = info.get("agent_status") or "unknown"
            if v.get("mode", "prompt") == "prompt":
                try:
                    from .swarm import deliver_brief

                    # A brief typed this tick counts as busy: the mail wake waits for the next idle tick.
                    if deliver_brief(pane, info, wake):
                        status = "working"
                except Exception as e:  # noqa: BLE001 - a db problem must never stop the mail wake
                    log(f"{pane} ({v['agent']}): brief delivery failed: {e}")
            try:
                endpoint = endpoint or mail.mail_endpoint()
                typed = tick_one(endpoint, pane, v, status)
            except (OSError, urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
                log(f"{pane} ({v['agent']}): mail check failed, skip: {e}")


def tick_one(endpoint, pane, v, status):
    """Advance one subscription. v changes only after the mail reads succeed, so a failure retries next tick."""
    agent, project = v["agent"], v["project"]
    # Entries written before modes existed are prompt subscribers; wake() still guards them.
    mode = v.get("mode", "prompt")
    cursor = v.get("cursor")
    try:
        new, cursor = mail.fetch_events(endpoint, agent, project, cursor)
    except MailToolError as e:
        if e.kind not in ("CURSOR_EXPIRED", "CURSOR_AHEAD"):
            raise
        log(f"{pane} ({agent}): {e.kind}, cursor reset to tail")
        new, cursor = mail.fetch_events(endpoint, agent, project, None)
        v["cursor"] = None
    unread = None
    if v.get("cursor") is None:
        # First sight (new or legacy row, lost cursor): what is unread now stands in for the missed events.
        unread = mail.unread_ids(endpoint, agent, project)
        new = sorted(unread)

    if mode == "aside":
        # Recount while the token shows mail, so it clears once the agent reads it.
        if unread is None and (new or v.get("last_unread", 0)):
            unread = mail.unread_ids(endpoint, agent, project)
        if unread is not None and len(unread) != v.get("last_unread", 0):
            aside(pane, len(unread))
            v["last_unread"] = len(unread)
            v["last_wake"] = time.time()
            log(f"{pane} ({agent}): {len(unread)} unread, aside shown")
        v["cursor"], v["pending"] = cursor, []
        return

    # The cursor advances now: pending carries the new ids until a wake delivers them.
    pending = sorted(set(v.get("pending") or []) | set(new))
    v["cursor"], v["pending"] = cursor, pending
    if not pending:
        return
    # `blocked` panes show a question form: typed text would answer it. Mid-turn text would interrupt.
    if status in ("working", "blocked"):
        if new:
            log(f"{pane} ({agent}): {status}, {len(pending)} pending until it is idle")
        return
    if unread is None:
        unread = mail.unread_ids(endpoint, agent, project)
    still = [m for m in pending if m in unread]
    if not still:
        v["pending"] = []
        log(f"{pane} ({agent}): pending mail already read, no wake")
        return
    try:
        wake(pane, mode)
    except (RuntimeError, OSError, subprocess.SubprocessError) as e:
        log(f"{pane} ({agent}): wake failed: {e}")
        return
    v["pending"] = []
    v["last_wake"] = time.time()
    log(f"{pane} ({agent}): {len(still)} new unread, woken")
