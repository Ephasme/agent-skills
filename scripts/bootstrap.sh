#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: this repo plus the third-party
# skills that are tracked here only by name, and the MCP servers rendered into
# every agent that is installed.
#
# Layout: content in ~/.agents/skills/<name>, and a relative symlink per skill per
# profile at ~/.claude-{perso,work}/skills/<name>. The CLI produces the store on
# its own — with no --agent flag it adds its "universal" agents, whose skills dir
# *is* ~/.agents/skills, which is what makes it symlink instead of copy — and it
# links the agents it detects. It does not detect ~/.claude-{perso,work}, so
# installing a skill activates it in neither profile. That is deliberate: each
# profile links only the skills that belong in it, and work and perso do not get
# the same set.
#
# So this script rebuilds the store only. The per-profile symlinks are yadm content
# (they are the sole record of which profile gets which skill), so `yadm clone`
# restores them; they simply dangle until this script has populated the store.
# Anything left unlinked afterwards is reported at the end.
#
# Every install runs with CLAUDE_CONFIG_DIR cleared, so the incidental claude-code
# link lands in ~/.claude/skills — a directory no profile reads — rather than in
# whichever profile happened to be active.
#
# This calls npx directly and deliberately NOT the ~/.local/bin/skills wrapper,
# even though the wrapper exists to make exactly these symlinks. The wrapper
# activates whatever this run adds to an empty .skill-lock.json — which on a fresh
# machine is everything, in both profiles. yadm has already restored the real
# per-profile selection by this point, so letting it run here would flatten it.
#
# Usage: scripts/bootstrap.sh
set -euo pipefail

REPO=git@github.com:Ephasme/agent-skills.git
STORE=$HOME/.agents/skills

skills_add() { env -u CLAUDE_CONFIG_DIR npx -y skills add "$@" -g --yes; }

echo "==> $REPO"
skills_add "$REPO" --skill '*'

# The one third-party skill, from its own upstream so it keeps receiving updates.
echo "==> third-party skills"
skills_add kunchenguid/gnhf --skill gnhf

# MCP servers. Deliberately after the skills and independent of them: this renders
# mcp/servers.json into each agent's own config format. It needs no credentials —
# what it writes are references to environment variables, not their values — so it
# runs correctly before `yadm decrypt` has restored ~/.config/secrets.zsh.
echo "==> MCP servers"
node "$(dirname "$0")/install-mcp.mjs"

# A skill in the store that no profile links is loaded by neither Claude. On a
# fresh clone that means yadm did not carry the link, or the skill is new since.
echo
unlinked=()
for path in "$STORE"/*/; do
  name=$(basename "$path")
  [ -e "$HOME/.claude-perso/skills/$name" ] || [ -e "$HOME/.claude-work/skills/$name" ] \
    || unlinked+=("$name")
done
if [ ${#unlinked[@]} -gt 0 ]; then
  echo "In the store but linked by no profile — activate what you want, per profile:"
  for name in "${unlinked[@]}"; do
    echo "  ln -s ../../.agents/skills/$name ~/.claude-perso/skills/$name"
  done
fi

echo
echo "Done. Verify with: agents-doctor"
