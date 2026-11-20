"""Swarm verbs: create, spawn, wait-joined, retire, status, restart, reinject, dispatch, stop.

Each does the mechanical part of a realm skill step and records it in realm's db, so the queen keeps only
judgement. Every verb acts on one realm key. herdr and Agent Mail are reached through `herdr()` and
`call()`, which tests replace. A registration token is used in memory only, never printed or stored.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path

from . import db
from .db import NeedsHuman, Refused
from .herdr import herdr as _herdr
from .state import locked_state, log

QUEEN_LABEL = "👑 queen"
WORKER_LABEL = "🛠️ subject-"
BRIEF_TEMPLATE = Path(__file__).resolve().parent.parent / "brief.md"
REREAD = "Re-read @{path}: it replaces your previous brief. Follow it from now on, keep your current subject."
PROGRAM = "omp"
IDLE = ("idle", "done")
JOIN_TIMEOUT = 60
LIVE_QUEEN_SECONDS = 300


# ---------- seams (tests replace these) ----------

def herdr(*args):
    return _herdr(*args)


def call(tool, args):
    return db.mail_call(tool, args)


def sleep(seconds):
    time.sleep(seconds)


def now():
    return time.time()


def launchd_loaded():
    from .launchd import LABEL

    p = subprocess.run(["launchctl", "print", f"gui/{os.getuid()}/{LABEL}"], capture_output=True)
    return p.returncode == 0


def launchd_install():
    from .launchd import cmd_install

    cmd_install(None)


# ---------- helpers ----------

def kebab(name):
    """SapphireSwan → sapphire-swan."""
    return re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower()


def brief_dir(key):
    """Per-key brief directory: one realm's stop never deletes another realm's briefs."""
    slug = re.sub(r"[^A-Za-z0-9]+", "-", key).strip("-") or "root"
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir()) / "swarm" / slug


def write_brief(key, name, queen):
    text = BRIEF_TEMPLATE.read_text().format(W=name, w=kebab(name), KEY=key, QUEEN=queen)
    path = brief_dir(key) / f"{kebab(name)}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _ok(out, what):
    if out.get("error"):
        raise Refused(f"herdr {what}: {out['error'].get('message') or out['error']}")
    return out.get("result", {})


def pane(pane_id):
    """herdr's pane dict, or None when it no longer exists."""
    out = herdr("pane", "get", pane_id)
    if (out.get("error") or {}).get("code") == "pane_not_found":
        return None
    return _ok(out, f"pane get {pane_id}")["pane"]


def tab_ids(workspace=None):
    args = ["tab", "list"] + (["--workspace", workspace] if workspace else [])
    return {t["tab_id"]: t for t in _ok(herdr(*args), "tab list")["tabs"]}


def subscribe(pane_id, agent, key, aside):
    """The same row `realm subscribe` writes; cursor None lets the next tick start from the tail."""
    with locked_state() as s:
        old = s["subscriptions"].get(pane_id, {})
        s["subscriptions"][pane_id] = {
            "agent": agent, "project": key, "mode": "aside" if aside else "prompt",
            "cursor": None, "pending": [],
            "last_wake": old.get("last_wake", 0), "last_unread": old.get("last_unread", 0),
        }


def unsubscribe(pane_ids):
    with locked_state() as s:
        for p in pane_ids:
            s["subscriptions"].pop(p, None)


def subscriptions(key):
    with locked_state() as s:
        return {p: v for p, v in s["subscriptions"].items() if v["project"] == key}


def _spawnable(conn, key):
    r = db.realm_row(conn, key)
    if not r["model"] or not r["workspace"]:
        raise Refused(f"realm {key} has no model/workspace recorded: run `realm create` or `realm restart`")
    return r


# ---------- verbs ----------

def spawn(conn, key):
    """Register one worker, write its brief, open its tab, start omp on the brief, subscribe it, record it."""
    r = _spawnable(conn, key)
    ident = call("create_agent_identity", {
        "project_key": key, "program": PROGRAM, "model": r["model"],
        "task_description": f"Swarm worker, queen {r['queen']}",
    })
    name = ident["name"]
    brief = write_brief(key, name, r["queen"])
    res = _ok(herdr("tab", "create", "--workspace", r["workspace"], "--cwd", r["cwd"] or os.getcwd(),
                    "--label", WORKER_LABEL + kebab(name), "--no-focus"), "tab create")
    pane_id, tab_id = res["root_pane"]["pane_id"], res["tab"]["tab_id"]
    _ok(herdr("pane", "run", pane_id, f"{PROGRAM} @{brief}"), "pane run")
    subscribe(pane_id, name, key, aside=False)
    db.add_worker(conn, key, name, pane_id, tab_id, str(brief), now())
    log(f"spawned {name} in {pane_id} for {key}")
    return {"name": name, "pane": pane_id, "tab": tab_id, "brief": str(brief)}


