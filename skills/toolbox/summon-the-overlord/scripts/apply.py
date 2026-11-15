#!/usr/bin/env python3
"""One command finishes the job: rename the workspace, move the branch when that
is safe, tell the agent that was moved, verify, print the report table.

The plan — one label per workspace — is the model's decision. Everything that
can be decided by a rule lives here instead, because these rules are
irreversible when got wrong: a branch name is pushed and its old remote ref
deleted, so every guard has to pass before that happens. Workspaces run in
parallel; nothing is left to a second command.

    apply.py '{"w7S": "nidi-search-trgm"}'            # dry run
    apply.py '{"w7S": "nidi-search-trgm"}' --apply    # do it, verify, report
    apply.py plan.json --apply --no-notify
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import labels
import survey
import verify

NOTIFY_POLLS, NOTIFY_SLEEP = 3, 1.2

# `git branch -m` parks a temp logfile in the repo's common log dir, so two
# renames in one repo at once destroy each other's reflog. One branch at a time
# per repo; workspaces of different repos still run in parallel.
LOCK_GUARD, REPO_LOCKS = threading.Lock(), {}


def repo_lock(name):
    with LOCK_GUARD:
        return REPO_LOCKS.setdefault(name or "", threading.Lock())


def sh(cmd, cwd=None, env=None):
    proc = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True,
        env={**os.environ, **env} if env else None,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def gh_token(slug):
    """The token of the gh login that reaches slug, or "" when the resolver is unavailable.

    Who's who is settled by overlord's credential(). A standalone run of this script has no
    httpx, so it keeps the active account, as before.
    """
    try:
        from overlord import credential
    except ImportError:
        return ""
    return credential(slug)[1]


def load_plan(spec):
    """A plan is a file, or the JSON itself — inline saves a write and a turn."""
    text = spec.strip()
    if text.startswith("{"):
        data = json.loads(text)
    elif text.startswith("["):
        data = json.loads(text)
    else:
        with open(spec) as handle:
            data = json.load(handle)
    if isinstance(data, dict):
        pairs = list(data.items())
    elif isinstance(data, list):
        if any(not isinstance(row, dict) or "workspace_id" not in row or "label" not in row for row in data):
            sys.exit("plan list entries must be objects with workspace_id and label")
        pairs = [(row["workspace_id"], row["label"]) for row in data]
    else:
        sys.exit("plan must be a JSON object or a list of workspace_id/label objects")
    seen, seen_ws = {}, set()
    for workspace_id, label in pairs:
        if not isinstance(workspace_id, str) or not workspace_id:
            sys.exit("plan workspace ids must be non-empty strings")
        if workspace_id in seen_ws:
            sys.exit("plan lists workspace %s more than once: each may appear once" % workspace_id)
        if not isinstance(label, str):
            sys.exit("plan label for %s must be a string" % workspace_id)
        if label in seen:
            sys.exit("plan gives %s the same label as %s: labels must be distinct" % (workspace_id, seen[label]))
        seen[label] = workspace_id
        seen_ws.add(workspace_id)
    return pairs


def repo_slug(path):
    """owner/repo for gh, which cannot parse the ssh alias the remote uses."""
    code, url, _ = survey.git(path, "remote", "get-url", "origin")
    if code != 0 or not url.strip():
        return None
    url = url.strip()
    if "://" in url:
        url = url.split("://", 1)[1]
        url = url.split("/", 1)[1] if "/" in url else ""
    elif ":" in url:
        url = url.split(":", 1)[1]
    url = url.strip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parts = [part for part in url.split("/") if part]
    return "%s/%s" % (parts[-2], parts[-1]) if len(parts) >= 2 else None


def open_prs(slug, branch):
    """PRs on this branch name in any state, or None when gh cannot answer."""
    token = gh_token(slug)
    code, out, _ = sh(
        ["gh", "pr", "list", "-R", slug, "--head", branch, "--state", "all", "--json", "number,state,url"],
        env={"GH_TOKEN": token} if token else None,
    )
    if code != 0:
        return None
    try:
        return json.loads(out or "[]")
    except ValueError:
        return None


def decide(entry, label, dry):
    """Can this branch move to worktree/<label>? Returns the decision, acts only when dry is False."""
    path, old = entry["checkout"], entry["branch"]
    new = "worktree/" + label
    out = {"old": old, "new": None, "reason": "", "pushed": False, "deleted_remote": False}
    if not old:
        out["reason"] = "detached HEAD"
        return out
    if not labels.is_generated(old):
        out["reason"] = "branch is a chosen name: %s" % old
        return out
    # The survey's facts can be minutes old and an agent may be switching branches.
    code, live, _ = survey.git(path, "branch", "--show-current")
    live = live.strip() if code == 0 else ""
    if live != old:
        out["reason"] = "branch changed since survey: %s" % (live or "detached")
        return out
    code, _, _ = survey.git(path, "show-ref", "--verify", "--quiet", "refs/heads/" + new)
    if code == 0:
        out["reason"] = "local branch %s already exists" % new
        return out

    with ThreadPoolExecutor(max_workers=2) as pool:
        remote_job = pool.submit(survey.git, path, "ls-remote", "--heads", "origin", new)
        slug = repo_slug(path) if entry["upstream"] else None
        pr_job = pool.submit(open_prs, slug, old) if slug else None
        code, remote_refs, _ = remote_job.result()
        if code != 0:
            out["reason"] = "cannot reach origin to check %s" % new
            return out
        if remote_refs.strip():
            out["reason"] = "remote branch %s already exists" % new
            return out
        if not entry["upstream"]:
            if dry:
                out.update(new=new, reason="no upstream")
                return out
            code, _, err = survey.git(path, "branch", "-m", new)
            if code != 0:
                out["reason"] = "branch -m failed: %s" % err
                return out
            out.update(new=new, reason="no upstream")
            return out
        if not slug:
            out["reason"] = "no origin remote"
            return out
        prs = pr_job.result()

    if prs is None:
        out["reason"] = "gh could not list PRs for %s" % slug
        return out
    if prs:
        out["reason"] = "PR on %s: %s" % (old, ", ".join("#%s %s" % (pr["number"], pr["state"]) for pr in prs))
        return out
    code, _, err = survey.git(path, "fetch", "origin", old)
    if code != 0:
        out["reason"] = "git fetch origin %s failed: %s" % (old, err.strip())
        return out
    code, behind, err = survey.git(path, "rev-list", "--count", "HEAD..@{u}")
    if code != 0 or not behind.strip().isdigit():
        out["reason"] = "cannot compare with upstream: %s" % (err or behind or "unknown")
        return out
    if int(behind) > 0:
        out["reason"] = "behind upstream by %s commits" % behind.strip()
        return out

    if dry:
        out.update(new=new, reason="no PR, not behind", pushed=True, deleted_remote=True)
        return out
    code, _, err = survey.git(path, "branch", "-m", new)
    if code != 0:
        out["reason"] = "branch -m failed: %s" % err
        return out
    code, _, err = survey.git(path, "push", "-u", "origin", new)
    if code != 0:
        survey.git(path, "branch", "-m", old)
        out.update(new=None, reason="push -u failed, local name rolled back: %s" % err)
        return out
    code, _, err = survey.git(path, "push", "origin", "--delete", old)
    if code != 0:
        out.update(new=new, pushed=True, reason="branch moved, old remote kept (delete failed): %s" % err)
        return out
    out.update(new=new, pushed=True, deleted_remote=True, reason="no PR, not behind")
    return out


def notify(entry, decision, dry):
    """Tell a running agent its branch moved, then check the broadcast landed."""
    if not decision["new"]:
        return "not needed"
    running = [pane for pane in entry["panes"] if pane["agent_status"] == "working"]
    if not running:
        return "no running agent"
    code, sha, _ = survey.git(entry["checkout"], "rev-parse", "--short", "HEAD")
    sha = sha.strip() if code == 0 else "HEAD"
    if decision["deleted_remote"]:
        remote = "upstream origin/%s at %s; old remote branch %s deleted" % (decision["new"], sha, decision["old"])
    elif decision["pushed"]:
        remote = "pushed origin/%s at %s; old remote branch %s kept" % (decision["new"], sha, decision["old"])
    else:
        remote = "local branch only (no upstream)"
    text = (
        "branch %s -> %s; %s; broadcast this to every subagent via write agent://all; never push the old name"
        % (decision["old"], decision["new"], remote)
    )
    if dry:
        return "would send to %s" % ", ".join(pane["pane_id"] for pane in running)
    for pane in running:
        survey.herdr("pane", "send-text", pane["pane_id"], text)
        survey.herdr("pane", "send-keys", pane["pane_id"], "enter")
    states = {pane["pane_id"]: "unconfirmed" for pane in running}
    for _ in range(NOTIFY_POLLS):
        time.sleep(NOTIFY_SLEEP)
        for pane in running:
            if states[pane["pane_id"]] == "confirmed":
                continue
            seen = survey.herdr("pane", "read", pane["pane_id"], "--source", "recent-unwrapped", "--lines", "40")
            if decision["new"] in seen or "agent://all" in seen:
                states[pane["pane_id"]] = "confirmed"
        if all(state == "confirmed" for state in states.values()):
            break
    return ", ".join("%s %s" % (pane_id, state) for pane_id, state in states.items())


def evidence(entry):
    """One line on what the workspace is on, for the report.

    The agent's own title first, then the file it is touching, then the tip
    commit: sibling worktrees of one repo often share history, so a commit says
    the least about which one is which.
    """
    title = next(
        (pane.get("title") for pane in entry.get("panes", [])
         if pane.get("title") and not labels.is_generated(pane["title"])),
        "",
    )
    touched = ""
    for row in entry.get("status") or []:
        parts = row.split(None, 1)
        if len(parts) == 2:
            touched = parts[1]
            break
    commit = entry["commits"][0].split(" ", 1)[-1] if entry.get("commits") else ""
    parts = [part[:60] for part in (title, touched, commit) if part]
    return " | ".join(parts[:2])


def table(rows):
    header = ("WS", "old", "new", "branch", "evidence")
    widths = [max(len(str(row[i])) for row in rows + [header]) for i in range(4)]
    line = lambda row: "  ".join(str(cell).ljust(widths[i]) if i < 4 else str(cell) for i, cell in enumerate(row))
    out = [line(header), "  ".join("-" * width for width in widths) + "  " + "-" * 8]
    out.extend(line(row) for row in rows)
    return "\n".join(out)


def apply_one(entry, label, dry, no_notify):
    if entry["label"] != label and not dry:
        survey.herdr("workspace", "rename", entry["workspace_id"], label)
    with repo_lock(entry.get("repo")):
        decision = decide(entry, label, dry)
    if no_notify:
        return decision, "skipped"
    return decision, notify(entry, decision, dry)



def herdr_json(*args):
    """Ask herdr for JSON; the caller's environment decides which session answers."""
    done = subprocess.run(["herdr", *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit("herdr %s failed: %s" % (" ".join(args), done.stderr.strip()))
    return json.loads(done.stdout)["result"]


REGISTRY = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "summon-the-overlord" / "worktrees.json"


def owned_paths():
    """Worktrees the overlord registers as its own; empty when it has spawned none."""
    if not REGISTRY.exists():
        return set()
    try:
        data = json.loads(REGISTRY.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit("registry unreadable (%s): %s" % (REGISTRY, error))
    if not isinstance(data, dict):
        raise SystemExit("registry is not an object (%s)" % REGISTRY)
    return {str(Path(path)) for path in data}

def drop_foreign(plan):
    """Keep only plans whose workspace the overlord registered as its own."""
    owned = owned_paths()
    paths = {(ws.get("worktree") or {}).get("checkout_path", ""): ws["workspace_id"] for ws in herdr_json("workspace", "list")["workspaces"]}
    keep = {ws for path, ws in paths.items() if str(Path(path).resolve()) in owned}
    kept = {ws: label for ws, label in plan.items() if ws in keep}
    for ws in plan:
        if ws not in kept:
            print("skip %s: not registered as an overlord worktree" % ws, file=sys.stderr)
    return kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", help="JSON plan — {workspace_id: label} — as a file path or inline JSON")
    parser.add_argument("--state", default="herdr-survey.json", help="survey.py output to read facts from")
    parser.add_argument("--json", default="herdr-applied.json", help="where to write the outcome")
    parser.add_argument("--apply", action="store_true", help="actually change herdr and git")
    parser.add_argument("--no-notify", action="store_true", help="skip the message to running agents")
    parser.add_argument("--only-mine", action="store_true", help="only worktrees the overlord registered")
    args = parser.parse_args(argv)
    dry = not args.apply

    with open(args.state) as handle:
        state = {entry["workspace_id"]: entry for entry in json.load(handle)["targets"]}
    plan = load_plan(args.plan)
    if args.only_mine:
        plan = list(drop_foreign(dict(plan)).items())

    problems = []
    for workspace_id, label in plan:
        if workspace_id not in state:
            problems.append("%s: not a linked-worktree target in %s" % (workspace_id, args.state))
            continue
        entry = state[workspace_id]
        if entry.get("error"):
            problems.append("%s: survey incomplete: %s" % (workspace_id, entry["error"]))
        for problem in labels.problems(label):
            problems.append("%s -> %s: %s" % (workspace_id, label, problem))
    if problems:
        sys.exit("plan refused:\n  " + "\n  ".join(problems))
    if not plan:
        print("empty plan: nothing to apply")
        return 0

    with ThreadPoolExecutor(max_workers=min(8, len(plan))) as pool:
        jobs = [(workspace_id, label, entry, pool.submit(apply_one, entry, label, dry, args.no_notify))
                for workspace_id, label in plan for entry in [state[workspace_id]]]
        results = [(workspace_id, label, entry, job.result()) for workspace_id, label, entry, job in jobs]

    rows = []
    for workspace_id, label, entry, (decision, told) in results:
        branch_cell = ("%s -> %s" % (decision["old"], decision["new"])
                       if decision["new"] else "kept: %s" % decision["reason"])
        rows.append((workspace_id, entry["label"], label, branch_cell, evidence(entry)))
        if told != "not needed" and not args.no_notify:
            rows.append(("", "", "", "", "notified: %s" % told))

    with open(args.json, "w") as handle:
        json.dump({"applied": not dry, "results": [
            {"workspace_id": workspace_id, "old_label": entry["label"], "new_label": label,
             "branch": decision, "notified": told}
            for workspace_id, label, entry, (decision, told) in results]}, handle, indent=2)
    print(table(rows))

    state_after = None if dry else verify.check()
    if state_after:
        for workspace_id, label, branch, note in state_after["rows"]:
            print("  %s  %-32s  %-34s  %s" % (workspace_id, label, branch, note))
        for failure in state_after["failures"]:
            print("  ! %s" % failure)
    print("\n%s. Outcome: %s%s" % (
        "dry run, nothing changed" if dry else "applied", args.json,
        "" if dry or not state_after["failures"] else ", %d problem(s) above" % len(state_after["failures"])))
    return 0 if dry or not state_after["failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
