#!/usr/bin/env bash
# Read-only. Prints one TSV row per herdr workspace and per checkout under the worktree root.
# Usage: audit.sh [worktree-root]   (default: ~/.herdr/worktrees)
set -uo pipefail
root=${1:-$HOME/.herdr/worktrees}
self=${HERDR_WORKSPACE_ID:-}

ws_json=$(herdr workspace list) || { echo "herdr workspace list failed" >&2; exit 1; }

echo "# WORKSPACES: id  label  agent  kind  checkout  note"
jq -r --arg self "$self" '.result.workspaces[] |
  [ .workspace_id, .label, .agent_status,
    (if .worktree == null then "plain"
     elif .worktree.is_linked_worktree then "linked" else "main" end),
    (.worktree.checkout_path // "-"),
    (if .workspace_id == $self then "SELF" else "" end) ] | @tsv' <<<"$ws_json" |
while IFS=$'\t' read -r id label agent kind path note; do
  [ "$kind" = linked ] && [ ! -d "$path" ] && note="${note:+$note,}MISSING"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$id" "$label" "$agent" "$kind" "$path" "$note"
done

echo "# CHECKOUTS: path  branch  dirty  commits_on_no_remote  workspace"
seen=""
while IFS= read -r -d '' gitfile; do
  p=$(dirname "$gitfile")
  top=$(git -C "$p" rev-parse --show-toplevel 2>/dev/null)
  if [ -z "$top" ] || [ "$top" != "$p" ]; then
    printf '%s\tBROKEN\t-\t-\t-\n' "$p"   # .git points at a gitdir that no longer exists
    continue
  fi
  case " $seen " in *" $p "*) continue ;; esac
  seen="$seen $p"
  kind=""; [ -d "$p/.git" ] && kind=" [CLONE]"   # full clone, not a worktree: never remove
  b=$(git -C "$p" branch --show-current); b=${b:-DETACHED}
  d=$(git -C "$p" status --porcelain | wc -l | tr -d ' ')
  n=$(git -C "$p" rev-list --count HEAD --not --remotes 2>/dev/null || echo "?")
  w=$(jq -r --arg p "$p" '.result.workspaces[] | select(.worktree.checkout_path == $p) |
        "\(.workspace_id):\(.agent_status)"' <<<"$ws_json")
  printf '%s\t%s\t%s\t%s\t%s\n' "$p" "$b$kind" "$d" "$n" "${w:-none}"
done < <(find "$root" -mindepth 2 -maxdepth 3 -name .git -print0 2>/dev/null)

# Directories under the root with no .git at all (e.g. leftover build output)
find "$root" -mindepth 2 -maxdepth 2 -type d ! -exec test -e '{}/.git' \; -print 2>/dev/null |
while IFS= read -r p; do
  git -C "$p" rev-parse 2>/dev/null && continue
  printf '%s\tNO-GIT\t-\t-\t-\n' "$p"
done
