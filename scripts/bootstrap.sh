#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: this repo into both Claude
# profiles, plus the third-party skills that are tracked here only by name.
#
# Everything lands in the canonical store ~/.agents/skills/<name>, with each
# agent's own skills dir symlinked at it.
#
# Usage: scripts/bootstrap.sh [extra-agent ...]
#   scripts/bootstrap.sh                 # both Claude profiles only
#   scripts/bootstrap.sh codex cursor    # ...and those agents too
set -euo pipefail

REPO=Ephasme/agent-skills

command -v skills >/dev/null || {
  echo "skills CLI not found. Install it: npm i -g skills" >&2
  exit 1
}

# The CLI probes `gh auth status` to decide SSH vs HTTPS for the private clone,
# and a plain terminal has no profile env. Point it at the perso account.
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-perso}"

for profile in perso work; do
  dir="$HOME/.claude-$profile"
  [ -d "$dir" ] || { echo "skip: $dir does not exist"; continue; }
  echo "==> $REPO -> $dir"
  CLAUDE_CONFIG_DIR="$dir" skills add "$REPO" -g -a claude-code -s '*' -y
done

for agent in "$@"; do
  echo "==> $REPO -> $agent"
  skills add "$REPO" -g -a "$agent" -s '*' -y
done

# Third-party skills, from their own upstreams so they keep receiving updates.
# Mirrors ~/.agents/.skill-lock.json; keep the two in step.
echo "==> third-party skills"
skills add vercel-labs/skills          -g -a claude-code -s find-skills -y
skills add vercel-labs/agent-skills    -g -a claude-code -s web-design-guidelines -y
skills add tamagui/tamagui             -g -a claude-code -s tamagui -y
skills add kunchenguid/gnhf            -g -a claude-code -s gnhf -y

echo
echo "Done. Verify with: skills list"
