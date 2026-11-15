#!/usr/bin/env python3
"""Check the live state after a rename: no placeholder label left, no duplicates,
and every branch that could be moved actually sits on its label.

Read-only, and importable: apply.py calls `check()` so the run ends verified
instead of needing a second command.

    verify.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import labels
import survey


def check():
    workspaces = survey.herdr_json("workspace", "list")["workspaces"]
    by_label = {}
    rows, failures = [], []
    for ws in workspaces:
        worktree = ws.get("worktree") or {}
        if not worktree.get("is_linked_worktree"):
            continue
        # Only targets: two primary checkouts of one repo share a name by design.
        by_label.setdefault(ws.get("label"), []).append(ws["workspace_id"])
        path = worktree.get("checkout_path")
        if not path or not os.path.isdir(path):
            rows.append((ws["workspace_id"], ws.get("label"), "-", "checkout missing"))
            failures.append("%s: checkout missing (%s)" % (ws["workspace_id"], path))
            continue
        code, branch, _ = survey.git(path, "branch", "--show-current")
        branch = branch.strip() if code == 0 and branch.strip() else "-"
        if labels.is_generated(ws.get("label")):
            note = "placeholder label"
            failures.append("%s: label is herdr's placeholder" % ws["workspace_id"])
        elif branch != "worktree/" + ws["label"] and not labels.is_generated(branch):
            note = "branch is a chosen name"
        elif branch != "worktree/" + ws["label"]:
            note = "branch still placeholder"
            failures.append("%s: branch %s not worktree/%s" % (ws["workspace_id"], branch, ws["label"]))
        else:
            note = "ok"
        rows.append((ws["workspace_id"], ws.get("label"), branch, note))

    duplicates = {label: ids for label, ids in by_label.items() if len(ids) > 1}
    for label, ids in duplicates.items():
        failures.append("duplicate label %r on %s" % (label, ", ".join(ids)))
    return {"rows": rows, "duplicates": duplicates, "failures": failures}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default="herdr-verified.json", help="where to write the check")
    args = parser.parse_args(argv)

    state = check()
    width = max([len(row[1] or "-") for row in state["rows"]] + [3])
    for workspace_id, label, branch, note in state["rows"]:
        print("%s  %-*s  %-34s  %s" % (workspace_id, width, label, branch, note))
    with open(args.json, "w") as handle:
        json.dump(state, handle, indent=2)
    if state["failures"]:
        print("\n%d problem(s):\n  %s" % (len(state["failures"]), "\n  ".join(state["failures"])))
        return 1
    print("\nclean: %d linked worktree(s), no placeholder label, no duplicate" % len(state["rows"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
