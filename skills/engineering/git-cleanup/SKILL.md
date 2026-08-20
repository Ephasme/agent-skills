---
name: git-cleanup
description: Safely cleans up git branches and worktrees — removes merged and squash-merged branches, prunes stale worktree registrations, removes obsolete clean worktrees, cleans up remote tracking refs, and protects unmerged commits and dirty worktrees. Use when the user asks to clean up git, prune/purge branches, remove stale worktrees, tidy a repo, wipe merged branches, or reset to default. Destructive — classifies first, confirms scope, rescues unsaved work, then cleans. Explicit invocation only.
disable-model-invocation: true
---

# git-cleanup

**Explicit invocation only.** It cleans up branches and worktrees, which must never happen on a guess. Some agents honour the `disable-model-invocation` frontmatter above; where that key is ignored, this paragraph is the rule — do not load this skill because a repo looks cluttered, only because the user explicitly asked.

Clean up git branches and worktrees without losing work. Requests range from the gentle ("prune merged branches and stale worktrees") to the absolute ("wipe everything except main"). The blunt approach — force-deleting non-default branches and running uninspected worktree commands — destroys unmerged commits, uncommitted edits in worktrees, and open pull requests.

The job is not "delete everything": it is **classify what is safe, confirm how far to go, rescue anything unsaved, then clean up in the correct order.**

## When to trigger

The user wants to delete, nuke, wipe, prune, tidy, or reset branches and worktrees — whether that is "remove merged branches and worktrees," "clean up stale worktrees," "tidy this repo," or "leave only main." Default branch is usually `main` but may be `master` or `trunk`; confirm if unclear.

## Core principles

### 1. Classify branches before deleting

`git branch --merged` misses **squash merges**: a squash lands a brand-new commit on the default branch, so the feature branch's commits never become ancestors and the branch appears unmerged forever. Blindly force-deleting "unmerged" branches or keeping only `--merged` branches is unreliable.

Decide each branch by **whether its work is already in the default branch**, detected empirically:

1. **Patch-id equivalence** — squash the branch's net diff onto its merge-base as one synthetic commit, then test with `git cherry` whether the default already contains that patch. Catches squash merges.
2. **Delta-over-touched-files fallback** — if the default branch later touched the same lines, compare the branch tip to the default over *only* the files changed by the branch; zero diff means the content is in the default.

A branch is:
- **`CONTAINED`** — work is already in the default branch (safe to delete).
- **`UNIQUE`** — has commits/content not in the default branch (deleting loses commits, recoverable only via local reflog, never on remote).

### 2. Classify worktrees before removing

Linked worktrees hold separate checkouts that may be active, obsolete, or disconnected:

- **`PRUNABLE`** — the worktree directory was deleted on disk, but git's administrative record in `.git/worktrees/` remains. Cleaned via `git worktree prune`.
- **`OBSOLETE (clean)`** — worktree is clean (no uncommitted or untracked changes) and points to a `CONTAINED` branch or a commit already in the default. Safe to remove via `git worktree remove <path>`.
- **`ACTIVE (unique/clean)`** — worktree points to a `UNIQUE` branch with unmerged commits. Keep unless the user explicitly orders an abandoned branch removed.
- **`DIRTY`** — worktree contains uncommitted modified, staged, or untracked files. `git worktree remove --force` destroys these permanently. Never remove without rescuing first.
- **`LOCKED`** — worktree is locked (`git worktree lock`). Must be inspected and unlocked (`git worktree unlock <path>`) before removal.
- **`MAIN`** — the primary working tree checkout. Never removed.

`scripts/classify.sh [default]` does all branch and worktree inspection read-only and prints formatted classification tables. Prefer it over manual probing.

## Workflow

### 1. Inventory — inspect the whole repository

```bash
echo "=== local branches ==="   && git branch
echo "=== remote branches =="   && git branch -r
echo "=== worktrees ==========" && git worktree list
echo "=== open PRs ===========" && (gh pr list 2>/dev/null || echo "(no gh / not a GitHub repo)")
```

### 2. Classify branches and worktrees

> **`$SKILL_DIR` is notation, not a variable that is already set.** It stands for this skill's own directory — the absolute path printed when the skill is loaded, or the directory holding this `SKILL.md`. Export it once (`SKILL_DIR=<that path>`) before running the command.

