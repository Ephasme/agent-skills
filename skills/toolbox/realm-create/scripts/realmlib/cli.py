"""`realm <verb>`: argparse wiring plus the subscription verbs."""

import argparse
import sys
import time

from . import __doc__ as PACKAGE_DOC
from .daemon import cmd_tick
from .herdr import is_queen_pane, pane_info
from .launchd import LABEL, cmd_install, cmd_uninstall
from .state import locked_state, log

DEFAULT_EVERY = 60


def cmd_subscribe(a):
    mode = "aside" if a.aside else "prompt"
    if mode == "prompt":
        pane = pane_info(a.pane_id)
        if not isinstance(pane, dict) or is_queen_pane(pane):
            sys.exit(f"realm subscribe: {a.pane_id} is the queen's or unknown; only --aside may watch it")
    with locked_state() as s:
        old = s["subscriptions"].get(a.pane_id, {})
        s["subscriptions"][a.pane_id] = {
            "agent": a.agent,
            "project": a.project,
            "every": a.every,
            "mode": mode,
            "last_wake": old.get("last_wake", 0),
            "last_unread": old.get("last_unread", 0),
        }
    log(f"subscribed {a.pane_id} agent={a.agent} project={a.project} every={a.every}s mode={mode}")


def cmd_unsubscribe(a):
    if bool(a.pane_id) == bool(a.project):
        sys.exit("realm unsubscribe: give a pane id or --project, not both")
    with locked_state() as s:
        subs = s["subscriptions"]
        gone = [p for p, v in subs.items() if p == a.pane_id or (a.project and v["project"] == a.project)]
        for p in gone:
            del subs[p]
    for p in gone:
        log(f"unsubscribed {p}")
    if not gone:
        print("nothing to unsubscribe", file=sys.stderr)


def cmd_list(_a):
    with locked_state() as s:
        subs = s["subscriptions"]
    if not subs:
        print("no subscriptions")
    for pane, v in sorted(subs.items()):
        last = time.strftime("%H:%M:%S", time.localtime(v["last_wake"])) if v["last_wake"] else "never"
        mode = v.get("mode", "prompt")
        print(f"{pane}\t{v['agent']}\t{v['project']}\t{mode}\tevery {v['every']}s\tlast wake {last}")


def main():
    ap = argparse.ArgumentParser(prog="realm", description=PACKAGE_DOC.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("subscribe", help="wake <pane_id> when <agent> has unread mail")
    p.add_argument("pane_id")
    p.add_argument("--agent", required=True)
    p.add_argument("--project", required=True, help="Agent Mail human_key")
    p.add_argument("--every", type=int, default=DEFAULT_EVERY, help="min seconds between wakes (default 60)")
    p.add_argument(
        "--aside", action="store_true", help="never type into the pane: pane token only (the queen)"
    )
    p.set_defaults(fn=cmd_subscribe)
    p = sub.add_parser("unsubscribe", help="drop one pane, or every pane of --project")
    p.add_argument("pane_id", nargs="?")
    p.add_argument("--project")
    p.set_defaults(fn=cmd_unsubscribe)
    for name, fn, h in (
        ("list", cmd_list, "show subscriptions"),
        ("tick", cmd_tick, "one wake pass (what launchd runs)"),
        ("install", cmd_install, f"write and load the {LABEL} LaunchAgent"),
        ("uninstall", cmd_uninstall, f"unload and remove the {LABEL} LaunchAgent"),
    ):
        sub.add_parser(name, help=h).set_defaults(fn=fn)
    a = ap.parse_args()
    a.fn(a)
