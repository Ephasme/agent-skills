"""Scout: one optional agent per realm that reads the user's channels and proposes calendar and to-do actions.

The scout reads; it never writes to a channel, a calendar or the to-do list. What it finds becomes a row in
`proposals`; the queen shows them to the user, who approves or rejects each one. An approved `task.add` lands in
`tasks` through `proposal apply`; an approved `calendar.*` goes to a worker as a normal subject.

Tracker: `scout_cursors` holds one high-water mark per (source, scope), `scout_seen` the message ids already
judged. A cursor advances only through `ack`, after the scout has judged the batch, so an interrupted scan
re-reads it and `seen` drops what was already judged.

WhatsApp and iMessage are fetched here, over their MCP HTTP endpoints. Slack and Gmail need the OAuth tokens
omp holds, so the scout agent fetches them itself and reports through the same `cursor`/`ack` verbs.

The allowlists, the ntfy endpoint and its token command live in CONFIG, outside the repository: they name
private contacts.
"""

import json
import os
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from . import db
from .db import Refused, tx
from .state import HOME, locked_state, log

CONFIG = Path(os.environ.get("REALM_SCOUT_CONFIG") or HOME / ".config/realm/scout.json")
SECRETS = Path(os.environ.get("REALM_SCOUT_SECRETS") or HOME / "code/perso/agent-skills/mcp/secrets.sops.yaml")
MCP_CONFIG = HOME / ".omp/agent/mcp.json"
SCAN_TEXT = "scan"
SCOUT_LABEL = "🔭 scout"
BRIEF_TEMPLATE = Path(__file__).resolve().parent.parent / "scout-brief.md"
TZ = ZoneInfo("Europe/Paris")
DAY_HOURS = (8, 22)  # [08:00, 22:00) local: scan every DAY_INTERVAL, otherwise every NIGHT_INTERVAL
DAY_INTERVAL = 3600
NIGHT_INTERVAL = 3 * 3600
BACKFILL_SECONDS = 30 * 86400
EXCERPT_MAX = 200
TEXT_MAX = 2000
FETCH_LIMIT = 300
SOURCES = ("slack", "gmail-work", "gmail-perso", "whatsapp", "imessage")
ACTIONS = ("task.add", "calendar.create", "calendar.update", "calendar.cancel")
CONFIDENCE = ("low", "med", "high")
DECIDED = ("approved", "rejected")


# ---------- schedule (the daemon's hook) ----------

def interval(now):
    """Seconds between scans at `now`: hourly by day, every three hours by night, Europe/Paris."""
    hour = datetime.fromtimestamp(now, TZ).hour
    return DAY_INTERVAL if DAY_HOURS[0] <= hour < DAY_HOURS[1] else NIGHT_INTERVAL


def scan_due(conn, key, now):
    """True when the realm's scout has never finished a scan, or its last one is older than interval(now).

    The daemon calls this for a scout subscription only; a realm without a scouts row has never scanned.
    """
    r = conn.execute("SELECT scan_end_ts FROM scouts WHERE realm=?", (key,)).fetchone()
    last = r["scan_end_ts"] if r else None
    return last is None or now - last >= interval(now)


# ---------- tracker ----------

def _scout(conn, key):
    r = conn.execute("SELECT * FROM scouts WHERE realm=?", (key,)).fetchone()
    if not r:
        raise Refused(f"realm {key!r} has no scout: run `realm scout spawn` first")
    return r


def _source(source):
    if source not in SOURCES:
        raise Refused(f"unknown source {source!r}: one of {', '.join(SOURCES)}")
    return source


def cursors(conn, key, source, now):
    """{scope: cursor} for a source; `first` is true before its first ack (then a scan backfills a month).

    The default for an unseen scope is now − BACKFILL_SECONDS, as epoch seconds; each source's own cursor
    format is the agent's or the fetcher's business.
    """
    _source(source)
    rows = conn.execute("SELECT scope, cursor FROM scout_cursors WHERE realm=? AND source=?",
                        (key, source)).fetchall()
    return {"source": source, "first": not rows, "default": now - BACKFILL_SECONDS,
            "cursors": {r["scope"]: r["cursor"] for r in rows}}


def unseen(conn, key, source, ids):
    """The ids not judged yet, input order kept."""
    seen = {r["msg_id"] for r in conn.execute(
        f"SELECT msg_id FROM scout_seen WHERE realm=? AND source=? AND msg_id IN ({','.join('?' * len(ids))})",
        (key, source, *ids))} if ids else set()
    return [i for i in ids if i not in seen]


