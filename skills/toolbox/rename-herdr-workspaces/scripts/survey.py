#!/usr/bin/env python3
"""Read-only survey: what every linked-worktree herdr workspace is on, with the
agent's recent conversation so the caller can name it.

One command, no follow-up reads: the brief is deliberately the whole naming
material — branch state, files touched, last commits, and the last rounds the
agent actually wrote. Nothing here proposes a label; naming is judgement.

Parallel per workspace, and one `git status --short --branch` carries branch,
upstream and ahead/behind together.

    survey.py                 # brief + herdr-survey.json
    survey.py --rounds 30     # more conversation per pane
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

MAX_WORKERS = 8
ROUND_CHARS, TOOL_CHARS = 200, 110
TAIL_BYTES = 4_000_000
COMMITS, FILES = 4, 6


def herdr(*args):
    if os.environ.get("HERDR_ENV") != "1":
        sys.exit("HERDR_ENV is not 1: this shell is not inside a herdr session, so the socket API may "
                 "belong to another server. Say so and stop instead of renaming anything.")
    proc = subprocess.run(["herdr"] + list(args), capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit("herdr %s failed: %s" % (" ".join(args), (proc.stderr or proc.stdout).strip()))
    return proc.stdout.strip()


def herdr_json(*args):
    return json.loads(herdr(*args))["result"]


def git(path, *args):
    proc = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr.strip()


def clean_title(title):
    """Drop the status-line glyphs — spinner, agent logo, icons — keep the words."""
    words = [word for word in (title or "").split() if re.search(r"[A-Za-z]{2}", word)]
    return re.sub(r"^[^A-Za-z0-9]+", "", " ".join(words)).strip()


def one_line(text, limit=ROUND_CHARS):
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def tool_summary(name, args):
    """What the call was after, minus the `cd <checkout> &&` every call carries."""
    for key in ("command", "path", "pattern", "i"):
        value = (args or {}).get(key)
        if isinstance(value, str) and value.strip():
            value = re.sub(r"(?:^|;\s*)cd [^;&|]+?&&\s*", "", value.strip())
            return one_line("%s %s" % (name or "tool", value.strip()), TOOL_CHARS)
    return (name or "tool")[:40]


def session_rounds(path, rounds):
    """Last `rounds` turns of the agent's session: prompts, answers, tool calls.

    Tool calls carry the current work when the agent has not written a summary
    yet; thinking blocks are dropped, being long and superseded by the answer.
    The newest prompt and answer survive even when the window fills with tool
    calls, so the reason the work exists is never what got cut.
    """
    if not path:
        return []
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - TAIL_BYTES))
            blob = handle.read().decode("utf-8", "replace")
    except OSError:
        return []
    events = []
    for line in blob.splitlines():
        try:
            node = json.loads(line)
        except ValueError:
            continue
        data = node.get("data") or {}
        if node.get("customType") == "tool_execution_start":
            events.append({"role": "tool", "text": tool_summary(data.get("toolName"), data.get("args"))})
            continue
        message = node.get("message") or {}
        role = message.get("role")
        if role not in ("user", "assistant"):
            continue
        parts = [part.get("text") or "" for part in message.get("content") or []
                 if isinstance(part, dict) and part.get("type") == "text"]
        text = one_line(" ".join(parts), 300 if role == "user" else ROUND_CHARS)
        if text:
            events.append({"role": role, "text": text})
    if len(events) <= rounds:
        return events
    kept = events[-rounds:]
    for role in ("user", "assistant"):
        if not any(event["role"] == role for event in kept):
            last = next((event for event in reversed(events) if event["role"] == role), None)
            if last:
                kept.insert(0, last)
    return kept


def pane_facts(pane, rounds):
    return {
        "pane_id": pane["pane_id"],
        "agent": pane.get("agent"),
        "agent_status": pane.get("agent_status"),
        "title": clean_title(pane.get("terminal_title_stripped") or pane.get("terminal_title")),
        "rounds": session_rounds((pane.get("agent_session") or {}).get("value"), rounds),
    }


BRANCH = re.compile(r"^## (?:No commits yet on )?([^.\s]+)(?:\.\.\.(\S+))?(?: \[(.+)\])?")


def git_facts(path):
    """Branch, upstream, ahead/behind and dirt in a single git invocation."""
    facts = {"checkout": path, "branch": None, "upstream": None, "ahead": 0, "behind": 0,
             "status": [], "dirty": 0, "commits": []}
    code, out, _ = git(path, "status", "--short", "--branch")
    if code == 0:
        rows = [row.rstrip() for row in out.splitlines() if row.strip()]
        if rows and rows[0].startswith("## "):
            match = BRANCH.match(rows[0])
            if match:
                facts["branch"] = None if match.group(1) == "HEAD" else match.group(1)
                facts["upstream"] = match.group(2)
                counts = match.group(3) or ""
                for key in ("ahead", "behind"):
                    found = re.search(key + r" (\d+)", counts)
                    if found:
                        facts[key] = int(found.group(1))
            rows = rows[1:]
        facts["status"] = rows[:20]
        facts["dirty"] = len(rows)
    code, out, _ = git(path, "log", "--oneline", "-%d" % COMMITS, "--no-decorate")
    if code == 0:
        facts["commits"] = [row for row in out.splitlines() if row]
    return facts


def survey(rounds, only):
    workspaces = herdr_json("workspace", "list")["workspaces"]
    panes = {}
    for pane in herdr_json("pane", "list")["panes"]:
        panes.setdefault(pane["workspace_id"], []).append(pane)

    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "targets": [], "skipped": []}
    targets = []
    for ws in workspaces:
        worktree = ws.get("worktree") or {}
        entry = {"workspace_id": ws["workspace_id"], "label": ws.get("label"),
                 "agent_status": ws.get("agent_status"), "repo": worktree.get("repo_name")}
        if not worktree:
            out["skipped"].append(dict(entry, why="not a git workspace"))
        elif not worktree.get("is_linked_worktree"):
            out["skipped"].append(dict(entry, why="primary checkout"))
        elif only and entry["workspace_id"] not in only:
            continue
        elif not worktree.get("checkout_path") or not os.path.isdir(worktree["checkout_path"]):
            out["skipped"].append(dict(entry, why="checkout folder missing: %s" % worktree.get("checkout_path")))
        else:
            entry["checkout"] = worktree["checkout_path"]
            targets.append(entry)

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        git_jobs = {e["workspace_id"]: pool.submit(git_facts, e["checkout"]) for e in targets}
        pane_jobs = {e["workspace_id"]: pool.submit(
            lambda e: [pane_facts(p, rounds) for p in panes.get(e["workspace_id"], [])], e) for e in targets}
        for entry in targets:
            entry.update(git_jobs[entry["workspace_id"]].result())
            entry["panes"] = pane_jobs[entry["workspace_id"]].result()
            out["targets"].append(entry)
    return out


def brief(state):
    lines = []
    for target in state["targets"]:
        upstream = target["upstream"] or "none"
        lines.append("%s  %s   [%s]  %s" % (target["workspace_id"], target["label"], target["agent_status"], target["repo"]))
        lines.append("  branch   %s   upstream %s  +%d/-%d  dirty %d"
                     % (target["branch"] or "(detached)", upstream, target["ahead"], target["behind"], target["dirty"]))
        for row in target["status"][:FILES]:
            lines.append("  file     %s" % row)
        for commit in target["commits"]:
            lines.append("  commit   %s" % commit)
        for pane in target["panes"]:
            lines.append("  pane     %s  agent %s (%s)  title: %s"
                         % (pane["pane_id"], pane["agent"] or "-", pane["agent_status"], pane["title"] or "-"))
            for round_ in pane["rounds"]:
                label = {"user": "user", "assistant": "ai"}.get(round_["role"], "tool")
                lines.append("  %-5s  %s" % (label, round_["text"]))
        lines.append("")
    for entry in state["skipped"]:
        lines.append("skipped %s  %s  (%s)" % (entry["workspace_id"], entry["label"], entry["why"]))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default="herdr-survey.json", help="where to write the facts (default: herdr-survey.json)")
    parser.add_argument("--rounds", type=int, default=25, help="conversation rounds per pane (default: 25)")
    parser.add_argument("--workspace", action="append", default=[], help="survey only this workspace (repeatable)")
    args = parser.parse_args(argv)
    state = survey(args.rounds, set(args.workspace))
    with open(args.json, "w") as handle:
        json.dump(state, handle, indent=2)
    print(brief(state))
    print("\n%d target(s), %d skipped. Facts: %s" % (len(state["targets"]), len(state["skipped"]), args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
