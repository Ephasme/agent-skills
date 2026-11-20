"""Agent Mail over its MCP HTTP endpoint, as ~/.omp/agent/mcp.json defines it."""

import json
import subprocess
import urllib.parse
import urllib.request

from .state import HOME

MAIL_SERVER = "agent-mail-perso"
MCP_CONFIG = HOME / ".omp/agent/mcp.json"
EVENTS_PAGE = 1000


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


def mail_rpc(endpoint, method, params):
    """One stateless JSON-RPC call to the Agent Mail server; returns its `result`."""
    url, headers = endpoint
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
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
        raise RuntimeError(f"{method}: {reply['error']}")
    return reply["result"]


class MailToolError(RuntimeError):
    def __init__(self, kind, message):
        super().__init__(f"{kind}: {message}")
        self.kind = kind


def mail_tool(endpoint, name, args):
    result = mail_rpc(endpoint, "tools/call", {"name": name, "arguments": args})
    data = json.loads(result["content"][0]["text"])
    if result.get("isError") or "error" in data:
        err = data.get("error") or {}
        raise MailToolError(err.get("type", "unknown"), err.get("message", str(data)[:200]))
    return data


def fetch_events(endpoint, agent, project, cursor):
    """Message ids delivered to agent after cursor, and the cursor to store once they are handled.

    cursor None asks for the durable tail only: no ids, the position to start from.
    """
    base = {"project_key": project, "agent_name": agent}
    if cursor is None:
        return [], mail_tool(endpoint, "fetch_inbox_events", {**base, "position_now": True})["tail_cursor"]
    ids = []
    while True:
        page = mail_tool(endpoint, "fetch_inbox_events", {**base, "after": cursor, "limit": EVENTS_PAGE})
        ids += [e["message_id"] for e in page["events"]]
        cursor = page["next_cursor"]
        if not page["has_more"]:
            return ids, cursor


def unread_ids(endpoint, agent, project):
    """Ids of agent's unread messages in project, via the read-only inbox priority snapshot.

    `resource://inbox/{agent}?context=true&unread=true` reads one database snapshot without marking
    anything read, acknowledging, or touching activity; fetch_inbox would mark the messages read.
    """
    query = urllib.parse.urlencode(
        {"project": project, "context": "true", "unread": "true", "format": "json", "limit": 1000}
    )
    uri = f"resource://inbox/{urllib.parse.quote(agent)}?{query}"
    snap = json.loads(mail_rpc(endpoint, "resources/read", {"uri": uri})["contents"][0]["text"])
    if "messages" not in snap:
        raise RuntimeError(f"unexpected inbox snapshot: {str(snap)[:200]}")
    return {m["id"] for m in snap["messages"] if m.get("read_ts") is None}
