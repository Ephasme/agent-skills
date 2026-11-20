"""realm db: the queen's table in SQLite — realms, workers, subjects and their state history.

One database per machine, beside realm's state file: the launchd tick already serves every realm on the
machine from one place. Every row is scoped by realm key.

Subject states: queued → assigned ⇄ blocked → done, plus paused. The queen sets them; `sync` derives only
what mail proves without judgement (see `sync`).
"""

import json
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

from . import mail
from .state import STATE_DIR, STATE_FILE

STATES = ("queued", "assigned", "blocked", "paused", "done")
# A worker holding a subject in one of these states is busy: never idle, never a scale-in candidate.
HELD = ("queued", "assigned", "blocked", "paused")
SCALE_IN_MINUTES = 30

MIGRATIONS = [
    # 1
    """
    CREATE TABLE realms (
        key TEXT PRIMARY KEY,
        queen TEXT NOT NULL,
        queen_pane TEXT,
        created_ts REAL NOT NULL,
        updated_ts REAL NOT NULL
    );
    CREATE TABLE workers (
        realm TEXT NOT NULL REFERENCES realms(key),
        name TEXT NOT NULL,
        pane TEXT,
        tab TEXT,
        brief TEXT,
        created_ts REAL NOT NULL,
        joined_ts REAL,
        last_activity_ts REAL,
        retired_ts REAL,
        PRIMARY KEY (realm, name)
    );
    CREATE TABLE subjects (
        realm TEXT NOT NULL REFERENCES realms(key),
        slug TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        worker TEXT,
        state TEXT NOT NULL CHECK (state IN ('queued','assigned','blocked','paused','done')),
        status TEXT NOT NULL DEFAULT '',
        after_slug TEXT,
        thread_id TEXT,
        last_reply_id INTEGER,
        last_reply_ts REAL,
        created_ts REAL NOT NULL,
        state_ts REAL NOT NULL,
        PRIMARY KEY (realm, slug),
        FOREIGN KEY (realm, worker) REFERENCES workers(realm, name)
    );
    CREATE TABLE subject_events (
        id INTEGER PRIMARY KEY,
        realm TEXT NOT NULL,
        slug TEXT NOT NULL,
        ts REAL NOT NULL,
        state TEXT NOT NULL,
        worker TEXT,
        status TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL CHECK (source IN ('queen','sync')),
        FOREIGN KEY (realm, slug) REFERENCES subjects(realm, slug)
    );
    CREATE INDEX subject_events_by_subject ON subject_events(realm, slug, ts);
    """,
    # 2: what spawning needs without asking again, and briefs waiting for an idle pane.
    """
    ALTER TABLE realms ADD COLUMN model TEXT;
    ALTER TABLE realms ADD COLUMN workspace TEXT;
    ALTER TABLE realms ADD COLUMN cwd TEXT;
    ALTER TABLE workers ADD COLUMN brief_pending INTEGER NOT NULL DEFAULT 0;
    """,
    # 3: scout: channel tracker, proposals awaiting the user, and the user's to-do list (realmlib/scout.py).
    """
    CREATE TABLE scouts (
        realm TEXT PRIMARY KEY REFERENCES realms(key),
        agent TEXT NOT NULL,
        pane TEXT,
        tab TEXT,
        brief TEXT,
        created_ts REAL NOT NULL,
        last_wake_ts REAL,
        scan_start_ts REAL,
        scan_end_ts REAL
    );
    CREATE TABLE scout_cursors (
        realm TEXT NOT NULL REFERENCES realms(key),
        source TEXT NOT NULL,
        scope TEXT NOT NULL,
        cursor TEXT NOT NULL,
        updated_ts REAL NOT NULL,
        PRIMARY KEY (realm, source, scope)
    );
    CREATE TABLE scout_seen (
        realm TEXT NOT NULL REFERENCES realms(key),
        source TEXT NOT NULL,
        msg_id TEXT NOT NULL,
        seen_ts REAL NOT NULL,
        proposal_id INTEGER,
        PRIMARY KEY (realm, source, msg_id)
    );
    CREATE TABLE proposals (
        id INTEGER PRIMARY KEY,
        realm TEXT NOT NULL REFERENCES realms(key),
        source TEXT NOT NULL,
        ref TEXT NOT NULL,
        permalink TEXT,
        excerpt TEXT NOT NULL DEFAULT '',
        action TEXT NOT NULL CHECK (action IN ('task.add','calendar.create','calendar.update','calendar.cancel')),
        payload TEXT NOT NULL,
        confidence TEXT NOT NULL CHECK (confidence IN ('low','med','high')),
        why TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL CHECK (state IN ('proposed','approved','rejected','applied','failed')),
        mail_id INTEGER,
        created_ts REAL NOT NULL,
        decided_ts REAL,
        applied_ref TEXT,
        UNIQUE (realm, source, ref, action)
    );
    CREATE INDEX proposals_by_state ON proposals(realm, state);
    CREATE TABLE tasks (
        id INTEGER PRIMARY KEY,
        realm TEXT NOT NULL REFERENCES realms(key),
        title TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        due TEXT,
        proposal_id INTEGER REFERENCES proposals(id),
        state TEXT NOT NULL CHECK (state IN ('open','done','dropped')),
        created_ts REAL NOT NULL,
        state_ts REAL NOT NULL
    );
    CREATE INDEX tasks_by_state ON tasks(realm, state);
    """,
    # 4: a human name per realm, unique; the Agent Mail key stays the identity and the partition.
    """
    ALTER TABLE realms ADD COLUMN name TEXT;
    CREATE UNIQUE INDEX realms_by_name ON realms(name) WHERE name IS NOT NULL;
    """,
]