```bash
bash "$SKILL_DIR/scripts/classify.sh"        # auto-detects default (main/master/trunk)
# or: bash "$SKILL_DIR/scripts/classify.sh" master
```

Review both tables:
1. **Branches table:** identify `CONTAINED` vs `UNIQUE` branches, attached worktrees, and open PRs.
2. **Worktrees table:** identify `PRUNABLE`, `OBSOLETE`, `ACTIVE`, `DIRTY`, and `LOCKED` worktrees.

### 3. The four things that bite

1. **Squash-merged branches.** Handled by the classifier. Do not rely on bare `git branch --merged`.
2. **Dirty worktrees.** A worktree with modified or untracked files will lose those edits permanently if force-removed. Always inspect with `git -C <path> status` and rescue unsaved files before removing.
3. **Detached-HEAD worktrees.** May hold ad-hoc commits or experiments. Check whether the commit is in default (`git merge-base --is-ancestor <sha> <default>`) and whether the tree is clean.
4. **Open PRs.** Deleting a remote branch closes its GitHub PR. Verify whether the PR is actually obsolete (`CONTAINED`) or represents active open work before proposing remote deletion. Never close an active PR without explicit user authorization.

### 4. Confirm scope — offer tiers

Present the scope as a graduated choice with a clear recommendation:

- **Safe clean (recommended default):**
  1. Prune missing worktrees (`git worktree prune`).
  2. Remove clean, `OBSOLETE` worktrees whose branches are merged into default.
  3. Delete local `CONTAINED` branches (including squash-merged branches).
  4. Delete remote branches for `CONTAINED` work (if remote cleanup is desired).
  5. Prune stale remote tracking refs (`git fetch --prune`).
  6. Keeps all `UNIQUE` branches, active/dirty worktrees, and open PRs. Loses zero work.

- **Worktrees-only clean:**
  Prune missing worktree metadata and remove obsolete clean worktrees. Leaves all branches and remotes untouched.

- **Local-only clean:**
  Clean up local branches and worktrees, but never touch remote branches or PRs.

- **Full nuke / deep reset:**
  Remove all secondary worktrees and force-delete all non-default branches. Requires explicit authorization ("wipe everything except main, yes I know it closes PRs and removes unmerged work"), with consequences and unsaved work rescued first.

### 5. Rescue before removing unsaved or UNIQUE work

For any dirty worktree, detached-HEAD experiment, or `UNIQUE` branch authorized for removal, save a backup copy first:

```bash
mkdir -p ../git-cleanup-rescue
# Uncommitted modifications and staged changes:
git -C <worktree-path> diff HEAD > ../git-cleanup-rescue/<name>.patch
# Untracked files:
git -C <worktree-path> status --porcelain | grep '^??' | cut -c4- | while read -r f; do
  mkdir -p "../git-cleanup-rescue/untracked/$(dirname "$f")"
  cp -r "<worktree-path>/$f" "../git-cleanup-rescue/untracked/$f"
done
```

Note the SHA of any deleted branch (`was <sha>`); local reflog retains it temporarily.

### 6. Execute — exact order of operations

Always ensure you are in the primary checkout on the default branch before cleaning.

```bash
# a) Prune stale worktree metadata for deleted directories
git worktree prune

# b) Unlock any locked worktrees authorized for removal
git worktree unlock <path>

# c) Remove obsolete clean worktrees (frees their branches for deletion)
git worktree remove <path>
# (Only use `git worktree remove --force <path>` if dirty work was rescued in step 5)

# d) Delete local CONTAINED branches
git branch -d <branch>                      # standard merged branches
git branch -D <branch>                      # squash-CONTAINED (or authorized UNIQUE)

# e) Delete remote branches in scope (closes associated PRs)
git push origin --delete <branch> [<branch> ...]

# f) Prune stale remote-tracking references
git fetch --prune
```

Perform deletes by name based on the classification, rather than blind shell globs or pipes.

### 7. Verify

```bash
echo "=== remaining local branches ==="   && git branch
echo "=== remaining remote branches =="   && git branch -r
echo "=== remaining worktrees ==========" && git worktree list
```

## Safety rules

1. Never run `git worktree remove --force` or `git branch -D` on unclassified work.
2. `git worktree prune` is always safe: it only cleans records where the directory is already gone.
3. Keep the classifier read-only. Deciding and deleting require user-confirmed scope.
