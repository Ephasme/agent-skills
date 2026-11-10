#!/usr/bin/env python3
"""The mechanical half of naming: what a label may and may not be.

Naming itself is judgement and stays with the model. This module only rejects a
label that breaks a stated rule, so a plan either passes or is refused before
anything reaches herdr or git.

    labels.py wallet-replaces-columns invoicing-microservice   # exit 1 on problems
"""

from __future__ import annotations

import re
import sys

KEBAB = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
# herdr names a fresh worktree `<adjective>-<noun>-<hex>`, as the label
# `worktree-brave-forest-5e18` and the branch `worktree/brave-forest-5e18`. Both
# are a placeholder, not a name.
GENERATED = re.compile(r"^worktree[-/][a-z]+-[a-z]+-[0-9a-f]{4,}$")
MIN_WORDS, MAX_WORDS, MAX_CHARS = 2, 4, 42
# A label says what the work is about. These say nothing.
GENERIC = {
    "worktree", "branch", "wip", "tmp", "temp", "misc", "stuff", "changes",
    "update", "updates", "fix", "fixes", "chore", "task", "tasks", "work",
    "dev", "feature", "refactor", "cleanup", "session", "agent", "test",
    "tests", "todo", "init", "various", "other",
}


def is_generated(name):
    """True when this is herdr's placeholder name rather than one somebody chose."""
    return bool(name) and bool(GENERATED.match(name.strip()))


def problems(label):
    """Every reason this label cannot be used, in the order it was checked."""
    if not label or not label.strip():
        return ["empty label"]
    label = label.strip()
    out = []
    if not KEBAB.match(label):
        out.append("not kebab-case (lowercase words joined by single hyphens)")
    words = label.split("-")
    if not MIN_WORDS <= len(words) <= MAX_WORDS:
        out.append("%d words, must be %d-%d" % (len(words), MIN_WORDS, MAX_WORDS))
    if len(label) > MAX_CHARS:
        out.append("%d chars, over %d" % (len(label), MAX_CHARS))
    if is_generated(label):
        out.append("herdr's generated placeholder name")
    generic = sorted(word for word in words if word in GENERIC)
    if generic:
        out.append("generic word(s): %s" % ", ".join(generic))
    return out


def main(argv):
    bad = 0
    for label in argv:
        found = problems(label)
        print("%-40s %s" % (label, "ok" if not found else "; ".join(found)))
        bad += bool(found)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
