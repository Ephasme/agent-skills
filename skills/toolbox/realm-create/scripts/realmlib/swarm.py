"""Swarm verbs: create, spawn, wait-joined, retire, move, status, restart, reinject, dispatch, stop.

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

from . import bind, db, hindsight
from .db import NeedsHuman, Refused
from .herdr import QUEEN_TAB_MARK, herdr as _herdr
from .state import locked_state, log

QUEEN_LABEL = "👑 queen"
WORKER_MARK = "🛠️"
BRIEF_TEMPLATE = Path(__file__).resolve().parent.parent / "brief.md"
REREAD = "Re-read @{path}: it replaces your previous brief. Follow it from now on, keep your current subject."
PROGRAM = "omp"
IDLE = ("idle", "done")
JOIN_TIMEOUT = 60
LIVE_QUEEN_SECONDS = 300
REALM_ORIGIN = re.compile(r"[:/]spare-cycles/realm(\.git)?$")


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


def label_step(realm_label, name, workspace):
    """The brief's first step: label its own workspace, or its tab on rows older than workspaces.

    The workspace id is written out, never `$HERDR_WORKSPACE_ID`: in a tab worker's pane, and in a pane
    `realm move` took out of a tab, that variable still names the queen's workspace."""
    if workspace:
        return f'`herdr workspace rename {workspace} "{WORKER_MARK} {realm_label} · {kebab(name)}"`'
    return f'`herdr tab rename "$HERDR_TAB_ID" "{WORKER_MARK} subject-{kebab(name)}"`'


def write_brief(key, name, queen, workspace, realm_label=None):
    realm_label = realm_label or key
    text = BRIEF_TEMPLATE.read_text().format(W=name, w=kebab(name), KEY=key, QUEEN=queen, REALM=realm_label,
                                             LABEL_STEP=label_step(realm_label, name, workspace))
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


def workspace_ids():
    return {w["workspace_id"]: w for w in _ok(herdr("workspace", "list"), "workspace list")["workspaces"]}


def closable_workspace(ws, queen_workspace, live):
    """A workspace realm may close whole: not the realm's queen workspace, and not labelled 👑 by any realm."""
    return bool(ws) and ws != queen_workspace and QUEEN_TAB_MARK not in (live.get(ws) or {}).get("label", "")


def open_workspace(label, cwd):
    """A top-level workspace (never nested under the queen's), unfocused: (pane id, workspace id)."""
    res = _ok(herdr("workspace", "create", "--cwd", cwd, "--label", label, "--no-focus"), "workspace create")
    return res["root_pane"]["pane_id"], res["workspace"]["workspace_id"]


def close_home(workspace, tab, queen_workspace):
    """Close a worker's own workspace, or its tab in the queen's workspace on rows older than workspaces.

    Returns (what, id, outcome): outcome "ok", "already gone", "still open" or herdr's error. The queen's
    workspace is never closed: a row naming it falls back to the tab.
    """
    if workspace and workspace != queen_workspace:
        live = workspace_ids()
        if workspace not in live:
            return "workspace", workspace, "already gone"
        if not closable_workspace(workspace, queen_workspace, live):
            return "workspace", workspace, "refused: queen workspace"
        kind, target, live = "workspace", workspace, workspace_ids
    else:
        kind, target, live = "tab", tab, tab_ids
    if not target or target not in live():
        return kind, target, "already gone"
    err = (herdr(kind, "close", target).get("error") or {}).get("message")
    return kind, target, err or ("still open" if target in live() else "ok")


def worker_label(realm, name):
    return f"{WORKER_MARK} {db.label(realm)} · {kebab(name)}"


def subscribe(pane_id, agent, key, aside):
    """The same row `realm subscribe` writes; cursor None lets the next tick start from the tail.

    Also binds the pane for the `realm-wake` extension, at the agent's delivery tail taken now: mail sent after
    this call is a delivery the extension wakes on, whatever the agent's connect marks read."""
    with locked_state() as s:
        old = s["subscriptions"].get(pane_id, {})
        s["subscriptions"][pane_id] = {
            "agent": agent, "project": key, "mode": "aside" if aside else "prompt",
            "cursor": None, "pending": [],
            "last_wake": old.get("last_wake", 0), "last_unread": old.get("last_unread", 0),
        }
    bind_pane(pane_id, agent, key)


def bind_pane(pane_id, agent, key):
    tail = call("fetch_inbox_events", {"project_key": key, "agent_name": agent, "position_now": True})
    bind.write(pane_id, agent, key, tail["tail_cursor"])


