#!/usr/bin/env python3
"""Check the live state after a rename: no placeholder label left, no duplicates,
and every branch that could be moved actually sits on its label.

Read-only. Exits 1 when a placeholder label or a duplicate remains.

    verify.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import labels
import survey


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", default="herdr-verified.json", help="where to write the check")
    args = parser.parse_args(argv)

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
        branch = branch if code == 0 and branch else "-"
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
        rows.append((ws["workspace_id"], ws["label"], branch, note))

    duplicates = {label: ids for label, ids in by_label.items() if len(ids) > 1}
    for label, ids in duplicates.items():
        failures.append("duplicate label %r on %s" % (label, ", ".join(ids)))

    width = max([len(row[1] or "-") for row in rows] + [3])
    for workspace_id, label, branch, note in rows:
        print("%s  %-*s  %-34s  %s" % (workspace_id, width, label, branch, note))
    with open(args.json, "w") as handle:
        json.dump({"rows": rows, "duplicates": duplicates, "failures": failures}, handle, indent=2)
    if failures:
        print("\n%d problem(s):\n  %s" % (len(failures), "\n  ".join(failures)))
        return 1
    print("\nclean: %d linked worktree(s), no placeholder label, no duplicate" % len(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