def mail_call(tool, args):
    """Call one Agent Mail tool; any failure, transport included, becomes Refused."""
    try:
        return mail.mail_tool(mail.mail_endpoint(), tool, args)
    except (mail.MailToolError, RuntimeError, OSError, ValueError, KeyError) as e:
        raise Refused(f"{tool}: {e}") from e


class Refused(Exception):
    """A request the db rejects as stated; printed as {"error": …}, exit 1."""

    exit_code = 1


class NeedsHuman(Refused):
    """Stopped before acting: a person must choose. Printed as {"needs": …}, exit 2."""

    exit_code = 2

    def __init__(self, message, **detail):
        super().__init__(message)
        self.detail = detail


def db_path():
    return Path(os.environ.get("REALM_DB") or STATE_DIR / "realm.db")


def connect(path=None):
    """Open the db with WAL and foreign keys, migrated to the latest schema version."""
    path = Path(path or db_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    migrate(conn)
    return conn


def migrate(conn):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    for n, sql in enumerate(MIGRATIONS[version:], start=version + 1):
        conn.execute("BEGIN IMMEDIATE")
        try:
            # executescript would commit the open transaction first; run statement by statement instead.
            for stmt in sql.split(";"):
                if stmt.strip():
                    conn.execute(stmt)
            conn.execute(f"PRAGMA user_version={n}")
            conn.execute("COMMIT")
        except BaseException:
            conn.execute("ROLLBACK")
            raise


class tx:
    """BEGIN IMMEDIATE … COMMIT, rolled back on any exception."""

    def __init__(self, conn):
        self.conn = conn

    def __enter__(self):
        self.conn.execute("BEGIN IMMEDIATE")
        return self.conn

    def __exit__(self, exc_type, *_):
        self.conn.execute("ROLLBACK" if exc_type else "COMMIT")


def iso(ts):
    return None if ts is None else time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))


def parse_ts(s):
    """Agent Mail timestamp (`2026-11-20T16:24:53.792753Z`, maybe `+00:00`) → epoch seconds."""
    from datetime import datetime

    return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()