def unsubscribe(pane_ids):
    with locked_state() as s:
        for p in pane_ids:
            s["subscriptions"].pop(p, None)
    bind.remove(pane_ids)


def subscriptions(key):
    with locked_state() as s:
        return {p: v for p, v in s["subscriptions"].items() if v["project"] == key}


def realm_repo(path=None):
    """The realm git repository every worker and the scout start in: `path`, else $REALM_REPO, else
    ~/code/perso/realm. Refused unless it is that repo's work tree root with origin spare-cycles/realm: never the
    caller's directory."""
    p = Path(path or os.environ.get("REALM_REPO") or Path.home() / "code/perso/realm").expanduser()

    def git(*args):
        r = subprocess.run(["git", "-C", str(p), *args], capture_output=True, text=True)
        return r.stdout.strip() if r.returncode == 0 else None

    top = git("rev-parse", "--show-toplevel") if p.is_dir() else None
    origin = git("remote", "get-url", "origin") if top else None
    if not top or Path(top).resolve() != p.resolve() or not origin or not REALM_ORIGIN.search(origin):
        raise Refused(f"{p} is not the realm repository (a work tree root whose origin is spare-cycles/realm): "
                      "clone it there or set REALM_REPO")
    return str(p.resolve())


def _spawnable(conn, key):
    """The realm row, its cwd checked to be the realm repo: a worker never starts anywhere else."""
    r = db.realm_row(conn, key)
    if not r["model"] or not r["workspace"]:
        raise Refused(f"realm {key} has no model/workspace recorded: run `realm create` or `realm restart`")
    r["cwd"] = realm_repo(r["cwd"])
    return r


# ---------- verbs ----------

def spawn(conn, key):
    """Register one worker, write its brief, open its workspace, start omp on the brief, subscribe it, record it."""
    r = _spawnable(conn, key)
    ident = call("create_agent_identity", {
        "project_key": key, "program": PROGRAM, "model": r["model"],
        "task_description": f"Swarm worker, queen {r['queen']}",
    })
    name = ident["name"]
    pane_id, ws = open_workspace(worker_label(r, name), r["cwd"])
    subscribe(pane_id, name, key, aside=False)  # bound before omp starts: its first poll already finds the file
    brief = write_brief(key, name, r["queen"], ws, db.label(r))
    _ok(herdr("pane", "run", pane_id, f"{PROGRAM} @{brief}"), "pane run")
    db.add_worker(conn, key, name, pane_id, None, str(brief), now(), workspace=ws)
    log(f"spawned {name} in {pane_id} ({ws}) for {key}")
    return {"name": name, "pane": pane_id, "workspace": ws, "brief": str(brief)}


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


def queen_label(realm_name):
    return f"{QUEEN_LABEL} · {realm_name}" if realm_name else QUEEN_LABEL


def label_queen_workspace(workspace):
    """Prefix the queen's workspace label with 👑, keeping the rest, unless a subscribed prompt pane (a tab-era
    worker or scout, any realm) lives in it: the guard would then refuse every wake there.
    Returns "ok", "already marked" or why it was left alone."""
    with locked_state() as s:
        prompts = [p for p, v in s["subscriptions"].items() if v["mode"] == "prompt"]
    if any((pane(p) or {}).get("workspace_id") == workspace for p in prompts):
        return "left alone: worker tabs still in it"
    label = _ok(herdr("workspace", "get", workspace), "workspace get")["workspace"]["label"]
    if QUEEN_TAB_MARK in label:
        return "already marked"
    _ok(herdr("workspace", "rename", workspace, f"{QUEEN_TAB_MARK} {label}"), "workspace rename")
    return "ok"


def create(conn, key, size, model, workspace, queen_pane, queen_tab, name=None):
    """Bootstrap a realm from the queen's pane: label, identity, launchd, aside, db, size workers, joins."""
    if size < 1:
        raise Refused("size must be an integer ≥ 1")
    if not (queen_pane and queen_tab and workspace):
        raise Refused("run from the queen's herdr pane: HERDR_PANE_ID, HERDR_TAB_ID and HERDR_WORKSPACE_ID")
    db._check_name(conn, key, name)  # before any side effect
    cwd = realm_repo()
    _ok(herdr("tab", "rename", queen_tab, queen_label(name)), "tab rename")
    ws_label = label_queen_workspace(workspace)
    session = call("macro_start_session", {"human_key": key, "program": PROGRAM, "model": model,
                                           "task_description": "Swarm queen"})
    queen = session["agent"]["name"]
    if not launchd_loaded():
        launchd_install()
    subscribe(queen_pane, queen, key, aside=True)
    db.init_realm(conn, key, queen, queen_pane, now(), model=model, workspace=workspace, cwd=cwd, name=name)
    hindsight.on_create(key)
    workers = [spawn(conn, key) for _ in range(size)]
    joined = wait_joined(conn, key, [w["name"] for w in workers])
    return {"queen": queen, "queen_workspace": ws_label, "inbox": session.get("inbox", []), "workers": workers,
            **joined}