def ack(conn, key, batch, now):
    """Record a judged batch: its ids as seen, then its cursors. One transaction: both or neither.

    batch: {"source", "cursors": {scope: cursor}, "ids": [msg_id, ...]}; extra keys (the messages) are ignored.
    A cursor never moves backwards when it is numeric.
    """
    source = _source(batch.get("source"))
    ids = [str(i) for i in batch.get("ids") or []]
    curs = {str(k): str(v) for k, v in (batch.get("cursors") or {}).items()}
    with tx(conn):
        conn.executemany(
            "INSERT OR IGNORE INTO scout_seen (realm, source, msg_id, seen_ts) VALUES (?,?,?,?)",
            [(key, source, i, now) for i in ids])
        for scope, cur in curs.items():
            old = conn.execute("SELECT cursor FROM scout_cursors WHERE realm=? AND source=? AND scope=?",
                               (key, source, scope)).fetchone()
            if old and _num(old["cursor"]) is not None and _num(cur) is not None and _num(cur) < _num(old["cursor"]):
                continue
            conn.execute(
                """INSERT INTO scout_cursors (realm, source, scope, cursor, updated_ts) VALUES (?,?,?,?,?)
                   ON CONFLICT(realm, source, scope) DO UPDATE SET cursor=excluded.cursor,
                     updated_ts=excluded.updated_ts""",
                (key, source, scope, cur, now))
    return {"source": source, "seen": len(ids), "cursors": curs}


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ---------- scans ----------

def scan_start(conn, key, now):
    _scout(conn, key)
    with tx(conn):
        conn.execute("UPDATE scouts SET scan_start_ts=? WHERE realm=?", (now, key))
    return {"scan_start": db.iso(now)}


def mailed(conn, key, ids, mail_id):
    """Record the Agent Mail message that carried these proposals to the queen."""
    rows = list_proposals(conn, key, ids=ids)
    missing = sorted(set(ids) - {p["id"] for p in rows})
    if missing:
        raise Refused(f"no such proposals in {key}: {missing}")
    with tx(conn):
        conn.execute(f"UPDATE proposals SET mail_id=? WHERE realm=? AND id IN ({','.join('?' * len(ids))})",
                     (mail_id, key, *ids))
    return {"mail_id": mail_id, "proposals": ids}


def scan_end(conn, key, now, push=None):
    """Close a scan: refuse while a proposal made since scan start was never mailed, push the titles of this
    scan's proposals to the phone, record the scan's end (which the schedule reads)."""
    s = _scout(conn, key)
    new = conn.execute("SELECT id, action, payload, mail_id FROM proposals WHERE realm=? AND created_ts>=? ORDER BY id",
                       (key, s["scan_start_ts"] or 0)).fetchall()
    unmailed = [r["id"] for r in new if r["mail_id"] is None]
    if unmailed:
        raise Refused(f"proposals never mailed to the queen: {unmailed}; mail them, then `proposal mailed`")
    with tx(conn):
        conn.execute("UPDATE scouts SET scan_end_ts=? WHERE realm=?", (now, key))
    pushed = None
    if new:
        lines = [f"P{r['id']} {title(r['action'], json.loads(r['payload']))}" for r in new]
        pushed = (push or notify)(f"scout: {len(new)} proposal(s)", "\n".join(lines))
    return {"scan_end": db.iso(now), "proposals": [r["id"] for r in new], "pushed": pushed}


# ---------- proposals ----------

def title(action, payload):
    return f"{action} {payload.get('title') or payload.get('event_id') or ''}".strip()


def propose(conn, key, items, now):
    """Record proposals; a repeat of (source, ref, action) is returned as a duplicate, not stored again."""
    _scout(conn, key)
    out = []
    for p in items:
        source, action = _source(p.get("source")), p.get("action")
        if action not in ACTIONS:
            raise Refused(f"action {action!r}: one of {', '.join(ACTIONS)}")
        if p.get("confidence") not in CONFIDENCE:
            raise Refused(f"confidence {p.get('confidence')!r}: one of {', '.join(CONFIDENCE)}")
        payload = p.get("payload") or {}
        if not isinstance(payload, dict) or not (payload.get("title") or payload.get("event_id")):
            raise Refused(f"{action} payload needs a title (or event_id): {payload!r}")
        if not p.get("ref"):
            raise Refused("each proposal needs ref: the message id it comes from")
        dup = conn.execute("SELECT id FROM proposals WHERE realm=? AND source=? AND ref=? AND action=?",
                           (key, source, str(p["ref"]), action)).fetchone()
        if dup:
            out.append({"id": dup["id"], "duplicate": True})
            continue
        with tx(conn):
            cur = conn.execute(
                """INSERT INTO proposals (realm, source, ref, permalink, excerpt, action, payload, confidence, why,
                     state, created_ts) VALUES (?,?,?,?,?,?,?,?,?, 'proposed', ?)""",
                (key, source, str(p["ref"]), p.get("permalink"), (p.get("excerpt") or "")[:EXCERPT_MAX], action,
                 json.dumps(payload, ensure_ascii=False), p["confidence"], p.get("why") or "", now))
            conn.execute("UPDATE scout_seen SET proposal_id=? WHERE realm=? AND source=? AND msg_id=?",
                         (cur.lastrowid, key, source, str(p["ref"])))
        out.append({"id": cur.lastrowid, "duplicate": False})
    return out