def wait_joined(conn, key, names, timeout=JOIN_TIMEOUT, interval=5):
    """Poll Agent Mail until each named worker is active after registration, or the timeout passes."""
    deadline = now() + timeout
    while True:
        db.sync(conn, key, now(), call)
        workers = {w["name"]: w for w in db.list_workers(conn, key, now())}
        missing = [n for n in names if not (workers.get(n) or {}).get("joined")]
        if not missing or now() >= deadline:
            return {"joined": [n for n in names if n not in missing],
                    "not_joined": [{"name": n, "pane": (workers.get(n) or {}).get("pane")} for n in missing]}
        sleep(interval)


def create(conn, key, size, model, workspace, cwd, queen_pane, queen_tab):
    """Bootstrap a realm from the queen's pane: label, identity, launchd, aside, db, size workers, joins."""
    if size < 1:
        raise Refused("size must be an integer ≥ 1")
    if not (queen_pane and queen_tab and workspace):
        raise Refused("run from the queen's herdr pane: HERDR_PANE_ID, HERDR_TAB_ID and HERDR_WORKSPACE_ID")
    _ok(herdr("tab", "rename", queen_tab, QUEEN_LABEL), "tab rename")
    session = call("macro_start_session", {"human_key": key, "program": PROGRAM, "model": model,
                                           "task_description": "Swarm queen"})
    queen = session["agent"]["name"]
    if not launchd_loaded():
        launchd_install()
    subscribe(queen_pane, queen, key, aside=True)
    db.init_realm(conn, key, queen, queen_pane, now(), model=model, workspace=workspace, cwd=cwd)
    workers = [spawn(conn, key) for _ in range(size)]
    joined = wait_joined(conn, key, [w["name"] for w in workers])
    return {"queen": queen, "inbox": session.get("inbox", []), "workers": workers, **joined}


def retire(conn, key, name):
    """Scale in one idle worker: unsubscribe, close its tab, retire it in Agent Mail, delete its brief."""
    w = db.worker_row(conn, key, name, now())
    if w["retired"]:
        raise Refused(f"{name} is already retired")
    if not w["idle"]:
        raise Refused(f"{name} still holds {w['open_subjects']}: reassign or close them first")
    steps = {}
    unsubscribe([w["pane"]])
    steps["unsubscribe"] = "ok"
    if w["tab"] in tab_ids():
        out = herdr("tab", "close", w["tab"])
        err = (out.get("error") or {}).get("message")
        steps["tab_close"] = err or ("still open" if w["tab"] in tab_ids() else "ok")
    else:
        steps["tab_close"] = "already gone"
    agent = call("macro_start_session", {"human_key": key, "agent_name": name, "program": PROGRAM,
                                         "model": db.realm_row(conn, key)["model"] or "unknown"})["agent"]
    call("retire_agent", {"project_key": key, "agent_name": name,
                          "registration_token": agent.get("registration_token")})
    steps["retire_agent"] = "ok"
    if w["brief"]:
        Path(w["brief"]).unlink(missing_ok=True)
    steps["brief"] = "deleted"
    db.retire_worker(conn, key, name, now())
    return {"name": name, "steps": steps}


def status(conn, key):
    """Worker map: db rows joined with realm subscriptions and herdr's view of each pane."""
    subs = subscriptions(key)
    out = []
    for w in db.list_workers(conn, key, now()):
        p = pane(w["pane"]) if w["pane"] else None
        out.append({**{k: w[k] for k in ("name", "pane", "tab", "idle", "brief_pending", "joined")},
                    "subscribed": subs.get(w["pane"], {}).get("mode"),
                    "agent": p and p.get("agent"), "agent_status": p and p.get("agent_status"),
                    "pane_gone": p is None})
    r = db.realm_row(conn, key)
    return {"queen": r["queen"], "queen_pane": r["queen_pane"], "workers": out}


def dispatch(conn, key, to, slug, title, body, after=None):
    """Send a subject to a worker with the [slug]/topic convention and record it. The daemon wakes the worker."""
    r = db.realm_row(conn, key)
    db.worker_row(conn, key, to, now())
    # Refuse before sending: a mail out with no subject recorded is worse than no mail.
    if conn.execute("SELECT 1 FROM subjects WHERE realm=? AND slug=?", (key, slug)).fetchone():
        raise Refused(f"subject {slug!r} already exists in realm {key!r}: pick another slug")
    if after:
        db.subject_row(conn, key, after)
    if after:
        body = f"queued: start after {after}\n\n{body}"
    sent = call("send_message", {"project_key": key, "sender_name": r["queen"], "to": [to],
                                 "subject": f"[{slug}] {title}", "topic": slug, "body_md": body})
    msg = sent["deliveries"][0]["payload"]
    thread = str(msg.get("thread_id") or msg["id"])
    subject = db.add_subject(conn, key, slug, title, to, after, thread, None, now())
    return {"message_id": msg["id"], "thread_id": thread, "subject": subject}


