---
name: prune-herdr-workspaces
description: >-
  Closes idle herdr workspaces and removes inactive Git worktrees without losing
  work. Use when the user asks to clean up, prune, tidy or close herdr workspaces
  or worktrees, e.g. "close all workspaces except the ones with a worktree",
  "remove inactive worktrees", "close workspaces with no running agent", or in
  French "ferme les workspaces", "nettoie les worktrees". Audits every workspace
  and checkout first, keeps anything with a working agent or uncommitted
  changes, and acts on everything else without asking.
  Invoke only on an explicit request, since it deletes checkouts.
compatibility: Requires herdr (terminal workspace manager), git, jq and bash.
disable-model-invocation: true
---

# Prune herdr workspaces

**Explicit invocation only.** Removing a worktree deletes its checkout; uncommitted changes in it
are gone for good. Where `disable-model-invocation` is ignored, this paragraph is the rule.

## 1. Audit (read-only)

```bash
"$SKILL_DIR/scripts/audit.sh"            # default root: ~/.herdr/worktrees
```

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this
`SKILL.md`. The script prints two TSV tables.

**Workspaces** — `kind` is `linked` (worktree workspace), `main` (a repo's primary checkout) or
`plain` (no repo). `note` flags `SELF` (the workspace running this session) and `MISSING` (linked
checkout folder already deleted).

**Checkouts** — every repo under the root: branch, `dirty` (changed files), commits reachable from
no remote, owning workspace. Special rows:

| Marker | Meaning | Action |
|---|---|---|
| `[CLONE]` | full clone, not a worktree; may be the parent of other worktrees | never remove |
| `BROKEN` | `.git` points at a gitdir the main repo pruned; git can't vouch for contents | report, don't `rm` |
| `NO-GIT` | plain directory (often build output) | delete (`rm -rf`) |

## 2. Classify

- **Active**: agent status `working` or `blocked`. Keep. Every other status (`idle`, `done`,
  `unknown`) is inactive: close it, main-checkout workspaces included.
- **SELF**: never close.
- **Removable**: `dirty=0`. Unpushed commits don't block removal: they survive on the branch in
  the main repo. Name the branch and commits in the report.
- **At risk**: `dirty>0`; uncommitted files die with the checkout.

Act on every inactive workspace and removable checkout without asking. Ask only for at-risk
checkouts: show the files that would be lost, offer skip or force; default skip.

## 3. Act

| Target | Command |
|---|---|
| Workspace with no linked checkout | `herdr workspace close <id>` |
| Workspace whose checkout is `MISSING` | `herdr workspace close <id>` |
| Removable worktree with a workspace | `herdr worktree remove --workspace <id>` (closes it too) |
| Removable worktree with no workspace | `git --git-dir="$(git -C <path> rev-parse --path-format=absolute --git-common-dir)" worktree remove <path>` |
| `NO-GIT` directory | `rm -rf <path>` |

Never pass `--force` to either remove command without the user's explicit go-ahead for that
checkout. Never close with `--group`.

`workspace_group_close_required` on close means the workspace is the main checkout of a repo that
still has linked worktree workspaces. `--group` would close those too, active agents included:
leave it open and say why.

A checkout under the root can be a worktree of a `[CLONE]` under the same root rather than of the
user's usual checkout; the `git-common-dir` form above resolves the right parent either way.

## 4. Verify and report

Re-run the audit. Report: closed, removed (with unpushed branches/commits), deleted `NO-GIT`,
kept-as-active, skipped-at-risk (with what's at risk), left-on-disk (`BROKEN`), and anything that
failed with its error.