def _proposal(r):
    return {"id": r["id"], "source": r["source"], "ref": r["ref"], "permalink": r["permalink"],
            "excerpt": r["excerpt"], "action": r["action"], "payload": json.loads(r["payload"]),
            "confidence": r["confidence"], "why": r["why"], "state": r["state"], "mail_id": r["mail_id"],
            "created": db.iso(r["created_ts"]), "decided": db.iso(r["decided_ts"]), "applied_ref": r["applied_ref"]}


def list_proposals(conn, key, states=None, ids=None):
    q, args = "SELECT * FROM proposals WHERE realm=?", [key]
    if states:
        q += f" AND state IN ({','.join('?' * len(states))})"
        args += states
    if ids:
        q += f" AND id IN ({','.join('?' * len(ids))})"
        args += ids
    return [_proposal(r) for r in conn.execute(q + " ORDER BY id", args)]


def render(proposals):
    """The markdown the scout mails to the queen and the queen shows the user: one block per proposal."""
    lines = []
    for p in proposals:
        pl = p["payload"]
        when = " → ".join(x for x in (pl.get("start"), pl.get("end")) if x)
        extra = ", ".join(f"{k}: {pl[k]}" for k in ("calendar", "due", "attendees", "event_id") if pl.get(k))
        head = f"**P{p['id']}** `{p['action']}` {pl.get('title', '')}" + (f" · {when}" if when else "")
        lines += [head,
                  f"- {p['source']} · {p['confidence']} · {p['why']}" + (f" · {extra}" if extra else ""),
                  f"- > {p['excerpt']}" + (f" ([link]({p['permalink']}))" if p["permalink"] else ""), ""]
    return "\n".join(lines).rstrip() or "no proposals"


def decide(conn, key, approve, reject, now):
    """The user's verdict, per item. Only a `proposed` item can be decided."""
    both = set(approve) & set(reject)
    if both:
        raise Refused(f"approved and rejected at once: {sorted(both)}")
    todo = [(i, "approved") for i in approve] + [(i, "rejected") for i in reject]
    rows = {r["id"]: r for r in conn.execute(
        f"SELECT id, state FROM proposals WHERE realm=? AND id IN ({','.join('?' * len(todo))})",
        (key, *[i for i, _ in todo]))} if todo else {}
    bad = [i for i, _ in todo if i not in rows or rows[i]["state"] != "proposed"]
    if bad:
        raise Refused(f"not proposed in {key}: {bad}")
    with tx(conn):
        for i, state in todo:
            conn.execute("UPDATE proposals SET state=?, decided_ts=? WHERE id=?", (state, now, i))
    return list_proposals(conn, key, ids=[i for i, _ in todo])


def apply_tasks(conn, key, ids, now):
    """Write approved task.add proposals into tasks. Calendar items go through a worker, then `applied`."""
    rows = list_proposals(conn, key, ids=ids)
    found = {p["id"] for p in rows}
    bad = [i for i in ids if i not in found] + [p["id"] for p in rows
                                                 if p["state"] != "approved" or p["action"] != "task.add"]
    if bad:
        raise Refused(f"only approved task.add proposals apply here: {bad}")
    out = []
    with tx(conn):
        for p in rows:
            pl = p["payload"]
            cur = conn.execute(
                """INSERT INTO tasks (realm, title, notes, due, proposal_id, state, created_ts, state_ts)
                   VALUES (?,?,?,?,?, 'open', ?, ?)""",
                (key, pl["title"], pl.get("notes") or "", pl.get("due"), p["id"], now, now))
            conn.execute("UPDATE proposals SET state='applied', applied_ref=? WHERE id=?",
                         (f"task:{cur.lastrowid}", p["id"]))
            out.append({"proposal": p["id"], "task": cur.lastrowid})
    return out


def applied(conn, key, pid, ref, failed, now):
    """A worker reports an approved calendar proposal executed (event id) or failed (reason)."""
    p = list_proposals(conn, key, ids=[pid])
    if not p or p[0]["state"] != "approved":
        raise Refused(f"P{pid} is not an approved proposal in {key}")
    with tx(conn):
        conn.execute("UPDATE proposals SET state=?, applied_ref=? WHERE id=?",
                     ("failed" if failed else "applied", ref, pid))
    return list_proposals(conn, key, ids=[pid])[0]


# ---------- tasks ----------

