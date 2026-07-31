#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: this repo into both Claude
# profiles, plus the third-party skills that are tracked here only by name, plus
# the MCP servers rendered into every agent that is installed.
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

# Self-hosted Forgejo. The CLI has no shorthand for it, so the full URL is the
# source string; it takes the generic git path and is cloned with plain `git
# clone`, using the git-ssh.loup-peluso.com block in ~/.ssh/config for the key
# and the :2222 port. No forge API and no token involved.
REPO=ssh://git@git-ssh.loup-peluso.com:2222/loup/agent-skills.git

command -v skills >/dev/null || {
  echo "skills wrapper not found at ~/.local/bin/skills — run 'yadm clone' first." >&2
  exit 1
}

echo "==> $REPO"
skills add "$REPO" -s '*' -y

# Third-party skills, from their own upstreams so they keep receiving updates.
echo "==> third-party skills"
skills add vercel-labs/skills       -s find-skills -y
skills add vercel-labs/agent-skills -s web-design-guidelines -y
skills add tamagui/tamagui          -s tamagui -y
skills add kunchenguid/gnhf         -s gnhf -y

# MCP servers. Deliberately after the skills and independent of them: this renders
# mcp/servers.json into each agent's own config format. It needs no credentials —
# what it writes are references to environment variables, not their values — so it
# runs correctly before `yadm decrypt` has restored ~/.config/secrets.zsh.
echo "==> MCP servers"
node "$(dirname "$0")/install-mcp.mjs"

echo
echo "Done. Verify with: skills list && node scripts/install-mcp.mjs --list"
