#!/usr/bin/env python3
"""realm: wake subscribed herdr panes that have unread Agent Mail.

launchd runs `realm tick` every 15 s; each subscriber is woken at most once per its own interval,
only when its Agent Mail inbox has unread messages and herdr does not report its agent as working.
"""

import argparse
import fcntl
import json
import os
import plistlib
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

LABEL = "com.loup.realm"
TICK_SECONDS = 15
DEFAULT_EVERY = 60
WAKE_TEXT = "check your mail"
MAIL_SERVER = "agent-mail-perso"

HOME = Path.home()
STATE_DIR = HOME / ".local/state/realm"
STATE_FILE = STATE_DIR / "state.json"
LOCK_FILE = STATE_DIR / "state.lock"
LOG_FILE = HOME / "Library/Logs/realm.log"
PLIST = HOME / "Library/LaunchAgents" / f"{LABEL}.plist"
MCP_CONFIG = HOME / ".omp/agent/mcp.json"


def log(msg):
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    line = f"{stamp} {msg}"
    print(line, file=sys.stderr)
    if os.environ.get("REALM_LAUNCHD") != "1":
        # Under launchd stderr already goes to LOG_FILE.
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with LOG_FILE.open("a") as f:
            f.write(line + "\n")


# ---------- state ----------

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


# ---------- herdr ----------

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


def pane_status(pane_id):
    """Return the pane's agent_status, "gone" if herdr says it no longer exists, None on other errors."""
    out = herdr("pane", "get", pane_id)
    err = out.get("error")
    if err:
        if err.get("code") == "pane_not_found":
            return "gone"
        log(f"herdr pane get {pane_id} failed: {err}")
        return None
    return out["result"]["pane"].get("agent_status") or "unknown"


def wake(pane_id):
    for args in (("send-text", pane_id, WAKE_TEXT), ("send-keys", pane_id, "enter")):
        out = herdr("pane", *args)
        if out.get("error"):
            raise RuntimeError(f"herdr pane {args[0]} {pane_id}: {out['error']}")


# ---------- Agent Mail ----------

def mail_endpoint():
    """URL and headers of the Agent Mail server, as ~/.omp/agent/mcp.json defines them.

    A header value starting with `!` is a shell command whose stdout is the value, resolved here at call
    time, the way omp resolves it; the credential never lands in this script or in state.
    """
    cfg = json.loads(MCP_CONFIG.read_text())
    servers = cfg.get("mcpServers") or cfg.get("servers") or {}
    srv = servers[MAIL_SERVER]
    headers = {}
    for name, value in (srv.get("headers") or {}).items():
        if value.startswith("!"):
            p = subprocess.run(["/bin/sh", "-c", value[1:]], capture_output=True, text=True, timeout=30)
            value = p.stdout.strip()
            if p.returncode != 0 or not value:
                raise RuntimeError(f"header {name} command failed: {p.stderr.strip()[:200]}")
        headers[name] = value
    return srv["url"], headers


