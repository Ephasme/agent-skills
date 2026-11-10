#!/usr/bin/env python3
"""Read-only survey: what every linked-worktree herdr workspace is on right now.

One run replaces a dozen commands per workspace. It prints a brief and writes
the same facts as JSON, so apply.py can re-read them under the same keys and the
final report can quote the evidence.

It never proposes a label. Naming is the caller's job; see labels.py for the
rules a label has to satisfy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

BOX = "│├╭╰╮╯─┬┴┼┤┌┐└┘"
MARKERS = re.compile(r"(?i)(\[\s*[xX-]?\s*\]|[☐☒]|✅|\bTODO\b|\bin[ _-]?progress\b|\bWIP\b|\bnext\b)")
TAIL, TODO_MAX = 6, 12


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
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def git_raw(path, *args):
    """Untrimmed stdout: `status --short` puts a space in column one, and stripping
    it turns the first row into a two-column format nobody can parse back."""
    proc = subprocess.run(["git", "-C", path] + list(args), capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr.strip()


def clean(text):
    """Drop the pane's box drawing and padding, keep the content."""
    rows = []
    for line in text.splitlines():
        line = line.strip(BOX).strip()
        if line:
            rows.append(line)
    return rows


TASK_STATES = {"pending", "in_progress", "in-progress", "todo", "completed", "done", "blocked", "cancelled"}
GLYPH = re.compile(r"^[^A-Za-z0-9]+")


def walk_todo(node, depth=0):
    """First recorded todo list: items that carry both a task state and a text.

    Both are required because every agent session is full of lists that look
    like tasks to a looser test — numeric columns come back as `- 1`, `- 0.02`
    — and a wrong TODO is worse than none.
    """
    if depth > 12:
        return []
    if isinstance(node, dict):
        for key, value in node.items():
            if key in ("todos", "items", "tasks", "plan") and isinstance(value, list) and value:
                rows = []
                for item in value:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("content") or item.get("title") or item.get("text") or item.get("name")
                    state = item.get("status") or item.get("state")
                    if text and state in TASK_STATES:
                        rows.append(("%s %s" % (state, str(text).splitlines()[0]))[:200])
                if rows:
                    return rows
            found = walk_todo(value, depth + 1)
            if found:
                return found
    elif isinstance(node, list):
        for value in reversed(node[-5:]):
            found = walk_todo(value, depth + 1)
            if found:
                return found
    return []


def clean_title(title):
    """Drop the status-line glyphs — spinner, agent logo, icons — keep the words."""
    words = [word for word in (title or "").split() if re.search(r"[A-Za-z]{2}", word)]
    return GLYPH.sub("", " ".join(words)).strip()


