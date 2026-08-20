#!/usr/bin/env bash
# Read-only git classifier for branches and worktrees (git-cleanup skill).
#
# For each branch and worktree, it answers the questions that decide whether
# they are safe to delete or remove:
#   1. Branches: "is this branch's work already in the default branch?"
#      (including squash merges that `git branch --merged` misses).
#   2. Worktrees: "is this worktree stale, obsolete, dirty, prunable, or locked?"
#
# It never deletes anything. Run it, read the tables, then decide.
#
# Usage:  classify.sh [default-branch]
#   default-branch defaults to origin/HEAD's target, else main/master/trunk.

set -uo pipefail

default="${1:-}"
if [ -z "$default" ]; then
  default=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD 2>/dev/null | sed 's@^origin/@@')
fi
if [ -z "$default" ]; then
  for cand in main master trunk; do
    if git show-ref --verify --quiet "refs/heads/$cand"; then default="$cand"; break; fi
  done
fi
if [ -z "$default" ]; then
  echo "Could not determine the default branch — pass it explicitly:" >&2
  echo "  classify.sh <default>" >&2
  exit 1
fi

# Compare against the remote tip if it exists — it's the source of truth for
# what has actually merged (and where squash commits land).
ref="$default"
git show-ref --verify --quiet "refs/remotes/origin/$default" && ref="origin/$default"

# Classify branch content: returns "CONTAINED" or "UNIQUE"
classify_branch() {
  local b="$1"
  local base
  base=$(git merge-base "$ref" "$b" 2>/dev/null) || { echo "NO-BASE"; return; }
  local ahead
  ahead=$(git rev-list --count "$base..$b")
  if [ "$ahead" -eq 0 ]; then
    echo "CONTAINED"
    return
  fi
  # Pass 1: patch-id equivalence. Squash the branch's whole net diff onto
  # its merge-base as one synthetic commit, then ask `git cherry` whether the
  # default already contains an equivalent patch (catches squash merges).
  local tree squash
  tree=$(git rev-parse "$b^{tree}" 2>/dev/null) || { echo "UNIQUE"; return; }
  squash=$(git commit-tree "$tree" -p "$base" -m _ 2>/dev/null)
  if [ -n "$squash" ] && git cherry "$ref" "$squash" 2>/dev/null | grep -q '^-'; then
    echo "CONTAINED"
    return
  fi
  # Pass 2: delta over touched files fallback (for when default re-touched lines).
  local files delta
  files=$(git diff --name-only "$base" "$b" 2>/dev/null)
  if [ -n "$files" ]; then
    delta=$(git diff "$ref" "$b" -- $files 2>/dev/null | wc -l | tr -d ' ')
    if [ "$delta" -eq 0 ]; then
      echo "CONTAINED"
      return
    fi
  fi
  echo "UNIQUE"
}

# Worktree path for a given branch (empty if not checked out anywhere).
wt_for() {
  git worktree list --porcelain | awk -v b="refs/heads/$1" '
    $1=="worktree"{p=$2}
    $1=="branch" && $2==b {print p; exit}'
}

# Main worktree root
main_wt=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

printf "Default branch: %s   (comparing against %s)\n\n" "$default" "$ref"

echo "=== BRANCHES ==="
printf "%-36s %-11s %-6s %-24s %s\n" "BRANCH" "VERDICT" "ahead" "WORKTREE(dirty)" "PR"

git for-each-ref --format='%(refname:short)' refs/heads/ | while IFS= read -r b; do
  [ "$b" = "$default" ] && continue

  base=$(git merge-base "$ref" "$b" 2>/dev/null || true)
  ahead="-"
  if [ -n "$base" ]; then
    ahead=$(git rev-list --count "$base..$b")
  fi

  verdict=$(classify_branch "$b")

  wt=$(wt_for "$b")
  wtcol="-"
  if [ -n "$wt" ]; then
    if [ -d "$wt" ]; then
      dirty=$(git -C "$wt" status --porcelain 2>/dev/null | awk 'END { print NR }')
      wtcol="$(basename "$wt")($dirty)"
    else
      wtcol="$(basename "$wt")(missing)"
    fi
  fi

  pr="-"
  if command -v gh >/dev/null 2>&1; then
    found=$(gh pr list --head "$b" --state open --json number -q '.[0].number' 2>/dev/null || true)
    [ -n "$found" ] && pr="#$found"
  fi

  printf "%-36s %-11s %-6s %-24s %s\n" "$b" "$verdict" "$ahead" "$wtcol" "$pr"
