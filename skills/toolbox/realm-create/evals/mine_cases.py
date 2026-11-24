"""Mine eval cases from real queen sessions.

The ratchet's cases were written by hand; the failures that matter in real sessions
(the queen doing the work herself, the queen asking the user about coordination) had
no cases at all. This reads omp session transcripts, keeps the queen's turns, and
emits candidates in the ratchet case schema: the user's words as `prompt`, the
environment as `context`, the expected behaviour as `checks`, and the session file
plus turn index in `source` so every case is traceable.

    python3 mine_cases.py --out mined-candidates.json [--sessions DIR] [--verbose]

It only *proposes*. A candidate becomes a case after a human reads the turn and
confirms that the behaviour graded is the skill's, not the miner's guess; `--that`
is why the emitted `expectations` quote the rule the case enforces.

Queen sessions are found by content, not by title: a session where the agent sends
mail as an agent that also runs `realm dispatch`/`realm table`.
"""
from __future__ import annotations

import argparse
import collections
import glob
import json
import os
import re
from pathlib import Path

SESSIONS = Path.home() / ".omp/agent/sessions"

# Programs whose use on a user turn is work the queen must delegate. Reading state to
# route work is `realm`, mail and `herdr pane read`; everything here is investigation,
# building, editing, shipping or reaching another machine.
WORK = {
    "git", "gh", "ssh", "scp", "rsync", "npm", "npx", "pnpm", "yarn", "bun", "cargo",
    "pytest", "make", "docker", "curl", "wget", "find", "rg", "rustc", "python", "python3",
}
INSPECT = {"sed", "grep", "ls", "cat", "head", "tail", "wc", "awk", "jq", "diff", "sort"}
ROUTE = {"realm", "herdr", "echo", "mkdir", "sleep", "wait", "true", "source", "export", "cd"}
TRIVIAL = re.compile(r"\b(du|ls|pwd|which)\b|^git status\b|^git log --oneline")

COORDINATION = re.compile(
    r"which worker|split|sequenc|queue|dispatch|branch base|stack|merge order|"
    r"assign|to whom|who should|scope|slice", re.I)
USER_OWNED = re.compile(
    r"credential|vault|unlock|sign-?in|password|token|deploy|release|money|price|"
    r"budget|pay|calendar|meeting|grant|approve", re.I)


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "\n".join(b.get("text", "") for b in content or [] if b.get("type") == "text")


def _toolcalls(content):
    if isinstance(content, str):
        return []
    return [b for b in content or [] if b.get("type") == "toolCall"]


def _segments(command: str):
    """(program, argv) per shell segment; heredoc bodies already dropped by the caller."""
    out = []
    for seg in re.split(r"\s*(?:;|&&|\|\||\n)\s*", command):
        if not seg.strip():
            continue
        try:
            import shlex
            argv = shlex.split(seg)
        except ValueError:
            argv = seg.split()
        while argv and re.match(r"^[A-Za-z_]\w*=", argv[0]):
            argv = argv[1:]
        if not argv:
            continue
        prog = os.path.basename(argv[0])
        if prog in ("python", "python3") and any(a.endswith("realm.py") for a in argv):
            prog = "realm"
        out.append((prog, argv))
    return out


def read_session(path: Path):
    turns, cur = [], None
    agent, title = None, ""
    for line in path.open():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("type") == "title" and not title:
            title = row.get("title") or ""
        msg = row.get("message") or {}
        role = msg.get("role")
        if role == "user":
            text = _text(msg.get("content")).strip()
            if not text or text.startswith("<system-reminder>"):
                continue
            cur = {"user": text, "calls": [], "reply": ""}
            turns.append(cur)
        elif role == "assistant" and cur is not None:
            for b in msg.get("content") if isinstance(msg.get("content"), list) else []:
                if b.get("type") == "toolCall":
                    cur["calls"].append({"name": b.get("name"), "args": b.get("arguments") or {}})
                    args = b.get("arguments") or {}
                    if b.get("name") == "macro_start_session" and args.get("agent_name"):
                        agent = args["agent_name"]
            text = _text(msg.get("content")).strip()
            if text:
                cur["reply"] = text
        elif role == "toolResult" and cur is not None:
            blob = _text(msg.get("content"))
            m = re.search(r'"queen"\s*:\s*"([A-Za-z]+)"', blob)
            if m:
                agent = m.group(1)
    return agent, turns, title


MAIL_HANDLE = re.compile(r"xd://mcp__\w+_(?:send|reply)_message$")


def _mail(call):
    """A mail send, however it is reached: the tool directly or a write to an MCP server's xd:// handle."""
    args = call.get("args") or {}
    if call.get("name") in ("send_message", "reply_message"):
        return args
    if call.get("name") == "write" and MAIL_HANDLE.search(str(args.get("path", ""))):
        try:
            return json.loads(args.get("content") or "{}")
        except json.JSONDecodeError:
            return {}
    return None


def queen_phase(turns):
    """The queen's turns, and her agent name: the phase starts at `realm restart`/`realm create`.

    A session can begin as Loup's own (content filter, unrelated work) and become the queen
    later; only what happens after the realm is taken over is queen material.
    """
    start = None
    for i, t in enumerate(turns):
        for c in t["calls"]:
            if c["name"] == "bash" and re.search(r"\brealm\s+(restart|create)\b",
                                                 c["args"].get("command", "")):
                start = i
                break
        if start is not None:
            break
    if start is None:
        return None, None
    # The queen's conversation spans restarts: every turn of a session that took a realm
    # over is addressed to her, including the ones before the restart call.
    return turns, "RubyGorge"


