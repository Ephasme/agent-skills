#!/usr/bin/env python3
"""Apply a naming plan: rename the workspace, move the branch when that is safe,
tell the agent that was moved, and print the report table.

The plan — one label per workspace — is the model's decision. Everything that
can be decided by a rule lives here instead, because these rules are
irreversible when got wrong: a branch name is pushed and its old remote ref
deleted, so every guard has to pass before that happens.

    apply.py plan.json               # dry run: every decision, nothing changed
    apply.py plan.json --apply       # do it
    apply.py plan.json --apply --no-notify
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time

import labels
import survey


def sh(cmd, cwd=None):
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def load_plan(path):
    with open(path) as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        pairs = list(data.items())
    else:
        pairs = [(row["workspace_id"], row["label"]) for row in data]
    seen = {}
    for workspace_id, label in pairs:
        if label in seen:
            sys.exit("plan gives %s the same label as %s: labels must be distinct" % (workspace_id, seen[label]))
        seen[label] = workspace_id
    return pairs


def repo_slug(path):
    """owner/repo for gh, which cannot parse the ssh alias the remote uses."""
    code, url, _ = survey.git(path, "remote", "get-url", "origin")
    if code != 0 or not url:
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


def open_prs(path, slug, branch):
    """PRs on this branch name in any state, or None when gh cannot answer."""
    code, out, _ = sh(["gh", "pr", "list", "-R", slug, "--head", branch, "--state", "all", "--json", "number,state,url"])
    if code != 0:
        return None
    try:
        return json.loads(out or "[]")
    except ValueError:
        return None


def decide(entry, label, dry, log):
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
    code, _, _ = survey.git(path, "show-ref", "--verify", "--quiet", "refs/heads/" + new)
    if code == 0:
        out["reason"] = "local branch %s already exists" % new
        return out
    code, remote_refs, _ = survey.git(path, "ls-remote", "--heads", "origin", new)
    if code != 0:
        out["reason"] = "cannot reach origin to check %s" % new
        return out
    if remote_refs:
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
        log("    branch -m %s" % new)
        return out

    slug = repo_slug(path)
    if not slug:
        out["reason"] = "no origin remote"
        return out
    prs = open_prs(path, slug, old)
    if prs is None:
        out["reason"] = "gh could not list PRs for %s" % slug
        return out
    if prs:
        out["reason"] = "PR on %s: %s" % (old, ", ".join("#%s %s" % (pr["number"], pr["state"]) for pr in prs))
        return out
    code, _, err = survey.git(path, "fetch", "origin", old)
    if code != 0:
        out["reason"] = "git fetch origin %s failed: %s" % (old, err)
        return out
    code, out_behind, _ = survey.git(path, "rev-list", "--count", "HEAD..@{u}")
    if code == 0 and out_behind and int(out_behind) > 0:
        out["reason"] = "behind upstream by %s commits" % out_behind
        return out

    if dry:
        out.update(new=new, reason="no PR, not behind", pushed=True, deleted_remote=True)
        return out
    code, _, err = survey.git(path, "branch", "-m", new)
    if code != 0:
        out["reason"] = "branch -m failed: %s" % err
        return out
    log("    branch -m %s" % new)
    code, _, err = survey.git(path, "push", "-u", "origin", new)
    if code != 0:
        out.update(new=None, reason="push -u failed, old remote kept: %s" % err)
        return out
    log("    push -u origin %s" % new)
    code, _, err = survey.git(path, "push", "origin", "--delete", old)
    if code != 0:
        out.update(new=new, pushed=True, reason="old remote kept, delete failed: %s" % err)
        return out
    log("    push origin --delete %s" % old)
    out.update(new=new, pushed=True, deleted_remote=True, reason="no PR, not behind")
    return out


def notify(entry, decision, dry, log):
    """Tell a running agent its branch moved, then check the broadcast landed."""
    if not decision["deleted_remote"]:
        return "not needed"
    running = [pane for pane in entry["panes"] if pane["agent_status"] == "working"]
    if not running:
        return "no running agent"
    code, sha, _ = survey.git(entry["checkout"], "rev-parse", "--short", "HEAD")
    sha = sha if code == 0 else "HEAD"
    text = (
        "branch %s -> %s; upstream origin/%s at %s; old remote branch %s deleted; "
        "broadcast this to every subagent via write agent://all; never push the old name"
        % (decision["old"], decision["new"], decision["new"], sha, decision["old"])
    )
    if dry:
        return "would send to %s" % ", ".join(pane["pane_id"] for pane in running)
    states = []
    for pane in running:
        survey.herdr("pane", "send-text", pane["pane_id"], text)
        survey.herdr("pane", "send-keys", pane["pane_id"], "enter")
        log("    notified %s" % pane["pane_id"])
        landed = "unconfirmed"
        for _ in range(6):
            time.sleep(2)
            seen = survey.clean(survey.herdr("pane", "read", pane["pane_id"], "--source", "recent-unwrapped", "--lines", "40"))
            if any(decision["new"] in row or "broadcast" in row.lower() for row in seen):
                landed = "confirmed"
                break
        states.append("%s %s" % (pane["pane_id"], landed))
    return ", ".join(states)


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
    widths = [max(len(str(row[i])) for row in rows + [("WS", "old", "new", "branch", "evidence")]) for i in range(5)]
    line = lambda row: "  ".join(str(cell).ljust(widths[i]) if i < 4 else str(cell) for i, cell in enumerate(row))
    out = [line(("WS", "old", "new", "branch", "evidence")), line(tuple("-" * w for w in widths))]
    out.extend(line(row) for row in rows)
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", help="JSON plan: {workspace_id: label} or [{workspace_id, label}]")
    parser.add_argument("--state", default="herdr-survey.json", help="survey.py output to read facts from")
    parser.add_argument("--json", default="herdr-applied.json", help="where to write the outcome")
    parser.add_argument("--apply", action="store_true", help="actually change herdr and git")
    parser.add_argument("--no-notify", action="store_true", help="skip the message to running agents")
    args = parser.parse_args(argv)
    dry = not args.apply

    with open(args.state) as handle:
        state = {entry["workspace_id"]: entry for entry in json.load(handle)["targets"]}
    plan = load_plan(args.plan)

    problems = []
    for workspace_id, label in plan:
        if workspace_id not in state:
            problems.append("%s: not a linked-worktree target in %s" % (workspace_id, args.state))
        for problem in labels.problems(label):
            problems.append("%s -> %s: %s" % (workspace_id, label, problem))
    if problems:
        sys.exit("plan refused:\n  " + "\n  ".join(problems))

    results, rows = [], []
    for workspace_id, label in plan:
        entry = state[workspace_id]
        print("%s %s -> %s" % (workspace_id, entry["label"], label) + ("   (dry run)" if dry else ""))
        if entry["label"] != label:
            if not dry:
                survey.herdr("workspace", "rename", workspace_id, label)
                print("    renamed workspace")
        decision = decide(entry, label, dry, print)
        told = "not needed" if args.no_notify else notify(entry, decision, dry, print)
        branch_cell = (
            "%s -> %s" % (decision["old"], decision["new"]) if decision["new"] else "kept: %s" % decision["reason"]
        )
        results.append({
            "workspace_id": workspace_id,
            "old_label": entry["label"],
            "new_label": label,
            "branch": decision,
            "notified": told,
        })
        rows.append((workspace_id, entry["label"], label, branch_cell, evidence(entry)))

    with open(args.json, "w") as handle:
        json.dump({"applied": not dry, "results": results}, handle, indent=2)
    print("\n" + table(rows))
    print("\n%s. Outcome: %s" % ("dry run, nothing changed" if dry else "applied", args.json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
