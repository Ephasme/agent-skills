"""Realm memory in Loup's Hindsight server: one bank per realm key, never his `personal` or `work` banks.

Endpoint and bearer come from the `hindsight` entry of ~/.omp/agent/mcp.json, the one agents use as MCP tools:
its URL is `<api>/mcp/<bank>/`, and its Authorization header is a `!` shell command resolved at call time, so the
key never lands in this code, the db, mail or logs.

Hooks (`on_done`, `context_block`) are best-effort: Hindsight runs on the NAS and is gone during a home-link
outage, so a failure logs `hindsight: skipped …` and the verb carries on. The `memory` verbs fail loudly.
"""

import json
import os
import subprocess
import urllib.error
import urllib.request

from .state import HOME, log

MCP_CONFIG = HOME / ".omp/agent/mcp.json"
SERVER = "hindsight"
TIMEOUT = 10  # hooks: a dispatch must not stall on a slow recall
VERB_TIMEOUT = 120  # `realm memory`: a recall waits on the server's embedding call, whose tail reached 40 s
REPLY_MAX = 4000
CONTEXT_FACTS = 8


def bank_id(key):
    """`/perso/realm` → `realm-perso-realm`."""
    return "realm-" + key.strip("/").replace("/", "-")


def _endpoint():
    cfg = json.loads(MCP_CONFIG.read_text())
    srv = (cfg.get("mcpServers") or cfg.get("servers") or {})[SERVER]
    api = srv["url"].split("/mcp/")[0]
    headers = {}
    for name, value in (srv.get("headers") or {}).items():
        if value.startswith("!"):
            p = subprocess.run(["/bin/sh", "-c", value[1:]], capture_output=True, text=True, timeout=30)
            value = p.stdout.strip()
            if p.returncode != 0 or not value:
                raise RuntimeError(f"hindsight header {name}: command failed: {p.stderr.strip()[:200]}")
        headers[name] = value
    return api, headers