def _task(r):
    return {"id": r["id"], "title": r["title"], "notes": r["notes"], "due": r["due"],
            "proposal": r["proposal_id"], "state": r["state"], "created": db.iso(r["created_ts"]),
            "changed": db.iso(r["state_ts"])}


def add_task(conn, key, ttl, notes, due, now):
    db.realm_row(conn, key)
    with tx(conn):
        cur = conn.execute(
            "INSERT INTO tasks (realm, title, notes, due, state, created_ts, state_ts) VALUES (?,?,?,?, 'open', ?, ?)",
            (key, ttl, notes or "", due, now, now))
    return _task(conn.execute("SELECT * FROM tasks WHERE id=?", (cur.lastrowid,)).fetchone())


def list_tasks(conn, key, states):
    return [_task(r) for r in conn.execute(
        f"SELECT * FROM tasks WHERE realm=? AND state IN ({','.join('?' * len(states))}) ORDER BY due IS NULL, due, id",
        (key, *states))]


def set_task(conn, key, tid, state, now):
    if not conn.execute("SELECT 1 FROM tasks WHERE realm=? AND id=?", (key, tid)).fetchone():
        raise Refused(f"no task {tid} in {key}")
    with tx(conn):
        conn.execute("UPDATE tasks SET state=?, state_ts=? WHERE id=?", (state, now, tid))
    return _task(conn.execute("SELECT * FROM tasks WHERE id=?", (tid,)).fetchone())


# ---------- config, MCP and ntfy ----------

def config():
    try:
        return json.loads(CONFIG.read_text())
    except FileNotFoundError:
        return {}


def _shell_value(value):
    """`!cmd` → the command's stdout, the way omp resolves mcp.json headers; anything else as is."""
    if not value.startswith("!"):
        return value
    p = subprocess.run(["/bin/sh", "-c", value[1:]], capture_output=True, text=True, timeout=30)
    if p.returncode != 0 or not p.stdout.strip():
        raise RuntimeError(f"secret command failed: {p.stderr.strip()[:200]}")
    return p.stdout.strip()


def _sse_json(raw):
    text = raw.decode()
    if text.lstrip().startswith("event:") or text.lstrip().startswith("data:"):
        text = [ln[5:] for ln in text.splitlines() if ln.startswith("data:")][-1]
    return json.loads(text)