def _pick_queen(conn, key, agents, queen):
    if queen:
        return queen
    known = conn.execute("SELECT queen FROM realms WHERE key=?", (key,)).fetchone()
    if known:
        return known["queen"]
    cands = [a for a in agents if a.get("task_description") == "Swarm queen"]
    if len(cands) == 1:
        return cands[0]["name"]
    raise NeedsHuman("choose the queen: pass --queen", candidates=[
        {"name": a["name"], "last_active": a.get("last_active_ts")} for a in cands])


def restart(conn, key, model, queen_pane, queen_tab, workspace, cwd, queen=None, force=False):
    """Take over a live realm from this pane: find and resume the queen, move the aside, re-brief workers."""
    if not (queen_pane and queen_tab and workspace):
        raise Refused("run from the new queen's herdr pane: HERDR_PANE_ID, HERDR_TAB_ID and HERDR_WORKSPACE_ID")
    _ok(herdr("tab", "rename", queen_tab, QUEEN_LABEL), "tab rename")
    agents = call("list_agents", {"project_key": key})
    queen = _pick_queen(conn, key, agents, queen)
    if not force:
        others = [t for t, v in tab_ids(workspace).items() if "👑" in v["label"] and t != queen_tab]
        a = next((a for a in agents if a["name"] == queen), {})
        recent = bool(a.get("last_active_ts")) and now() - db.parse_ts(a["last_active_ts"]) < LIVE_QUEEN_SECONDS
        if others or recent:
            raise NeedsHuman("the old queen may still be running; two sessions on one inbox lose replies. "
                             "Pass --force once it is closed", queen_tabs=others,
                             queen_last_active=a.get("last_active_ts"))
    session = call("macro_start_session", {"human_key": key, "agent_name": queen, "program": PROGRAM,
                                           "model": model, "task_description": "Swarm queen"})
    # The aside follows the queen to this pane; any other aside row of this key is the old queen's.
    unsubscribe([p for p, v in subscriptions(key).items() if v["mode"] == "aside" and p != queen_pane])
    subscribe(queen_pane, queen, key, aside=True)
    db.init_realm(conn, key, queen, queen_pane, now(), model=model, workspace=workspace, cwd=cwd)
    # A realm older than the db: adopt the worker panes realm already wakes.
    for p, v in subscriptions(key).items():
        if v["mode"] != "prompt":
            continue
        if not conn.execute("SELECT 1 FROM workers WHERE realm=? AND name=?", (key, v["agent"])).fetchone():
            info = pane(p)
            db.add_worker(conn, key, v["agent"], p, info and info.get("tab_id"), None, now())
    rebriefed = rebrief(conn, key)
    synced = db.sync(conn, key, now(), call)
    return {"queen": queen, "inbox": session.get("inbox", []), **rebriefed, "sync": synced["changes"],
            "table": db.render_table(conn, key, False, now())}


def rebrief(conn, key):
    """Rewrite every live worker's brief from the current template and mark it pending delivery.

    The tick delivers it to an omp pane once idle; a plain shell gets omp started now; a gone pane is reported.
    """
    r = db.realm_row(conn, key)
    pending, started, gone = [], [], []
    for w in db.list_workers(conn, key, now()):
        path = write_brief(key, w["name"], r["queen"])
        db.add_worker(conn, key, w["name"], None, None, str(path), now())
        p = pane(w["pane"]) if w["pane"] else None
        if p is None:
            gone.append({"name": w["name"], "pane": w["pane"]})
        elif p.get("agent") != PROGRAM:
            _ok(herdr("pane", "run", w["pane"], f"{PROGRAM} @{path}"), "pane run")
            started.append(w["name"])
        else:
            db.set_brief_pending(conn, key, w["name"], True)
            pending.append(w["name"])
    return {"brief_pending": pending, "started": started, "pane_gone": gone}


def deliver_brief(pane_id, info, wake):
    """Tick hook: type the re-read prompt into an idle omp worker pane whose brief is pending.

    Returns True when it typed, so the caller types nothing else this tick. wake() keeps its guards.
    """
    if info.get("agent") != PROGRAM or info.get("agent_status") not in IDLE:
        return False
    if not db.db_path().exists():
        return False
    with closing(db.connect()) as conn:
        hit = db.worker_by_pane(conn, pane_id)
        if not hit or not hit[1]["brief_pending"] or not hit[1]["brief"]:
            return False
        key, w = hit
        wake(pane_id, "prompt", REREAD.format(path=w["brief"]))
        db.set_brief_pending(conn, key, w["name"], False)
    log(f"{pane_id} ({w['name']}): brief re-sent")
    return True