def todo_from_session(path):
    """The newest todo list the agent recorded, when its session is a JSONL of turns."""
    try:
        with open(path, "rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(0, handle.tell() - 400_000))
            blob = handle.read().decode("utf-8", "replace")
    except (OSError, TypeError):
        return []
    for line in reversed(blob.splitlines()):
        try:
            node = json.loads(line)
        except ValueError:
            continue
        found = walk_todo(node)
        if found:
            return found
    return []


def pane_facts(pane, lines):
    text = herdr("pane", "read", pane["pane_id"], "--source", "recent-unwrapped", "--lines", str(lines))
    rows = clean(text)
    marker_rows = [row[:200] for row in rows if MARKERS.search(row)]
    todo = todo_from_session((pane.get("agent_session") or {}).get("value"))
    return {
        "pane_id": pane["pane_id"],
        "agent": pane.get("agent"),
        "agent_status": pane.get("agent_status"),
        "title": clean_title(pane.get("terminal_title_stripped") or pane.get("terminal_title")),
        "todo": todo,
        "marked": marker_rows[-TODO_MAX:],
        "tail": [row[:200] for row in rows[-TAIL:]],
    }


def git_facts(path):
    facts = {"checkout": path}
    rc, out, _ = git(path, "branch", "--show-current")
    facts["branch"] = out or None
    rc, out, _ = git(path, "log", "--oneline", "-8", "--no-decorate")
    facts["commits"] = [line for line in out.splitlines() if line]
    rc, out, _ = git_raw(path, "status", "--short")
    rows = [line.rstrip() for line in out.splitlines() if line.strip()]
    facts["status"] = rows[:20]
    facts["dirty"] = len(rows)
    rc, out, _ = git(path, "rev-parse", "--abbrev-ref", "@{u}")
    facts["upstream"] = out if rc == 0 else None
    if facts["upstream"]:
        rc, out, _ = git(path, "rev-list", "--left-right", "--count", "@{u}...HEAD")
        if rc == 0 and out:
            behind, ahead = out.split()
            facts["behind"], facts["ahead"] = int(behind), int(ahead)
        else:
            facts["behind"] = facts["ahead"] = 0
    return facts


def survey(lines, only):
    out = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "targets": [], "skipped": []}
    for ws in herdr_json("workspace", "list")["workspaces"]:
        worktree = ws.get("worktree") or {}
        entry = {
            "workspace_id": ws["workspace_id"],
            "label": ws.get("label"),
            "agent_status": ws.get("agent_status"),
            "repo": worktree.get("repo_name"),
        }
        if not worktree:
            out["skipped"].append(dict(entry, why="not a git workspace"))
            continue
        if not worktree.get("is_linked_worktree"):
            out["skipped"].append(dict(entry, why="primary checkout"))
            continue
        if only and entry["workspace_id"] not in only:
            continue
        path = worktree.get("checkout_path")
        if not path or not os.path.isdir(path):
            out["skipped"].append(dict(entry, why="checkout folder missing: %s" % path))
            continue
        entry.update(git_facts(path))
        entry["panes"] = [pane_facts(p, lines) for p in herdr_json("pane", "list", "--workspace", entry["workspace_id"])["panes"]]
        out["targets"].append(entry)
    return out


def brief(state):
    lines = []
    for target in state["targets"]:
        lines.append("%s  %s   [%s]  %s" % (target["workspace_id"], target["label"], target["agent_status"], target["repo"]))
        branch = target["branch"] or "(detached)"
        behind = target.get("behind") or 0
        ahead = target.get("ahead") or 0
        upstream = target["upstream"] or "none"
        lines.append("  branch   %s   upstream %s  %+d/-%d  dirty %d" % (branch, upstream, ahead, behind, target["dirty"]))
        for row in target["status"][:8]:
            lines.append("  file     %s" % row)
        for commit in target["commits"][:8]:
            lines.append("  commit   %s" % commit)
        for pane in target["panes"]:
            lines.append("  pane     %s  agent %s (%s)" % (pane["pane_id"], pane["agent"] or "-", pane["agent_status"]))
            if pane["title"]:
                lines.append("  title    %s" % pane["title"])
            for row in pane["todo"]:
                lines.append("  todo     %s" % row)
            for row in pane["marked"][-6:]:
                lines.append("  marked   %s" % row)
            for row in pane["tail"]:
                lines.append("  tail     %s" % row)
        lines.append("")
    for entry in state["skipped"]:
        lines.append("skipped %s  %s  (%s)" % (entry["workspace_id"], entry["label"], entry["why"]))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default="herdr-survey.json", help="where to write the facts (default: herdr-survey.json)")
    parser.add_argument("--lines", type=int, default=60, help="pane lines to read (default: 60)")
    parser.add_argument("--workspace", action="append", default=[], help="survey only this workspace (repeatable)")
    args = parser.parse_args(argv)
    state = survey(args.lines, set(args.workspace))
    with open(args.json, "w") as handle:
        json.dump(state, handle, indent=2)
    print(brief(state))
    print("\n%d target(s), %d skipped. Facts: %s" % (len(state["targets"]), len(state["skipped"]), args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