class Mcp:
    """One MCP HTTP server from ~/.omp/agent/mcp.json: initialize once, then tools/call. Read-only use."""

    def __init__(self, server):
        cfg = json.loads(MCP_CONFIG.read_text())
        srv = (cfg.get("mcpServers") or cfg.get("servers"))[server]
        self.url = srv["url"]
        self.headers = {n: _shell_value(v) for n, v in (srv.get("headers") or {}).items()}
        self.headers.update({"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                             "User-Agent": "realm/1"})
        hdrs, _ = self._post({"jsonrpc": "2.0", "id": 0, "method": "initialize", "params": {
            "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "realm-scout", "version": "1"}}})
        if hdrs.get("mcp-session-id"):
            self.headers["mcp-session-id"] = hdrs["mcp-session-id"]
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def _post(self, body):
        req = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=self.headers)
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return r.headers, (_sse_json(raw) if raw.strip() else None)

    def call(self, tool, args):
        """The tool's text contents, each parsed as JSON."""
        _, reply = self._post({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                               "params": {"name": tool, "arguments": args}})
        if "error" in reply:
            raise RuntimeError(f"{tool}: {reply['error']}")
        res = reply["result"]
        if res.get("isError"):
            raise RuntimeError(f"{tool}: {res['content'][0]['text'][:300]}")
        return [json.loads(c["text"]) for c in res["content"]]


def notify(ttl, message):
    """One ntfy push (topic and endpoint from CONFIG). Returns 'sent', 'off' (not configured) or the error."""
    n = config().get("ntfy") or {}
    if not n.get("url"):
        return "off"
    body = json.dumps({"topic": n.get("topic", "answers"), "title": ttl, "message": message,
                       "tags": ["telescope"], "priority": 3}).encode()
    headers = {"Content-Type": "application/json"}
    if n.get("token"):
        headers["Authorization"] = f"Bearer {_shell_value(n['token'])}"
    try:
        with urllib.request.urlopen(urllib.request.Request(n["url"].rstrip("/") + "/", data=body, headers=headers),
                                    timeout=20) as r:
            return "sent" if r.status == 200 else f"http {r.status}"
    except Exception as e:  # noqa: BLE001 - a failed push never fails the scan
        log(f"scout: ntfy push failed: {e}")
        return f"failed: {e}"


# ---------- fetchers (sources reachable without omp) ----------

def _clip(s):
    s = s or ""
    return s if len(s) <= TEXT_MAX else s[:TEXT_MAX] + "…"


class Skipped(Refused):
    """A source that cannot be read now (missing key, auth refused): reported, never a crash."""


def secret(name):
    """One key from the sops secrets file, decrypted at call time. Missing or undecryptable → Skipped."""
    p = subprocess.run(["sops", "-d", "--extract", f'["{name}"]', str(SECRETS)], capture_output=True, text=True,
                       timeout=30)
    if p.returncode != 0 or not p.stdout.strip():
        raise Skipped(f"secret {name} not available in {SECRETS}")
    return p.stdout.strip()


def _http_json(url, headers=None, data=None):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": "realm/1", **(headers or {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


class SlackApi:
    """Slack Web API with a read-only user token. Only search.messages is used."""

    def __init__(self, token=None):
        self.token = token or secret("SCOUT_SLACK_USER_TOKEN")

    def get(self, method, **params):
        d = _http_json(f"https://slack.com/api/{method}?{urllib.parse.urlencode(params)}",
                       {"Authorization": f"Bearer {self.token}"})
        if not d.get("ok"):
            err = d.get("error", "unknown")
            if err in ("invalid_auth", "not_authed", "token_revoked", "missing_scope", "account_inactive"):
                raise Skipped(f"slack: {err}")
            raise RuntimeError(f"slack {method}: {err}")
        return d


def fetch_slack(conn, key, now, limit=None, api=None):
    """Every message the user can read since the cursor, via search (the user's own index), oldest first.

    search's `after:` filter is day-granular and exclusive of that day, so the query starts the day before the
    cursor and drops older messages here; `seen` absorbs the overlap.
    """
    state = cursors(conn, key, "slack", now)
    after = float(state["cursors"].get("all", state["default"]))
    api = api or SlackApi()
    day = datetime.fromtimestamp(after - 86400, timezone.utc).strftime("%Y-%m-%d")
    msgs, page, top = [], 1, after
    while True:
        d = api.get("search.messages", query=f"after:{day}", sort="timestamp", sort_dir="asc", count=100, page=page)
        res = d.get("messages") or {}
        for m in res.get("matches") or []:
            ts = float(m["ts"])
            if ts < after or m.get("subtype") == "bot_message" or m.get("bot_id"):
                continue
            ch = m.get("channel") or {}
            top = max(top, ts)
            msgs.append({"id": f"{ch.get('id')}:{m['ts']}", "scope": "all", "epoch": ts, "chat": ch.get("name"),
                         "ts": db.iso(ts), "from_me": False, "sender": m.get("username") or m.get("user"),
                         "kind": "text", "text": _clip(m.get("text")), "permalink": m.get("permalink")})
        pages = (res.get("paging") or {}).get("pages", 1)
        if page >= pages or (limit and len(msgs) > limit):
            more_pages = page < pages
            break
        page += 1
    out = _batch(conn, key, "slack", msgs, {"all": str(top)}, state["first"], limit)
    out["more"] = out["more"] or more_pages
    return out


class GmailApi:
    """Gmail REST with a gmail.readonly refresh token; one account."""

    def __init__(self, account, token=None):
        if token is None:
            body = urllib.parse.urlencode({
                "client_id": secret("SCOUT_GMAIL_CLIENT_ID"), "client_secret": secret("SCOUT_GMAIL_CLIENT_SECRET"),
                "refresh_token": secret(f"SCOUT_GMAIL_{account.upper()}_REFRESH_TOKEN"),
                "grant_type": "refresh_token"}).encode()
            try:
                token = _http_json("https://oauth2.googleapis.com/token", data=body)["access_token"]
            except urllib.error.HTTPError as e:
                raise Skipped(f"gmail-{account}: token refresh refused ({e.code})") from e
        self.token = token

    def get(self, path, **params):
        return _http_json(f"https://gmail.googleapis.com/gmail/v1/users/me/{path}?{urllib.parse.urlencode(params)}",
                          {"Authorization": f"Bearer {self.token}"})


def _gmail_text(payload):
    """The first text/plain part, decoded; None when the message has none."""
    import base64

    stack = [payload]
    while stack:
        part = stack.pop(0)
        if part.get("mimeType") == "text/plain" and (part.get("body") or {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"] + "==").decode("utf-8", "replace")
        stack += part.get("parts") or []
    return None


def fetch_gmail(conn, key, now, account, limit=None, api=None):
    """New mail since the cursor (Promotions and Social skipped), oldest first; nothing is marked read."""
    source = f"gmail-{account}"
    state = cursors(conn, key, source, now)
    after = float(state["cursors"].get("all", state["default"]))
    api = api or GmailApi(account)
    ids, page = [], None
    while True:
        params = {"q": f"after:{int(after)} -category:promotions -category:social", "maxResults": 500}
        if page:
            params["pageToken"] = page
        d = api.get("messages", **params)
        ids += [m["id"] for m in d.get("messages") or []]
        page = d.get("nextPageToken")
        if not page:
            break
    todo = unseen(conn, key, source, ids)
    msgs, top = [], after
    # Gmail lists newest first: read the oldest `limit` (+1 to know there is more), the rest comes next fetch.
    for mid in list(reversed(todo))[: (limit + 1) if limit else None]:
        m = api.get(f"messages/{mid}", format="full")
        ts = int(m["internalDate"]) / 1000
        top = max(top, ts)
        hdr = {h["name"].lower(): h["value"] for h in (m.get("payload") or {}).get("headers") or []}
        body = _gmail_text(m.get("payload") or {}) or m.get("snippet")
        msgs.append({"id": mid, "scope": "all", "epoch": ts, "chat": hdr.get("subject"), "ts": db.iso(ts),
                     "from_me": "SENT" in (m.get("labelIds") or []), "sender": hdr.get("from"), "kind": "mail",
                     "text": _clip(body), "permalink": f"https://mail.google.com/mail/u/0/#all/{mid}"})
    return _batch(conn, key, source, msgs, {"all": str(top)}, state["first"], limit)


FETCHERS = {
    "whatsapp": lambda c, k, n, lim: fetch_whatsapp(c, k, n, lim),
    "imessage": lambda c, k, n, lim: fetch_imessage(c, k, n, lim),
    "slack": lambda c, k, n, lim: fetch_slack(c, k, n, lim),
    "gmail-work": lambda c, k, n, lim: fetch_gmail(c, k, n, "work", lim),
    "gmail-perso": lambda c, k, n, lim: fetch_gmail(c, k, n, "perso", lim),
}


def fetch(conn, key, source, now, limit):
    """One source's next batch; an unreadable source answers {source, skipped: reason} instead of failing."""
    try:
        return FETCHERS[source](conn, key, now, limit)
    except Skipped as e:
        return {"source": source, "skipped": str(e)}


def fetch_whatsapp(conn, key, now, limit=None, client=None):
    """New messages in the allowlisted WhatsApp chats since their cursors; nothing is marked read."""
    chats = (config().get("whatsapp") or {}).get("chats") or {}
    if not chats:
        raise Skipped(f"no WhatsApp chats allowlisted in {CONFIG}")
    state = cursors(conn, key, "whatsapp", now)
    client = client or Mcp("whatsapp")
    msgs, curs = [], {}
    for jid, label in chats.items():
        after = int(float(state["cursors"].get(jid, state["default"])))
        top, page = after, None
        while True:
            args = {"chat": jid, "after": after, "asc": True, "limit": 200}
            if page:
                args["cursor"] = page
            data = client.call("whatsapp_messages_list", args)[0]
            for m in data.get("items") or []:
                top = max(top, int(m["ts"]))
                msgs.append({"id": m["id"], "scope": jid, "epoch": float(m["ts"]), "chat": label, "ts": db.iso(m["ts"]),
                             "from_me": m["from_me"], "sender": (m.get("sender") or {}).get("name"),
                             "kind": m.get("kind"), "text": _clip(m.get("text") or m.get("transcript")),
                             "permalink": None})
            page = data.get("next_cursor")
            if not page:
                break
        curs[jid] = str(top)
    return _batch(conn, key, "whatsapp", msgs, curs, state["first"], limit)


def fetch_imessage(conn, key, now, limit=None, client=None):
    """New messages in the allowlisted iMessage chats since their cursors; nothing is marked read."""
    chats = (config().get("imessage") or {}).get("chats") or {}
    if not chats:
        raise Skipped(f"no iMessage chats allowlisted in {CONFIG}")
    state = cursors(conn, key, "imessage", now)
    client = client or Mcp("imessage")
    msgs, curs = [], {}
    for chat_id, label in chats.items():
        after = float(state["cursors"].get(chat_id, state["default"]))
        start = datetime.fromtimestamp(after, timezone.utc).isoformat().replace("+00:00", "Z")
        rows = client.call("imessage_history", {"chat_id": int(chat_id), "start": start, "limit": 1000})
        top = after
        for m in rows:
            if not isinstance(m, dict) or "guid" not in m:
                continue
            ts = db.parse_ts(m["created_at"])
            top = max(top, ts)
            msgs.append({"id": m["guid"], "scope": chat_id, "epoch": ts, "chat": label, "ts": m["created_at"],
                         "from_me": m.get("is_from_me", False), "sender": label if not m.get("is_from_me") else "me",
                         "kind": "text", "text": _clip(m.get("text")), "permalink": None})
        curs[chat_id] = str(top)
    return _batch(conn, key, "imessage", msgs, curs, state["first"], limit)


def _batch(conn, key, source, msgs, curs, first, limit=None):
    """The fetch result, already in `ack`'s shape: judge `messages`, then pipe the whole thing to `ack`.

    limit keeps the oldest `limit` unjudged messages; each chat's cursor then stops at the newest message
    returned for it (the fetch is inclusive there, and `seen` drops the repeat), so the rest comes next time.
    `more` says so.
    """
    fresh = set(unseen(conn, key, source, [m["id"] for m in msgs]))
    msgs = sorted((m for m in msgs if m["id"] in fresh), key=lambda m: m["epoch"])
    more = bool(limit) and len(msgs) > limit
    if more:
        msgs = msgs[:limit]
        curs = {}
        for m in msgs:
            curs[m["scope"]] = str(max(float(curs.get(m["scope"], 0)), m["epoch"]))
    return {"source": source, "first": first, "more": more, "cursors": curs, "ids": [m["id"] for m in msgs],
            "messages": msgs}


# ---------- launch ----------

def fill(template, **values):
    """Replace {NAME} placeholders only: the brief also holds JSON braces that str.format would choke on."""
    for k, v in values.items():
        template = template.replace("{" + k + "}", v)
    return template


def spawn(conn, key, now):
    """Register the scout, write its brief, open its tab, start omp on it, subscribe it as a scout, record it."""
    from . import swarm

    r = swarm._spawnable(conn, key)
    old = conn.execute("SELECT * FROM scouts WHERE realm=?", (key,)).fetchone()
    if old and old["pane"] and swarm.pane(old["pane"]):
        raise Refused(f"realm {key} already has a live scout {old['agent']} in {old['pane']}")
    name = swarm.call("create_agent_identity", {
        "project_key": key, "program": swarm.PROGRAM, "model": r["model"],
        "task_description": f"Swarm scout, queen {r['queen']}"})["name"]
    brief = swarm.brief_dir(key) / f"{swarm.kebab(name)}.md"
    brief.parent.mkdir(parents=True, exist_ok=True)
    brief.write_text(fill(BRIEF_TEMPLATE.read_text(), S=name, KEY=key, QUEEN=r["queen"], LABEL=SCOUT_LABEL))
    res = swarm._ok(swarm.herdr("tab", "create", "--workspace", r["workspace"], "--cwd", r["cwd"] or os.getcwd(),
                                "--label", SCOUT_LABEL, "--no-focus"), "tab create")
    pane_id, tab_id = res["root_pane"]["pane_id"], res["tab"]["tab_id"]
    swarm._ok(swarm.herdr("pane", "run", pane_id, f"{swarm.PROGRAM} @{brief}"), "pane run")
    with locked_state() as s:
        s["subscriptions"][pane_id] = {
            "agent": name, "project": key, "mode": "prompt", "cursor": None, "pending": [],
            "last_wake": 0, "last_unread": 0, "kind": "scout", "wake_text": SCAN_TEXT, "last_scan_wake": now}
    with tx(conn):
        conn.execute(
            """INSERT INTO scouts (realm, agent, pane, tab, brief, created_ts) VALUES (?,?,?,?,?,?)
               ON CONFLICT(realm) DO UPDATE SET agent=excluded.agent, pane=excluded.pane, tab=excluded.tab,
                 brief=excluded.brief""",
            (key, name, pane_id, tab_id, str(brief), now))
    log(f"spawned scout {name} in {pane_id} for {key}")
    return {"name": name, "pane": pane_id, "tab": tab_id, "brief": str(brief)}


def show(conn, key, now):
    s = _scout(conn, key)
    return {"agent": s["agent"], "pane": s["pane"], "tab": s["tab"], "last_scan_start": db.iso(s["scan_start_ts"]),
            "last_scan_end": db.iso(s["scan_end_ts"]), "scan_due": scan_due(conn, key, now),
            "interval_s": interval(now),
            "proposed": conn.execute("SELECT COUNT(*) FROM proposals WHERE realm=? AND state='proposed'",
                                     (key,)).fetchone()[0],
            "cursors": [dict(r) for r in conn.execute(
                "SELECT source, scope, cursor, updated_ts FROM scout_cursors WHERE realm=? ORDER BY source, scope",
                (key,))]}


# ---------- CLI ----------

def _stdin_json():
    import sys

    return json.load(sys.stdin)


def _ids(s):
    return [int(x.lstrip("Pp")) for x in (s or "").replace(" ", "").split(",") if x]


def register(sub):
    run, kp = db.run_verb, db.keyed_parser

    sc = sub.add_parser("scout", help="scout: channel tracker and proposals").add_subparsers(dest="sccmd", required=True)
    p = kp(sc, "spawn", "start the realm's scout in its own tab")
    p.set_defaults(fn=run(lambda c, a, now: spawn(c, a.key, now)))
    p = kp(sc, "show", "the scout, its schedule and cursors")
    p.set_defaults(fn=run(lambda c, a, now: show(c, a.key, now)))
    p = kp(sc, "scan-start", "record a scan's start")
    p.set_defaults(fn=run(lambda c, a, now: scan_start(c, a.key, now)))
    p = kp(sc, "scan-end", "record a scan's end (refused while a proposal of it was never mailed); pushes titles")
    p.set_defaults(fn=run(lambda c, a, now: scan_end(c, a.key, now)))
    p = kp(sc, "cursor", "a source's cursors (first=true: backfill a month)")
    p.add_argument("--source", required=True, choices=SOURCES)
    p.set_defaults(fn=run(lambda c, a, now: cursors(c, a.key, a.source, now)))
    p = kp(sc, "unseen", "the ids, among --ids, not judged yet")
    p.add_argument("--source", required=True, choices=SOURCES)
    p.add_argument("--ids", required=True, help="comma-separated message ids")
    p.set_defaults(fn=run(lambda c, a, now: unseen(c, a.key, a.source, [x for x in a.ids.split(",") if x])))
    p = kp(sc, "ack", "stdin {source, cursors, ids}: mark judged, advance cursors")
    p.set_defaults(fn=run(lambda c, a, now: ack(c, a.key, _stdin_json(), now)))
    p = kp(sc, "fetch", "a source's next unjudged messages, in ack's shape; marks nothing read")
    p.add_argument("source", choices=SOURCES)
    p.add_argument("--limit", type=int, default=FETCH_LIMIT, help="oldest N unjudged; more=true means fetch again")
    p.set_defaults(fn=run(lambda c, a, now: fetch(c, a.key, a.source, now, a.limit)))
    p = kp(sc, "propose", "stdin [proposal, …]: record them; duplicates come back flagged")
    p.set_defaults(fn=run(lambda c, a, now: propose(c, a.key, _stdin_json(), now)))

    pr = sub.add_parser("proposal", help="proposals awaiting the user").add_subparsers(dest="prcmd", required=True)
    p = kp(pr, "list", "proposals (default: proposed)")
    p.add_argument("--state", action="append", choices=("proposed", "approved", "rejected", "applied", "failed"))
    p.add_argument("--ids", help="P1,P2 or 1,2")
    p.add_argument("--md", action="store_true", help="markdown, as mailed and shown to the user")
    p.set_defaults(fn=run(lambda c, a, now: (render if a.md else (lambda x: x))(list_proposals(
        c, a.key, None if a.ids else (a.state or ["proposed"]), _ids(a.ids) or None))))
    p = kp(pr, "decide", "the user's verdict per item")
    p.add_argument("--approve", default="")
    p.add_argument("--reject", default="")
    p.set_defaults(fn=run(lambda c, a, now: decide(c, a.key, _ids(a.approve), _ids(a.reject), now)))
    p = kp(pr, "apply", "write approved task.add proposals into tasks")
    p.add_argument("--ids", required=True)
    p.set_defaults(fn=run(lambda c, a, now: apply_tasks(c, a.key, _ids(a.ids), now)))
    p = kp(pr, "mailed", "record the Agent Mail message that carried these proposals to the queen")
    p.add_argument("--ids", required=True)
    p.add_argument("--mail-id", type=int, required=True)
    p.set_defaults(fn=run(lambda c, a, now: mailed(c, a.key, _ids(a.ids), a.mail_id)))
    p = kp(pr, "applied", "a worker executed (or failed) an approved calendar proposal")
    p.add_argument("--id", required=True)
    p.add_argument("--ref", required=True, help="event id, or the failure reason with --failed")
    p.add_argument("--failed", action="store_true")
    p.set_defaults(fn=run(lambda c, a, now: applied(c, a.key, _ids(a.id)[0], a.ref, a.failed, now)))

    tk = sub.add_parser("task", help="the user's to-do list").add_subparsers(dest="tkcmd", required=True)
    p = kp(tk, "add", "add a task directly (the user asked for it)")
    p.add_argument("--title", required=True)
    p.add_argument("--notes")
    p.add_argument("--due", help="ISO date or datetime")
    p.set_defaults(fn=run(lambda c, a, now: add_task(c, a.key, a.title, a.notes, a.due, now)))
    p = kp(tk, "list", "tasks (default: open)")
    p.add_argument("--state", action="append", choices=("open", "done", "dropped"))
    p.set_defaults(fn=run(lambda c, a, now: list_tasks(c, a.key, a.state or ["open"])))
    for verb, state in (("done", "done"), ("drop", "dropped"), ("reopen", "open")):
        p = kp(tk, verb, f"mark a task {state}")
        p.add_argument("--id", type=int, required=True)
        p.set_defaults(fn=run(lambda c, a, now, s=state: set_task(c, a.key, a.id, s, now)))