# ---------- operations (pure: conn + now in, dicts out) ----------

def _check_name(conn, key, name):
    if name is None:
        return
    if not name.strip() or name.startswith("/"):
        raise Refused("a realm name is non-empty and does not start with '/' (that is a key)")
    other = conn.execute("SELECT key FROM realms WHERE name=? AND key!=?", (name, key)).fetchone()
    if other:
        raise Refused(f"realm name {name!r} is taken by {other['key']}")


def init_realm(conn, key, queen, pane, now, model=None, workspace=None, cwd=None, name=None):
    """Record a realm (idempotent). Omitted fields keep their stored value."""
    _check_name(conn, key, name)
    with tx(conn):
        conn.execute(
            """INSERT INTO realms (key, queen, queen_pane, model, workspace, cwd, name, created_ts, updated_ts)
                 VALUES (?,?,?,?,?,?,?,?,?)
               ON CONFLICT(key) DO UPDATE SET queen=excluded.queen,
                 queen_pane=COALESCE(excluded.queen_pane, queen_pane), model=COALESCE(excluded.model, model),
                 workspace=COALESCE(excluded.workspace, workspace), cwd=COALESCE(excluded.cwd, cwd),
                 name=COALESCE(excluded.name, name), updated_ts=excluded.updated_ts""",
            (key, queen, pane, model, workspace, cwd, name, now, now),
        )
    return realm_row(conn, key)


def rename_realm(conn, key, name, now):
    realm_row(conn, key)
    _check_name(conn, key, name)
    with tx(conn):
        conn.execute("UPDATE realms SET name=?, updated_ts=? WHERE key=?", (name, now, key))
    return realm_row(conn, key)


def realm_row(conn, key):
    r = conn.execute("SELECT * FROM realms WHERE key=?", (key,)).fetchone()
    if not r:
        raise Refused(f"no realm {key!r} in the db: run `realm init` first")
    return {"key": r["key"], "name": r["name"], "queen": r["queen"], "queen_pane": r["queen_pane"],
            "model": r["model"], "workspace": r["workspace"], "cwd": r["cwd"],
            "created": iso(r["created_ts"]), "updated": iso(r["updated_ts"])}


def label(realm):
    """How a realm is shown to people: its name, else its key."""
    return realm["name"] or realm["key"]


def set_brief_pending(conn, key, name, pending):
    _worker(conn, key, name)
    with tx(conn):
        conn.execute("UPDATE workers SET brief_pending=? WHERE realm=? AND name=?", (int(pending), key, name))


def worker_by_pane(conn, pane):
    """(realm key, worker row) for a live worker on this pane, or None. The pane id is unique per herdr server."""
    r = conn.execute("SELECT * FROM workers WHERE pane=? AND retired_ts IS NULL", (pane,)).fetchone()
    return (r["realm"], r) if r else None


def add_worker(conn, key, name, pane, tab, brief, now):
    realm_row(conn, key)
    with tx(conn):
        conn.execute(
            """INSERT INTO workers (realm, name, pane, tab, brief, created_ts) VALUES (?,?,?,?,?,?)
               ON CONFLICT(realm, name) DO UPDATE SET pane=COALESCE(excluded.pane, pane),
                 tab=COALESCE(excluded.tab, tab), brief=COALESCE(excluded.brief, brief), retired_ts=NULL""",
            (key, name, pane, tab, brief, now),
        )
    return worker_row(conn, key, name, now)


def _worker(conn, key, name):
    w = conn.execute("SELECT * FROM workers WHERE realm=? AND name=?", (key, name)).fetchone()
    if not w:
        raise Refused(f"no worker {name!r} in realm {key!r}")
    return w


def worker_row(conn, key, name, now):
    _worker(conn, key, name)
    return next(w for w in list_workers(conn, key, now, include_retired=True) if w["name"] == name)