def retire(conn, key, name):
    """Scale in one worker: unsubscribe, close its workspace (its tab on older rows), retire it in Agent Mail,
    delete its brief.

    Only a worker whose subjects are all done: a paused one too keeps it, since retiring loses its conversation.
    The queen closes or reassigns each subject first, explicitly; there is no override.
    """
    w = db.worker_row(conn, key, name, now())
    if w["retired"]:
        raise Refused(f"{name} is already retired")
    if not w["idle"]:
        raise Refused(f"{name} still holds {w['open_subjects']}: close or reassign each one first")
    steps = {}
    unsubscribe([w["pane"]])
    steps["unsubscribe"] = "ok"
    kind, _, outcome = close_home(w["workspace"], w["tab"], db.realm_row(conn, key)["workspace"])
    steps[f"{kind}_close"] = outcome
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


def move(conn, key, name):
    """Move a tab-era worker or scout pane into its own workspace with `herdr pane move`: the process keeps
    running, mid-turn included, so the agent keeps its conversation and its current subject. Then rekey its
    subscription, record the pane and workspace, and rewrite its brief for a later restart.
    """
    r = db.realm_row(conn, key)
    row = conn.execute("SELECT * FROM workers WHERE realm=? AND name=? AND retired_ts IS NULL",
                       (key, name)).fetchone()
    scout = None if row else conn.execute("SELECT * FROM scouts WHERE realm=? AND agent=?", (key, name)).fetchone()
    if not (row or scout):
        raise Refused(f"no live worker or scout {name!r} in realm {key!r}")
    old = (row or scout)["pane"]
    info = pane(old) if old else None
    if info is None:
        raise Refused(f"{name}'s pane {old} is gone")
    tab_label = (herdr("tab", "get", info["tab_id"]).get("result") or {}).get("tab", {}).get("label")
    # By tab, not is_queen_pane: the queen's workspace label may carry 👑 while worker tabs still sit in it.
    if r["queen_pane"] in (old, info["pane_id"]) or tab_label is None or QUEEN_TAB_MARK in tab_label:
        raise Refused(f"{old} is the queen's pane, or its tab cannot be read")
    # Realms created before the db recorded a workspace: the queen's pane says where she lives.
    queen_ws = r["workspace"]
    if not queen_ws and r["queen_pane"]:
        queen_ws = (pane(r["queen_pane"]) or {}).get("workspace_id")
    if not queen_ws:
        raise Refused(f"realm {key} records no queen workspace and her pane {r['queen_pane']} is gone")
    if info["workspace_id"] != queen_ws:
        raise Refused(f"{name} is already outside the queen's workspace {queen_ws}, in {info['workspace_id']}")
    from . import scout as scout_mod  # scout imports swarm
    label = f"{scout_mod.SCOUT_MARK} {db.label(r)} · scout" if scout else worker_label(r, name)
    res = _ok(herdr("pane", "move", old, "--new-workspace", "--label", label, "--no-focus"), "pane move")["move_result"]
    new, ws = res["pane"]["pane_id"], res["pane"]["workspace_id"]
    with locked_state() as s:
        subs = s["subscriptions"]
        sub = subs.pop(old, None) or subs.pop(info["pane_id"], None)
        if sub:
            subs[new] = sub
    # The moved session keeps its old `$HERDR_PANE_ID`; realm-wake asks herdr for the pane's current id when no
    # file sits under the old one, so the binding and its saved cursor move to the new id.
    bind.move(old, new) or bind.move(info["pane_id"], new)
    if scout:
        brief = scout_mod.write_brief(key, name, r["queen"], label, ws)
        sql = "UPDATE scouts SET pane=?, workspace=?, tab=NULL, brief=? WHERE realm=? AND agent=?"
    else:
        brief = write_brief(key, name, r["queen"], ws, db.label(r))
        sql = "UPDATE workers SET pane=?, workspace=?, tab=NULL, brief=? WHERE realm=? AND name=?"
    with db.tx(conn):
        conn.execute(sql, (new, ws, str(brief), key, name))
    log(f"moved {name} {old} → {new} ({ws}) for {key}")
    return {"name": name, "old_pane": old, "pane": new, "workspace": ws,
            "closed_tab": res.get("closed_tab_id"), "subscribed": bool(sub),
            "queen_workspace": label_queen_workspace(queen_ws)}


