"""`realm signal-queen`: a worker rings the queen's doorbell after replying by mail.

The signal is a `signal` pane token on the queen's pane, beside it and never in it: nothing is typed, sent or
keyed into her pane. Mail stays the content. Pending signals live in state.json per realm key, one per worker
(a repeat replaces that worker's entry), and the daemon clears them once the queen's inbox has no unread mail.
"""

import os

from . import db
from .db import Refused
from .herdr import canonical_pane, herdr, is_queen_pane, pane_info
from .state import locked_state, log

SIGNAL_SOURCE = "realm-signal"
TOKEN = "signal"
TEXT_MAX = 80


def render(signals):
    parts = [f"{w}:{s['slug']}" + (f" {s['text']}" if s.get("text") else "") for w, s in sorted(signals.items())]
    return "🔔 " + ", ".join(parts)


def show(pane_id, signals):
    """Set or clear the queen's signal token. report-metadata is display-only: it never reaches her prompt."""
    token = ["--token", f"{TOKEN}={render(signals)}"] if signals else ["--clear-token", TOKEN]
    out = herdr("pane", "report-metadata", pane_id, "--source", SIGNAL_SOURCE, *token)
    if out.get("error"):
        raise RuntimeError(f"herdr pane report-metadata {pane_id}: {out['error']}")


def signal_queen(conn, key, sender, slug, text, now):
    realm = db.realm_row(conn, key)
    queen_pane = realm["queen_pane"]
    if not queen_pane:
        raise Refused(f"realm {key!r} has no queen pane in the db")
    live = {w["name"] for w in db.list_workers(conn, key, now)}
    if sender not in live:
        raise Refused(f"{sender!r} is not a live worker of {key!r}")
    pane = pane_info(queen_pane)
    if not isinstance(pane, dict) or not is_queen_pane(pane):
        raise Refused(f"{queen_pane} is not a queen pane (gone, or its tab lost the queen label)")
    text = " ".join((text or "").split())[:TEXT_MAX]
    entry = {"slug": slug, "text": text, "ts": now}
    with locked_state() as s:
        sub = s["subscriptions"].get(queen_pane)
        if sub and sub["project"] != key:
            raise Refused(f"{queen_pane} is subscribed for {sub['project']!r}, not {key!r}")
        signals = s.setdefault("signals", {}).setdefault(key, {})
        repeat = {k: signals.get(sender, {}).get(k) for k in ("slug", "text")} == {"slug": slug, "text": text}
        signals[sender] = entry
        show(queen_pane, signals)
    log(f"{queen_pane} ({realm['queen']}): signal from {sender} [{slug}]{' (repeat)' if repeat else ''}")
    return {"queen": realm["queen"], "pane": queen_pane, "from": sender, "slug": slug, "text": text,
            "repeat": repeat, "pending": sorted(signals)}


def clear(state, key, pane_id, before):
    """Drop the realm's signals rung before `before` and refresh the token; called with the state lock held."""
    signals = state.get("signals", {}).get(key)
    if not signals:
        return False
    old = [w for w, e in signals.items() if e["ts"] < before]
    if not old:
        return False
    for w in old:
        del signals[w]
    if not signals:
        del state["signals"][key]
    show(pane_id, signals)
    return True


def _sender(a):
    if a.sender:
        return a.sender
    pane = os.environ.get("HERDR_PANE_ID") or ""
    with locked_state() as s:
        sub = s["subscriptions"].get(pane)
    if not sub and pane:  # a pane `realm move` took out of a tab: its env still holds the old id
        moved = canonical_pane(pane)
        with locked_state() as s:
            sub = s["subscriptions"].get(moved)
    if sub:
        return sub["agent"]
    raise Refused("no sender: pass --from <worker>, or run from your subscribed worker pane")


def register(sub):
    p = db.keyed_parser(sub, "signal-queen", "ring the queen after replying by mail: aside token, never typed")
    p.add_argument("--from", dest="sender", help="worker name; default: the agent of $HERDR_PANE_ID's subscription")
    p.add_argument("--slug", required=True, help="the subject you replied on")
    p.add_argument("--text", help=f"one line, at most {TEXT_MAX} characters")
    p.set_defaults(fn=db.run_verb(lambda c, a, now: signal_queen(c, a.key, _sender(a), a.slug, a.text, now)))