def retire_worker(conn, key, name, now, keep_subjects=False):
    """Mark retired in the db only. Closing the tab and Agent Mail retirement stay separate steps.

    keep_subjects: the realm is stopping; its subjects stay with the retired worker, paused, for the record.
    """
    _worker(conn, key, name)
    held = conn.execute(
        f"SELECT slug FROM subjects WHERE realm=? AND worker=? AND state IN ({','.join('?' * len(HELD))})",
        (key, name, *HELD),
    ).fetchall()
    if held and not keep_subjects:
        raise Refused(f"{name} still holds {', '.join(r['slug'] for r in held)}: reassign or close them first")
    with tx(conn):
        conn.execute("UPDATE workers SET retired_ts=? WHERE realm=? AND name=?", (now, key, name))
    return worker_row(conn, key, name, now)


def list_workers(conn, key, now, include_retired=False):
    """Workers with load and idleness, computed by query.

    idle: holds no queued/assigned/blocked/paused subject. idle_since: the latest of its last subject state
    change, its join and its registration. scale_in: idle for SCALE_IN_MINUTES or more.
    """
    rows = conn.execute(
        f"""SELECT w.*,
              (SELECT COUNT(*) FROM subjects s WHERE s.realm=w.realm AND s.worker=w.name
                 AND s.state IN ({','.join('?' * len(HELD))})) AS held,
              (SELECT group_concat(s.slug || ':' || s.state, ' ') FROM subjects s
                 WHERE s.realm=w.realm AND s.worker=w.name AND s.state != 'done') AS open_subjects,
              MAX(w.created_ts, COALESCE(w.joined_ts, 0),
                  COALESCE((SELECT MAX(s.state_ts) FROM subjects s WHERE s.realm=w.realm AND s.worker=w.name), 0))
                AS idle_since
            FROM workers w WHERE w.realm=? {'' if include_retired else 'AND w.retired_ts IS NULL'}
            ORDER BY w.created_ts, w.name""",
        (*HELD, key),
    ).fetchall()
    out = []
    for w in rows:
        idle = w["held"] == 0 and w["retired_ts"] is None
        out.append({
            "name": w["name"], "pane": w["pane"], "tab": w["tab"], "brief": w["brief"],
            "brief_pending": bool(w["brief_pending"]),
            "joined": iso(w["joined_ts"]), "last_activity": iso(w["last_activity_ts"]),
            "retired": iso(w["retired_ts"]), "open_subjects": w["open_subjects"] or "",
            "idle": idle, "idle_since": iso(w["idle_since"]) if idle else None,
            "scale_in": idle and now - w["idle_since"] >= SCALE_IN_MINUTES * 60,
        })
    return out


def _subject(conn, key, slug):
    s = conn.execute("SELECT * FROM subjects WHERE realm=? AND slug=?", (key, slug)).fetchone()
    if not s:
        raise Refused(f"no subject {slug!r} in realm {key!r}")
    return s


def _event(conn, key, slug, now, state, worker, status, source):
    conn.execute(
        "INSERT INTO subject_events (realm, slug, ts, state, worker, status, source) VALUES (?,?,?,?,?,?,?)",
        (key, slug, now, state, worker, status, source),
    )


def _live_worker(conn, key, name):
    if _worker(conn, key, name)["retired_ts"] is not None:
        raise Refused(f"worker {name!r} is retired")