def unread_count(endpoint, agent, project):
    """Unread messages for agent in project, via the read-only inbox priority snapshot.

    `resource://inbox/{agent}?context=true&unread=true` reads one database snapshot without marking
    anything read, acknowledging, or touching activity; fetch_inbox would mark the messages read.
    """
    url, headers = endpoint
    query = urllib.parse.urlencode(
        {"project": project, "context": "true", "unread": "true", "format": "json", "limit": 1000}
    )
    uri = f"resource://inbox/{urllib.parse.quote(agent)}?{query}"
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "resources/read", "params": {"uri": uri}})
    req = urllib.request.Request(
        url,
        data=body.encode(),
        # The server's edge answers 403 to urllib's default `Python-urllib/x.y` User-Agent.
        headers={
            **headers,
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "User-Agent": "realm/1",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        reply = json.loads(resp.read())
    if "error" in reply:
        raise RuntimeError(f"resources/read: {reply['error']}")
    snap = json.loads(reply["result"]["contents"][0]["text"])
    if "messages" not in snap:
        raise RuntimeError(f"unexpected inbox snapshot: {str(snap)[:200]}")
    return sum(1 for m in snap["messages"] if m.get("read_ts") is None)


# ---------- commands ----------

def cmd_subscribe(a):
    with locked_state() as s:
        s["subscriptions"][a.pane_id] = {
            "agent": a.agent,
            "project": a.project,
            "every": a.every,
            "last_wake": s["subscriptions"].get(a.pane_id, {}).get("last_wake", 0),
        }
    log(f"subscribed {a.pane_id} agent={a.agent} project={a.project} every={a.every}s")


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
        print(f"{pane}\t{v['agent']}\t{v['project']}\tevery {v['every']}s\tlast wake {last}")


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
            status = pane_status(pane)
            if status == "gone":
                del subs[pane]
                log(f"{pane} ({v['agent']}): pane gone, unsubscribed")
                continue
            if status is None:
                continue
            if status == "working":
                log(f"{pane} ({v['agent']}): busy, skip")
                continue
            try:
                endpoint = endpoint or mail_endpoint()
                n = unread_count(endpoint, v["agent"], v["project"])
            except (OSError, urllib.error.URLError, RuntimeError, KeyError, ValueError) as e:
                log(f"{pane} ({v['agent']}): mail check failed, skip: {e}")
                continue
            if n == 0:
                log(f"{pane} ({v['agent']}): no unread mail, skip")
                continue
            try:
                wake(pane)
            except (RuntimeError, OSError, subprocess.SubprocessError) as e:
                log(f"{pane} ({v['agent']}): wake failed: {e}")
                continue
            v["last_wake"] = now
            log(f"{pane} ({v['agent']}): {n} unread, woken")


def cmd_install(_a):
    herdr = shutil.which("herdr")
    if not herdr:
        sys.exit("realm install: herdr not on PATH")
    # Unresolved on purpose: the Homebrew symlink survives Python upgrades, the Cellar path does not.
    python = shutil.which("python3") or sys.executable
    script = os.path.realpath(__file__)
    # PATH covers the shell commands mcp.json headers run (sops, …): launchd starts with a bare PATH.
    path_dirs = [os.path.dirname(herdr), "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    env = {
        "PATH": ":".join(dict.fromkeys(path_dirs)),
        "HOME": str(HOME),
        "REALM_HERDR": herdr,
        "REALM_LAUNCHD": "1",
    }
    if os.environ.get("HERDR_SOCKET_PATH"):
        env["HERDR_SOCKET_PATH"] = os.environ["HERDR_SOCKET_PATH"]
    plist = {
        "Label": LABEL,
        "ProgramArguments": [python, script, "tick"],
        "StartInterval": TICK_SECONDS,
        "RunAtLoad": True,
        "EnvironmentVariables": env,
        "StandardOutPath": str(LOG_FILE),
        "StandardErrorPath": str(LOG_FILE),
    }
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    domain = f"gui/{os.getuid()}"
    subprocess.run(["launchctl", "bootout", f"{domain}/{LABEL}"], capture_output=True)
    with PLIST.open("wb") as f:
        plistlib.dump(plist, f)
    subprocess.run(["launchctl", "bootstrap", domain, str(PLIST)], check=True)
    log(f"installed {PLIST} (python={python}, herdr={herdr})")


def cmd_uninstall(_a):
    subprocess.run(["launchctl", "bootout", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    PLIST.unlink(missing_ok=True)
    log(f"uninstalled {PLIST}")


def main():
    ap = argparse.ArgumentParser(prog="realm", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("subscribe", help="wake <pane_id> when <agent> has unread mail")
    p.add_argument("pane_id")
    p.add_argument("--agent", required=True)
    p.add_argument("--project", required=True, help="Agent Mail human_key")
    p.add_argument("--every", type=int, default=DEFAULT_EVERY, help="min seconds between wakes (default 60)")
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


if __name__ == "__main__":
    main()
