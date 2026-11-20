"""Agent Mail over its MCP HTTP endpoint, as ~/.omp/agent/mcp.json defines it."""

import json
import subprocess
import urllib.parse
import urllib.request

from .state import HOME

MAIL_SERVER = "agent-mail-perso"
MCP_CONFIG = HOME / ".omp/agent/mcp.json"


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