def status(conn, key):
    """Worker map: db rows joined with realm subscriptions and herdr's view of each pane."""
    subs = subscriptions(key)
    out = []
    for w in db.list_workers(conn, key, now()):
        p = pane(w["pane"]) if w["pane"] else None
        out.append({**{k: w[k] for k in ("name", "pane", "workspace", "tab", "idle", "brief_pending", "joined")},
                    "subscribed": subs.get(w["pane"], {}).get("mode"),
                    "agent": p and p.get("agent"), "agent_status": p and p.get("agent_status"),
                    "pane_gone": p is None})
    r = db.realm_row(conn, key)
    return {"realm": db.label(r), "queen": r["queen"], "queen_pane": r["queen_pane"], "workers": out}


def dispatch(conn, key, to, slug, title, body, after=None):
    """Send a subject to a worker with the [slug]/topic convention and record it. The daemon wakes the worker.

    A worker that has not joined yet is waited for first: its connect (`macro_start_session`) marks its inbox
    read, and the daemon wakes only on unread mail, so a subject sent before it would never start.
    """
    r = db.realm_row(conn, key)
    w = db.worker_row(conn, key, to, now())
    # Refuse before sending: a mail out with no subject recorded is worse than no mail.
    if conn.execute("SELECT 1 FROM subjects WHERE realm=? AND slug=?", (key, slug)).fetchone():
        raise Refused(f"subject {slug!r} already exists in realm {key!r}: pick another slug")
    if after:
        db.subject_row(conn, key, after)
    if not w["joined"] and wait_joined(conn, key, [to])["not_joined"]:
        raise Refused(f"{to} has not joined Agent Mail after {JOIN_TIMEOUT}s; its connect would mark this subject "
                      f"read and nothing would wake it. Nothing sent: check its pane, then dispatch again")
    if after:
        body = f"queued: start after {after}\n\n{body}"
    body += hindsight.context_block(key, f"{title}\n{body[:500]}")
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


def restart(conn, key, model, queen_pane, queen_tab, workspace, queen=None, force=False):
    """Take over a live realm from this pane: find and resume the queen, move the aside, re-brief workers."""
    if not (queen_pane and queen_tab and workspace):
        raise Refused("run from the new queen's herdr pane: HERDR_PANE_ID, HERDR_TAB_ID and HERDR_WORKSPACE_ID")
    cwd = realm_repo()  # before any side effect; the realm's cwd is the realm repo, never this pane's directory
    known = conn.execute("SELECT name FROM realms WHERE key=?", (key,)).fetchone()
    _ok(herdr("tab", "rename", queen_tab, queen_label(known and known["name"])), "tab rename")
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
    # A realm older than the db: adopt the worker panes realm already wakes. A pane is recorded as owning its
    # workspace only when realm labelled that workspace a worker's.
    live_ws = workspace_ids()
    for p, v in subscriptions(key).items():
        if v["mode"] != "prompt":
            continue
        if not bind.read(p):  # a pane subscribed before bind files existed
            bind_pane(p, v["agent"], key)
        if not conn.execute("SELECT 1 FROM workers WHERE realm=? AND name=?", (key, v["agent"])).fetchone():
            info = pane(p) or {}
            ws = info.get("workspace_id")
            own = ws != workspace and WORKER_MARK in (live_ws.get(ws) or {}).get("label", "")
            db.add_worker(conn, key, v["agent"], p, None if own else info.get("tab_id"), None, now(),
                          workspace=ws if own else None)
    ws_label = label_queen_workspace(workspace)
    rebriefed = rebrief(conn, key)
    synced = db.sync(conn, key, now(), call)
    return {"queen": queen, "queen_workspace": ws_label, "inbox": session.get("inbox", []), **rebriefed,
            "sync": synced["changes"],
            "table": db.render_table(conn, key, False, now())}


def rebrief(conn, key):
    """Rewrite every live worker's brief from the current template and mark it pending delivery.

    The tick delivers it to an omp pane once idle; a plain shell gets omp started now; a gone pane is reported.
    """
    r = db.realm_row(conn, key)
    pending, started, gone = [], [], []
    for w in db.list_workers(conn, key, now()):
        path = write_brief(key, w["name"], r["queen"], w["workspace"], db.label(r))
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


