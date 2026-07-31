#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: this repo into both Claude
# profiles, plus the third-party skills that are tracked here only by name.
#
# Uses the `skills` wrapper at ~/.local/bin/skills (yadm-tracked), which runs the
# upstream CLI once per profile with CLAUDE_CONFIG_DIR set and pairs claude-code
# with a universal store-agent so upstream symlinks natively into the shared
# store. Never pass -a here: that suppresses the store-agent injection and each
# profile gets its own full copy instead of a symlink.
#
# Result: ~/.agents/skills/<name> holds the content, and
# ~/.claude-{perso,work}/skills/<name> are relative symlinks at it.
#
# Usage: scripts/bootstrap.sh
set -euo pipefail

REPO=Ephasme/agent-skills

command -v skills >/dev/null || {
  echo "skills wrapper not found at ~/.local/bin/skills — run 'yadm clone' first." >&2
  exit 1
}

# The upstream CLI probes `gh auth status` to decide SSH vs HTTPS for the private
# clone, and a plain terminal has no profile env. Point it at the perso account.
export GH_CONFIG_DIR="${GH_CONFIG_DIR:-$HOME/.config/gh-perso}"

echo "==> $REPO"
skills add "$REPO" -s '*' -y

# Third-party skills, from their own upstreams so they keep receiving updates.
echo "==> third-party skills"
skills add vercel-labs/skills       -s find-skills -y
skills add vercel-labs/agent-skills -s web-design-guidelines -y
skills add tamagui/tamagui          -s tamagui -y
skills add kunchenguid/gnhf         -s gnhf -y

echo
echo "Done. Verify with: skills list"