def stop(conn, key, own_tab, close_working=False):
    """Close the realm's worker tabs (its subscribed prompt panes only), unsubscribe the key, delete its briefs."""
    subs = subscriptions(key)
    targets = []
    for p, v in subs.items():
        info = pane(p) if v["mode"] == "prompt" else None
        if info is None or info.get("tab_id") == own_tab:
            continue
        targets.append({"pane": p, "agent": v["agent"], "tab": info["tab_id"],
                        "agent_status": info.get("agent_status")})
    working = [t for t in targets if t["agent_status"] == "working"]
    if working and not close_working:
        raise NeedsHuman("workers mid-subject: confirm, then pass --close-working", working=working)
    for t in targets:
        t["error"] = (herdr("tab", "close", t["tab"]).get("error") or {}).get("message")
    still = tab_ids()
    for t in targets:
        if not t["error"] and t["tab"] in still:
            t["error"] = "still open"
    unsubscribe(list(subs))
    shutil.rmtree(brief_dir(key), ignore_errors=True)
    for s in db.list_subjects(conn, key):
        if s["state"] not in ("done", "paused"):
            db.set_state(conn, key, s["slug"], "paused", None, None, now())
    closed = [t for t in targets if not t["error"]]
    names = {t["agent"] for t in closed}
    for w in db.list_workers(conn, key, now()):
        if w["name"] in names:
            db.retire_worker(conn, key, w["name"], now(), keep_subjects=True)
    return {"closed": [{"agent": t["agent"], "tab": t["tab"]} for t in closed],
            "failed": [{"agent": t["agent"], "tab": t["tab"], "error": t["error"]} for t in targets if t["error"]],
            "unsubscribed": sorted(subs), "briefs_deleted": str(brief_dir(key))}


# ---------- CLI ----------

def _read_body(path):
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def register(sub):
    env = os.environ.get
    p = db.keyed_parser(sub, "create", "bootstrap a realm from the queen's pane with SIZE workers")
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--model", required=True)
    p.set_defaults(fn=db.run_verb(lambda c, a, t: create(
        c, a.key, a.size, a.model, env("HERDR_WORKSPACE_ID"), os.getcwd(), env("HERDR_PANE_ID"),
        env("HERDR_TAB_ID"))))

    p = db.keyed_parser(sub, "spawn", "add one worker to the realm")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: spawn(c, a.key)))

    p = db.keyed_parser(sub, "wait-joined", "wait until the named workers joined Agent Mail")
    p.add_argument("names", nargs="+")
    p.add_argument("--timeout", type=int, default=JOIN_TIMEOUT)
    p.set_defaults(fn=db.run_verb(lambda c, a, t: wait_joined(c, a.key, a.names, a.timeout)))

    p = db.keyed_parser(sub, "retire", "scale in: unsubscribe, close tab, retire_agent, delete brief")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=db.run_verb(lambda c, a, t: retire(c, a.key, a.name)))

    p = db.keyed_parser(sub, "status", "worker map: db, subscriptions and herdr panes")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: status(c, a.key)))

    p = db.keyed_parser(sub, "dispatch", "send a [slug] subject to a worker and record it")
    p.add_argument("--to", required=True)
    p.add_argument("--slug", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--body-file", required=True, help="markdown body; - reads stdin")
    p.add_argument("--after", help="slug this one waits for: queued")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: dispatch(
        c, a.key, a.to, a.slug, a.title, _read_body(a.body_file), a.after)))

    p = db.keyed_parser(sub, "restart", "make this pane the queen of a running realm")
    p.add_argument("--model", required=True)
    p.add_argument("--queen", help="queen agent name, when several candidates exist")
    p.add_argument("--force", action="store_true", help="resume even if the old queen looks alive")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: restart(
        c, a.key, a.model, env("HERDR_PANE_ID"), env("HERDR_TAB_ID"), env("HERDR_WORKSPACE_ID"), os.getcwd(),
        a.queen, a.force)))

    p = db.keyed_parser(sub, "reinject", "rewrite every worker's brief; the tick delivers it once idle")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: rebrief(c, a.key)))

    p = db.keyed_parser(sub, "stop", "close the realm's worker tabs, unsubscribe, delete briefs")
    p.add_argument("--close-working", action="store_true", help="also close workers mid-subject")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: stop(c, a.key, env("HERDR_TAB_ID"), a.close_working)))