def workers(turns):
    names = collections.Counter()
    for t in turns:
        for c in t["calls"]:
            if c["name"] == "bash":
                for m in re.finditer(r"--to\s+([A-Z][a-z]+[A-Z][a-z]+)", c["args"].get("command", "")):
                    names[m.group(1)] += 1
            for k in ("to",):
                for n in (c["args"].get(k) or []) if isinstance(c["args"].get(k), list) else []:
                    if re.match(r"^[A-Z][a-z]+[A-Z][a-z]+$", str(n)):
                        names[str(n)] += 1
    return [n for n, _ in names.most_common(12)]


def classify(turn):
    """'delegation', 'coordination-ask', 'trivial-control' or None."""
    work, inspect_cmds, dispatched, asked = [], 0, False, None
    for c in turn["calls"]:
        if c["name"] == "bash":
            cmd = c["args"].get("command", "")
            for prog, argv in _segments(cmd):
                if prog in WORK and not (prog in ("python", "python3") and
                                         any(a.endswith("realm.py") for a in argv)):
                    work.append(prog)
                elif prog in INSPECT:
                    inspect_cmds += 1
                if prog == "realm" and "dispatch" in argv:
                    dispatched = True
            if re.search(r"\brealm\s+(dispatch|subject\s+add)\b", cmd):
                dispatched = True
        elif _mail(c) is not None:
            dispatched = dispatched or bool(_mail(c).get("body_md"))
        elif c["name"] == "ask":
            asked = c["args"].get("html") or c["args"].get("question") or ""
        elif c["name"] == "edit":
            work.append("edit")
        elif c["name"] == "write":
            p = c["args"].get("path", "")
            if p and not p.startswith("xd://") and not p.startswith("/tmp/"):
                work.append("write")
        elif c["name"] == "read":
            p = c["args"].get("path", "")
            if p and not p.startswith(("xd://", "skill://", "/tmp/")):
                inspect_cmds += 1
        elif c["name"] == "grep":
            inspect_cmds += 1
    if asked is not None and COORDINATION.search(asked) and not USER_OWNED.search(asked):
        return "coordination-ask", {"work": work, "asked": asked[:400]}
    if work or inspect_cmds >= 3:
        # "except if the user says otherwise": only explicit words let her act herself.
        if re.search(r"\b(do it|run it|fix it) yourself\b|\byou can do it\b|no need to bother",
                     turn["user"], re.IGNORECASE):
            return None, {}
        trivial = not work and TRIVIAL.search(turn["user"]) is not None and inspect_cmds <= 2
        if not trivial:
            return "delegation", {"work": work[:8], "inspect": inspect_cmds, "dispatched": dispatched}
    if not work and inspect_cmds <= 2 and TRIVIAL.search(turn["user"]) and dispatched:
        return "trivial-control", {"work": []}
    return None, {}


def context_for(agent, wks, pane):
    if not wks:
        return (f"You are the queen {agent} of realm /perso/realm, already running. Your pane is {pane} "
                f"(tab queen). No worker is idle.")
    return (f"You are the queen {agent} of realm /perso/realm, already running. Your pane is {pane} "
            f"(tab queen). Workers: " + ", ".join(wks) + ". Their panes are open and they are idle.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", default=str(SESSIONS))
    ap.add_argument("--out", default="mined-candidates.json")
    ap.add_argument("--verbose", action="store_true")
    a = ap.parse_args()
    cases, n, seen = [], 0, set()
    for path in sorted(glob.glob(a.sessions + "/*/*.jsonl")):
        p = Path(path)
        try:
            agent, turns, title = read_session(p)
        except Exception:
            continue
        if not turns or "QUEEN" not in title.upper():
            continue
        turns, agent = queen_phase(turns)
        if not turns or "QUEEN" not in title.upper():
            continue
        wks = workers(turns)
        for i, t in enumerate(turns):
            kind, why = classify(t)
            if not kind or t["user"][:160] in seen:
                continue
            seen.add(t["user"][:160])
            n += 1
            cases.append({
                "id": 3000 + n,
                "family": "delegation" if kind == "delegation" else
                          "coordination-ask" if kind == "coordination-ask" else "trivial-task",
                "polarity": "negative" if kind != "trivial-control" else "positive",
                "prompt": t["user"][:1200],
                "context": context_for(agent, wks, "w8:p1"),
                "expected_output": {
                    "delegation": "Dispatches the work to an idle worker; runs no build, edit, ssh, git or "
                                  "investigation of her own.",
                    "coordination-ask": "Decides and reports in one line; opens no question form.",
                    "trivial-control": "Does the trivial act herself and reports the result.",
                }[kind],
                "expectations": [why.get("work") and f"no {', '.join(why['work'])} by the queen" or "",
                                 "no question form"] if kind != "trivial-control" else ["the act is performed"],
                "checks": [],
                "source": f"{p.name}#turn{i}",
                "signals": why,
            })
    Path(a.out).write_text(json.dumps({"cases": cases}, indent=1, ensure_ascii=False))
    fam = collections.Counter(c["family"] for c in cases)
    print(f"{len(cases)} candidates from {len({c['source'].split('#')[0] for c in cases})} sessions: {dict(fam)}")
    if a.verbose:
        for c in cases:
            print(f"\n{c['id']} {c['family']} {c['source']}\n  USER: {c['prompt'][:160]!r}"
                  f"\n  why: {c['signals']}")


if __name__ == "__main__":
    main()