def add_subject(conn, key, slug, title, worker, after, thread_id, status, now):
    """New subject: `assigned` when given a worker and no --after, else `queued`."""
    realm_row(conn, key)
    if worker:
        _live_worker(conn, key, worker)
    if after:
        _subject(conn, key, after)
    if conn.execute("SELECT 1 FROM subjects WHERE realm=? AND slug=?", (key, slug)).fetchone():
        raise Refused(f"subject {slug!r} already exists in realm {key!r}")
    state = "assigned" if worker and not after else "queued"
    with tx(conn):
        conn.execute(
            """INSERT INTO subjects (realm, slug, title, worker, state, status, after_slug, thread_id,
                 created_ts, state_ts) VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (key, slug, title or "", worker, state, status or "", after, thread_id, now, now),
        )
        _event(conn, key, slug, now, state, worker, status or "", "queen")
    return subject_row(conn, key, slug)


def assign_subject(conn, key, slug, worker, thread_id, now):
    s = _subject(conn, key, slug)
    _live_worker(conn, key, worker)
    if s["state"] == "done":
        raise Refused(f"{slug} is done; set its state first to reopen it")
    with tx(conn):
        conn.execute(
            """UPDATE subjects SET worker=?, state='assigned', after_slug=NULL,
                 thread_id=COALESCE(?, thread_id), state_ts=? WHERE realm=? AND slug=?""",
            (worker, thread_id, now, key, slug),
        )
        _event(conn, key, slug, now, "assigned", worker, s["status"], "queen")
    return subject_row(conn, key, slug)


def set_state(conn, key, slug, state, status, thread_id, now, source="queen"):
    if state not in STATES:
        raise Refused(f"state must be one of {', '.join(STATES)}")
    s = _subject(conn, key, slug)
    if state in ("assigned", "blocked") and not s["worker"]:
        raise Refused(f"{slug} has no worker: `realm subject assign` it")
    new_status = s["status"] if status is None else status
    with tx(conn):
        conn.execute(
            """UPDATE subjects SET state=?, status=?, thread_id=COALESCE(?, thread_id),
                 state_ts=CASE WHEN state=? THEN state_ts ELSE ? END WHERE realm=? AND slug=?""",
            (state, new_status, thread_id, state, now, key, slug),
        )
        _event(conn, key, slug, now, state, s["worker"], new_status, source)
    row = subject_row(conn, key, slug)
    if state == "done" and s["state"] != "done":
        from . import hindsight  # best-effort, never raises: a down memory server must not block the queen

        hindsight.on_done(key, row)
    return row


def subject_row(conn, key, slug):
    s = _subject(conn, key, slug)
    w = conn.execute("SELECT pane, tab FROM workers WHERE realm=? AND name=?", (key, s["worker"])).fetchone()
    return {
        "slug": s["slug"], "title": s["title"], "worker": s["worker"],
        "pane": w["pane"] if w else None, "tab": w["tab"] if w else None,
        "state": s["state"], "status": s["status"], "after": s["after_slug"], "thread_id": s["thread_id"],
        "unread_reply": s["last_reply_ts"] is not None and s["last_reply_ts"] > s["state_ts"],
        "last_reply_id": s["last_reply_id"], "last_reply": iso(s["last_reply_ts"]),
        "created": iso(s["created_ts"]), "state_changed": iso(s["state_ts"]),
    }


def list_subjects(conn, key, states=None):
    realm_row(conn, key)
    q = "SELECT slug FROM subjects WHERE realm=?"
    args = [key]
    if states:
        q += f" AND state IN ({','.join('?' * len(states))})"
        args += states
    order = "CASE state " + " ".join(f"WHEN '{s}' THEN {i}" for i, s in enumerate(
        ("blocked", "assigned", "queued", "paused", "done"))) + " END"
    return [subject_row(conn, key, r["slug"]) for r in conn.execute(f"{q} ORDER BY {order}, state_ts", args)]


def show_subject(conn, key, slug):
    out = subject_row(conn, key, slug)
    out["history"] = [
        {"at": iso(e["ts"]), "state": e["state"], "worker": e["worker"], "status": e["status"],
         "source": e["source"]}
        for e in conn.execute(
            "SELECT * FROM subject_events WHERE realm=? AND slug=? ORDER BY ts, id", (key, slug))
    ]
    return out


def render_table(conn, key, include_done, now):
    """The table the queen shows the user: markdown, one row per subject, then idle workers."""
    realm = realm_row(conn, key)
    subjects = [s for s in list_subjects(conn, key) if include_done or s["state"] != "done"]
    title = f"Realm `{realm['name']}` ({key})" if realm["name"] else f"Realm `{key}`"
    lines = [f"{title}, queen {realm['queen']}", ""]
    if subjects:
        lines += ["| slug | worker | pane | state | since | status |", "|---|---|---|---|---|---|"]
        for s in subjects:
            state = s["state"] + (" · reply" if s["unread_reply"] else "")
            if s["state"] == "queued" and s["after"]:
                state += f" (after {s['after']})"
            since = (s["state_changed"] or "")[11:16]
            status = (s["status"] or "").replace("|", "\\|").replace("\n", " ")
            lines.append(f"| {s['slug']} | {s['worker'] or '—'} | {s['pane'] or '—'} | {state} | {since} | {status} |")
    else:
        lines.append("No open subjects.")
    idle = [w for w in list_workers(conn, key, now) if w["idle"]]
    if idle:
        lines += ["", "Idle: " + ", ".join(
            f"{w['name']} ({w['pane'] or '—'}{', scale in' if w['scale_in'] else ''})" for w in idle)]
    return "\n".join(lines)


# ---------- sync from mail ----------

def sync(conn, key, now, call):
    """Apply what mail proves without judgement; `call(tool, args)` is an Agent Mail tool call.

    Automatic:
    - worker joined_ts / last_activity_ts from list_agents (`last_active_ts` past registration = joined);
    - subject thread_id from the queen's `[<slug>]` message in topic <slug>;
    - last_reply_id/ts: newest message in the topic from the subject's worker. The table flags it `· reply`
      until the queen sets a state; done vs blocked is hers;
    - queued (after X) → assigned once X's worker replied after X was assigned, which is when the brief
      tells the worker to start it.
    """
    realm = realm_row(conn, key)
    changes = []
    agents = {a["name"]: a for a in call("list_agents", {"project_key": key})}
    with tx(conn):
        for w in conn.execute("SELECT * FROM workers WHERE realm=?", (key,)).fetchall():
            a = agents.get(w["name"])
            if not a or not a.get("last_active_ts"):
                continue
            last = parse_ts(a["last_active_ts"])
            joined = w["joined_ts"]
            if joined is None and a.get("inception_ts") and last > parse_ts(a["inception_ts"]) + 1:
                joined = last
                changes.append({"worker": w["name"], "joined": iso(last)})
            conn.execute("UPDATE workers SET joined_ts=?, last_activity_ts=? WHERE realm=? AND name=?",
                         (joined, last, key, w["name"]))
    for s in conn.execute("SELECT * FROM subjects WHERE realm=? AND state != 'done'", (key,)).fetchall():
        msgs = call("fetch_topic", {"project_key": key, "topic_name": s["slug"], "include_bodies": False})
        msgs = msgs.get("messages", msgs) if isinstance(msgs, dict) else msgs
        thread = s["thread_id"]
        reply = None
        for m in sorted(msgs, key=lambda m: m["created_ts"]):
            # The subject's thread is rooted at the queen's own `[<slug>]` message.
            if (not thread and m.get("from") == realm["queen"] and not m.get("thread_id")
                    and f"[{s['slug']}]" in m.get("subject", "")):
                thread = str(m["id"])
            # Only a worker message in that thread is a reply; its side mail in the same topic is not.
            if thread and s["worker"] and m.get("from") == s["worker"] and str(m.get("thread_id")) == thread:
                reply = m
        with tx(conn):
            if thread != s["thread_id"]:
                conn.execute("UPDATE subjects SET thread_id=? WHERE realm=? AND slug=?", (thread, key, s["slug"]))
                changes.append({"subject": s["slug"], "thread_id": thread})
            if reply and reply["id"] != s["last_reply_id"]:
                conn.execute("UPDATE subjects SET last_reply_id=?, last_reply_ts=? WHERE realm=? AND slug=?",
                             (reply["id"], parse_ts(reply["created_ts"]), key, s["slug"]))
                changes.append({"subject": s["slug"], "reply": reply["id"]})
    for s in conn.execute(
        """SELECT q.slug, q.worker FROM subjects q JOIN subjects p ON p.realm=q.realm AND p.slug=q.after_slug
           WHERE q.realm=? AND q.state='queued' AND q.worker IS NOT NULL
             AND (p.state='done' OR (p.last_reply_ts IS NOT NULL AND p.last_reply_ts > p.state_ts))""",
        (key,),
    ).fetchall():
        set_state(conn, key, s["slug"], "assigned", None, None, now, source="sync")
        changes.append({"subject": s["slug"], "state": "assigned"})
    return {"changes": changes}


# ---------- CLI ----------

def _emit(obj):
    print(json.dumps(obj, indent=2, ensure_ascii=False))


def resolve_key(project, pane=None, state_file=None, conn=None):
    """The realm key a verb acts on: --project (a key, or a realm name looked up in the db), else the
    project of the caller's pane subscription.

    No default and no guessing: neither given, or an unknown name → Refused. A realm never reads another key's rows.
    """
    if project:
        if project.startswith("/"):
            return project
        r = conn.execute("SELECT key FROM realms WHERE name=?", (project,)).fetchone() if conn else None
        if not r:
            raise Refused(f"no realm named {project!r}: keys start with '/'; `realm realms` lists both")
        return r["key"]
    pane = pane or os.environ.get("HERDR_PANE_ID")
    if pane:
        try:
            subs = json.loads(Path(state_file or STATE_FILE).read_text()).get("subscriptions", {})
        except FileNotFoundError:
            subs = {}
        if pane in subs:
            return subs[pane]["project"]
    raise Refused("no realm key: pass --project <key or name>, or run from a pane subscribed to realm")


def list_realms(conn):
    """Admin listing: each realm's key and name, never its rows."""
    return [{"key": r["key"], "name": r["name"]}
            for r in conn.execute("SELECT key, name FROM realms ORDER BY key")]


def run_verb(fn, keyed=True):
    """argparse handler: resolve the key, open the db, print fn's result as JSON (or text).

    Refused → {"error"} exit 1; NeedsHuman → {"needs", …detail} exit 2: nothing was done past that point.
    """
    def handler(a):
        try:
            with closing(connect()) as conn:
                if keyed:
                    a.key = resolve_key(a.project, conn=conn)
                out = fn(conn, a, time.time())
        except Refused as e:
            if isinstance(e, NeedsHuman):
                _emit({"needs": str(e), **e.detail})
            else:
                _emit({"error": str(e)})
            sys.exit(e.exit_code)
        if isinstance(out, str):
            print(out)
        else:
            _emit(out)
    return handler


def keyed_parser(sub, name, help):
    p = sub.add_parser(name, help=help)
    p.add_argument("--project", help="realm key (/…) or name; default: the project of $HERDR_PANE_ID's subscription")
    return p


def register(sub):
    """Add the db verbs to realm's argparse subparsers. Each one acts on exactly one realm key."""

    p = sub.add_parser("realms", help="db: list realms, key and name (admin; no rows)")
    p.set_defaults(fn=run_verb(lambda c, a, now: list_realms(c), keyed=False))

    p = keyed_parser(sub, "init", "db: record a realm and its queen (idempotent)")
    p.add_argument("--queen", required=True)
    p.add_argument("--pane", help="queen pane id")
    p.add_argument("--name", help="human name, unique across realms")
    p.set_defaults(fn=run_verb(lambda c, a, now: init_realm(c, a.key, a.queen, a.pane, now, name=a.name)))

    p = keyed_parser(sub, "rename", "db: set the realm's human name")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=run_verb(lambda c, a, now: rename_realm(c, a.key, a.name, now)))

    w = sub.add_parser("worker", help="db: workers").add_subparsers(dest="wcmd", required=True)
    p = keyed_parser(w, "add", "record or update a worker (clears retired)")
    p.add_argument("--name", required=True)
    p.add_argument("--pane")
    p.add_argument("--tab")
    p.add_argument("--brief")
    p.set_defaults(fn=run_verb(lambda c, a, now: add_worker(c, a.key, a.name, a.pane, a.tab, a.brief, now)))
    p = keyed_parser(w, "list", "workers with idle and scale_in flags")
    p.add_argument("--all", action="store_true", help="include retired")
    p.add_argument("--idle", action="store_true", help="idle workers only")
    p.add_argument("--scale-in", action="store_true", help="scale-in candidates only")
    p.set_defaults(fn=run_verb(lambda c, a, now: [
        x for x in list_workers(c, a.key, now, a.all)
        if (not a.idle or x["idle"]) and (not a.scale_in or x["scale_in"])
    ]))
    p = keyed_parser(w, "retire", "mark a worker retired in the db (refused while it holds a subject)")
    p.add_argument("--name", required=True)
    p.set_defaults(fn=run_verb(lambda c, a, now: retire_worker(c, a.key, a.name, now)))

    s = sub.add_parser("subject", help="db: subjects").add_subparsers(dest="scmd", required=True)
    p = keyed_parser(s, "add", "new subject: assigned with --worker, queued with --after or no worker")
    p.add_argument("--slug", required=True)
    p.add_argument("--title", default="")
    p.add_argument("--worker")
    p.add_argument("--after", help="slug this one waits for")
    p.add_argument("--thread-id")
    p.add_argument("--status")
    p.set_defaults(fn=run_verb(lambda c, a, now: add_subject(
        c, a.key, a.slug, a.title, a.worker, a.after, a.thread_id, a.status, now)))
    p = keyed_parser(s, "assign", "give a subject to a worker: state assigned")
    p.add_argument("--slug", required=True)
    p.add_argument("--worker", required=True)
    p.add_argument("--thread-id")
    p.set_defaults(fn=run_verb(lambda c, a, now: assign_subject(c, a.key, a.slug, a.worker, a.thread_id, now)))
    p = keyed_parser(s, "set-state", "queen sets state and/or status text")
    p.add_argument("--slug", required=True)
    p.add_argument("--state", required=True, choices=STATES)
    p.add_argument("--status", help="short status text; omitted keeps the current one")
    p.add_argument("--thread-id")
    p.set_defaults(fn=run_verb(lambda c, a, now: set_state(
        c, a.key, a.slug, a.state, a.status, a.thread_id, now)))
    p = keyed_parser(s, "list", "subjects, open first")
    p.add_argument("--state", action="append", choices=STATES)
    p.set_defaults(fn=run_verb(lambda c, a, now: list_subjects(c, a.key, a.state)))
    p = keyed_parser(s, "show", "one subject with its state history")
    p.add_argument("--slug", required=True)
    p.set_defaults(fn=run_verb(lambda c, a, now: show_subject(c, a.key, a.slug)))

    p = keyed_parser(sub, "table", "db: the subject table as markdown (or --json)")
    p.add_argument("--all", action="store_true", help="include done subjects")
    p.add_argument("--json", action="store_true")
    p.set_defaults(fn=run_verb(lambda c, a, now: {
        "realm": realm_row(c, a.key),
        "subjects": [x for x in list_subjects(c, a.key) if a.all or x["state"] != "done"],
        "workers": list_workers(c, a.key, now),
    } if a.json else render_table(c, a.key, a.all, now)))

    p = keyed_parser(sub, "sync", "db: apply what Agent Mail proves (joins, threads, replies, queued→assigned)")
    p.set_defaults(fn=run_verb(lambda c, a, now: sync(c, a.key, now, mail_call)))