def _homes(conn, key):
    """pane → workspace the db records as that pane's own, for the key's live workers and its scout."""
    rows = conn.execute("SELECT pane, workspace FROM workers WHERE realm=? AND retired_ts IS NULL "
                        "UNION ALL SELECT pane, workspace FROM scouts WHERE realm=?", (key, key)).fetchall()
    return {r["pane"]: r["workspace"] for r in rows if r["pane"] and r["workspace"]}


def stop(conn, key, own_tab, close_working=False):
    """Close the realm's worker workspaces (its subscribed prompt panes only; a tab on rows older than
    workspaces), unsubscribe the key, delete its briefs."""
    subs = subscriptions(key)
    homes = _homes(conn, key)
    queen_ws, live_ws = db.realm_row(conn, key)["workspace"], workspace_ids()
    targets = []
    for p, v in subs.items():
        info = pane(p) if v["mode"] == "prompt" else None
        if info is None or info.get("tab_id") == own_tab:
            continue
        # A whole workspace is closed only when the db says it is this pane's own, and never a queen's.
        ws = homes.get(p)
        if ws != info.get("workspace_id") or not closable_workspace(ws, queen_ws, live_ws):
            ws = None
        targets.append({"pane": p, "agent": v["agent"], "workspace": ws, "tab": None if ws else info["tab_id"],
                        "agent_status": info.get("agent_status")})
    working = [t for t in targets if t["agent_status"] == "working"]
    if working and not close_working:
        raise NeedsHuman("workers mid-subject: confirm, then pass --close-working", working=working)
    for t in targets:
        kind, target = ("workspace", t["workspace"]) if t["workspace"] else ("tab", t["tab"])
        t["error"] = (herdr(kind, "close", target).get("error") or {}).get("message")
    still_tabs, still_ws = tab_ids(), workspace_ids()
    for t in targets:
        if not t["error"] and (t["workspace"] in still_ws if t["workspace"] else t["tab"] in still_tabs):
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

    def where(t):
        return {"workspace": t["workspace"]} if t["workspace"] else {"tab": t["tab"]}

    return {"closed": [{"agent": t["agent"], **where(t)} for t in closed],
            "failed": [{"agent": t["agent"], **where(t), "error": t["error"]} for t in targets if t["error"]],
            "unsubscribed": sorted(subs), "briefs_deleted": str(brief_dir(key))}


# ---------- CLI ----------

def _read_body(path):
    return sys.stdin.read() if path == "-" else Path(path).read_text()


def register(sub):
    env = os.environ.get
    p = db.keyed_parser(sub, "create", "bootstrap a realm from the queen's pane with SIZE workers")
    p.add_argument("--size", type=int, required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--name", help="human name of the new realm, unique; --project stays its key")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: create(
        c, a.key, a.size, a.model, env("HERDR_WORKSPACE_ID"), env("HERDR_PANE_ID"),
        env("HERDR_TAB_ID"), a.name)))

    p = db.keyed_parser(sub, "spawn", "add one worker to the realm")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: spawn(c, a.key)))

    p = db.keyed_parser(sub, "wait-joined", "wait until the named workers joined Agent Mail")
    p.add_argument("names", nargs="+")
    p.add_argument("--timeout", type=int, default=JOIN_TIMEOUT)
    p.set_defaults(fn=db.run_verb(lambda c, a, t: wait_joined(c, a.key, a.names, a.timeout)))

    p = db.keyed_parser(sub, "retire", "scale in a worker whose subjects are all done: unsubscribe, close "
                                       "workspace, retire_agent, delete brief")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=db.run_verb(lambda c, a, t: retire(c, a.key, a.name)))

    p = db.keyed_parser(sub, "move", "move a tab-era worker or scout into its own workspace, conversation kept")
    p.add_argument("--name", required=True, help="worker or scout agent name")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: move(c, a.key, a.name)))

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
        c, a.key, a.model, env("HERDR_PANE_ID"), env("HERDR_TAB_ID"), env("HERDR_WORKSPACE_ID"),
        a.queen, a.force)))

    p = db.keyed_parser(sub, "reinject", "rewrite every worker's brief; the tick delivers it once idle")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: rebrief(c, a.key)))

    p = db.keyed_parser(sub, "stop", "close the realm's worker workspaces, unsubscribe, delete briefs")
    p.add_argument("--close-working", action="store_true", help="also close workers mid-subject")
    p.set_defaults(fn=db.run_verb(lambda c, a, t: stop(c, a.key, env("HERDR_TAB_ID"), a.close_working)))