done

echo
echo "=== WORKTREES ==="
printf "%-32s %-24s %-22s %s\n" "WORKTREE" "BRANCH/HEAD" "STATUS" "RECOMMENDATION"

# Parse git worktree list --porcelain
wt_path=""
wt_head=""
wt_branch=""
wt_locked=""
wt_prunable=""
is_first=1

process_worktree() {
  [ -z "$wt_path" ] && return
  local display_name
  display_name="$(basename "$wt_path")"
  if [ "$is_first" -eq 1 ]; then
    display_name="$display_name (main)"
    is_first=0
  fi

  local branch_display="detached"
  if [ -n "$wt_branch" ]; then
    branch_display="${wt_branch#refs/heads/}"
  elif [ -n "$wt_head" ]; then
    branch_display="detached(${wt_head:0:7})"
  fi

  local status="ACTIVE"
  local rec="keep"

  if [ "$is_first" -eq 0 ] && [ "$wt_path" = "$main_wt" ]; then
    status="MAIN"
    rec="keep (main checkout)"
  elif [ -n "$wt_prunable" ] || [ ! -d "$wt_path" ]; then
    status="PRUNABLE (missing dir)"
    rec="git worktree prune"
  elif [ -n "$wt_locked" ]; then
    status="LOCKED ($wt_locked)"
    rec="inspect / unlock before remove"
  else
    local dirty_counts dirty_mod dirty_untracked dirty_total
    dirty_counts=$(git -C "$wt_path" status --porcelain 2>/dev/null | awk '
      BEGIN { mod=0; unt=0 }
      /^\?\?/ { unt++; next }
      { mod++ }
      END { print mod, unt }
    ')
    read -r dirty_mod dirty_untracked <<< "${dirty_counts:-0 0}"
    dirty_total=$((dirty_mod + dirty_untracked))

    local content_status="UNIQUE"
    if [ -n "$wt_branch" ]; then
      local bname="${wt_branch#refs/heads/}"
      if [ "$bname" = "$default" ]; then
        content_status="CONTAINED"
      else
        content_status=$(classify_branch "$bname")
      fi
    elif [ -n "$wt_head" ]; then
      if git merge-base --is-ancestor "$wt_head" "$ref" 2>/dev/null; then
        content_status="CONTAINED"
      fi
    fi

    if [ "$dirty_total" -gt 0 ]; then
      status="DIRTY ($dirty_mod mod, $dirty_untracked untracked)"
      if [ "$content_status" = "CONTAINED" ]; then
        rec="rescue dirty files -> remove"
      else
        rec="active work (rescue if removing)"
      fi
    else
      if [ "$content_status" = "CONTAINED" ]; then
        status="OBSOLETE (merged/clean)"
        rec="safe to remove"
      else
        status="ACTIVE (unique/clean)"
        rec="keep (or remove if abandoned)"
      fi
    fi
  fi

  printf "%-32s %-24s %-22s %s\n" "$display_name" "$branch_display" "$status" "$rec"
}

while IFS= read -r line || [ -n "$line" ]; do
  if [[ "$line" =~ ^worktree[[:space:]]+(.*)$ ]]; then
    process_worktree
    wt_path="${BASH_REMATCH[1]}"
    wt_head=""
    wt_branch=""
    wt_locked=""
    wt_prunable=""
  elif [[ "$line" =~ ^HEAD[[:space:]]+(.*)$ ]]; then
    wt_head="${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^branch[[:space:]]+(.*)$ ]]; then
    wt_branch="${BASH_REMATCH[1]}"
  elif [[ "$line" =~ ^locked([[:space:]]+(.*))?$ ]]; then
    wt_locked="${BASH_REMATCH[2]:-yes}"
  elif [[ "$line" =~ ^prunable[[:space:]]+(.*)$ ]]; then
    wt_prunable="${BASH_REMATCH[1]}"
  fi
done < <(git worktree list --porcelain)
process_worktree