def _request(method, path, body=None, timeout=TIMEOUT):
    api, headers = _endpoint()
    req = urllib.request.Request(
        f"{api}/v1/default/banks/{path}",
        method=method,
        data=None if body is None else json.dumps(body).encode(),
        # Cloudflare answers 403 / error 1010 to urllib's default `Python-urllib/x.y` User-Agent.
        headers={**headers, "Content-Type": "application/json", "User-Agent": "realm/1"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"hindsight {method} {path}: HTTP {e.code} {e.read()[:200]!r}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise RuntimeError(f"hindsight {method} {path}: {e}") from e
    return json.loads(raw) if raw.strip() else {}


def ensure_bank(key):
    """Create the realm's bank, or update its name and mission (idempotent)."""
    return _request("PUT", bank_id(key), {
        "name": f"realm {key}",
        "mission": f"Shared memory of the {key} agent swarm working for Loup Peluso: subject outcomes, "
                   "queen decisions, Loup's answers, approved channel facts, and facts about Loup himself.",
    })


def retain(key, items, wait=False, timeout=TIMEOUT):
    """items: [{content, context?, document_id?, tags?, timestamp?}]. Async unless wait: extraction is an LLM call."""
    return _request("POST", f"{bank_id(key)}/memories", {"items": items, "async": not wait}, timeout)


def recall(key, query, tags=None, max_tokens=2048, timeout=TIMEOUT):
    body = {"query": query, "max_tokens": max_tokens}
    if tags:
        body.update(tags=tags, tags_match="any")
    return _request("POST", f"{bank_id(key)}/memories/recall", body, timeout).get("results", [])


def hooks_enabled(key):
    """Hooks stay off for test keys (`/test/…`) and when REALM_HINDSIGHT=off, so suites never reach the server."""
    return os.environ.get("REALM_HINDSIGHT") != "off" and not key.startswith("/test/")


def _safe(what, fn, key, *args):
    if not hooks_enabled(key):
        return None
    try:
        return fn(key, *args)
    except Exception as e:  # noqa: BLE001 - a hook must never break the verb it rides on
        log(f"hindsight: skipped {what}: {e}")
        return None


def on_done(key, subject, reply_body=None):
    """A subject went to done: retain its outcome, upserted per subject so a reopen-and-close replaces it."""
    text = f"Subject [{subject['slug']}] \"{subject['title']}\" was completed by worker {subject['worker']}."
    if subject.get("status"):
        text += f" Final status: {subject['status']}."
    if reply_body:
        text += "\n\nThe worker's last reply:\n" + reply_body[:REPLY_MAX]
    tags = ["kind:subject-outcome", f"subject:{subject['slug']}"]
    if subject.get("worker"):
        tags.append(f"worker:{subject['worker']}")
    return _safe(f"retain {subject['slug']}", retain, key, [{
        "content": text, "context": "realm subject outcome", "document_id": f"subject/{subject['slug']}",
        "tags": tags}])


def on_create(key):
    """A realm was created: make sure its bank exists."""
    return _safe("ensure bank", ensure_bank, key)


def context_block(key, query):
    """Markdown block of the realm facts relevant to a subject, for the dispatch mail; '' when none or down."""
    results = _safe("recall for dispatch", recall, key, query, None, 1024) or []
    facts = [r["text"] for r in results[:CONTEXT_FACTS] if r.get("text")]
    if not facts:
        return ""
    lines = "\n".join(f"- {f}" for f in facts)
    return ("\n\n## Realm memory (Hindsight, recalled for this subject; may be stale)\n" + lines +
            "\n\nMore: the `hindsight` MCP tools (`recall`, `retain`) work on this realm's bank only.")


# ---------- CLI ----------

def _read(path):
    import sys
    from pathlib import Path

    return sys.stdin.read() if path == "-" else Path(path).read_text()


def _items(a):
    """--file holds either plain text (one item) or a JSON list of items."""
    raw = _read(a.file)
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        items = None
    if not isinstance(items, list):
        items = [{"content": raw}]
    for it in items:
        if a.document_id and len(items) == 1:
            it.setdefault("document_id", a.document_id)
        if a.context:
            it.setdefault("context", a.context)
        it["tags"] = sorted(set(it.get("tags") or []) | set(a.tag or []))
    return items


def register(sub):
    from . import db

    def verb(fn):
        """Network and server failures become the verb's {"error": …} instead of a traceback."""
        def run(c, a, now):
            try:
                return fn(c, a, now)
            except RuntimeError as e:
                raise db.Refused(str(e)) from e
        return db.run_verb(run)

    m = sub.add_parser("memory", help="hindsight: the realm's memory bank").add_subparsers(dest="mcmd", required=True)
    p = db.keyed_parser(m, "init", "create or update the realm's bank")
    p.set_defaults(fn=verb(lambda c, a, now: {"bank": bank_id(a.key), **ensure_bank(a.key)}))
    p = db.keyed_parser(m, "retain", "store text (or a JSON list of items) in the realm's bank")
    p.add_argument("--file", default="-", help="text or JSON items; - reads stdin")
    p.add_argument("--document-id", help="upsert key: same id replaces the earlier document")
    p.add_argument("--context")
    p.add_argument("--tag", action="append", help="repeatable, e.g. --tag decision")
    p.add_argument("--wait", action="store_true", help="return after extraction, not before")
    p.set_defaults(fn=verb(lambda c, a, now: retain(a.key, _items(a), a.wait, VERB_TIMEOUT)))
    p = db.keyed_parser(m, "recall", "facts from the realm's bank relevant to a query")
    p.add_argument("--query", required=True)
    p.add_argument("--tag", action="append")
    p.add_argument("--max-tokens", type=int, default=2048)
    p.set_defaults(fn=verb(lambda c, a, now: [
        {k: r.get(k) for k in ("text", "type", "tags", "occurred_start", "document_id") if r.get(k)}
        for r in recall(a.key, a.query, a.tag, a.max_tokens, VERB_TIMEOUT)]))
