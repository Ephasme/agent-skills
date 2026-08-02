#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: every skill recorded in
# ~/.agents/.skill-lock.json — this repo's own skills and every third-party one,
# tracked there by name — plus the MCP servers rendered into every agent that is
# installed.
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
# The install list is derived from the lock rather than hardcoded, so a package
# added to it is reinstalled without this script also being edited by hand. The
# lock's top-level "skills" key holds a name -> metadata OBJECT (siblings are
# "version", an int, plus "dismissed" and "lastSelectedAgents") — iterating the
# file's top level instead of its "skills" key walks the wrong thing entirely.
# Each entry's "source" field is already in the exact form `skills add` expects
# for its "sourceType" (the SSH URL for this repo's own git-type entries, the bare
# "owner/repo" shorthand for github-type ones like gnhf and brainstorming) — jq
# groups entries by that field and one `add` call per group covers every skill
# that shares it, in one pass over whatever the lock currently records. Deriving
# the list this way is the actual fix here: `brainstorming` (from obra/superpowers)
# was in the lock and still missing after the 2026-08-01 restore, because the old
# hardcoded list only ever replayed this repo's skills plus gnhf and had no way to
# notice a third package had since been added.
#
# Usage: scripts/bootstrap.sh
set -euo pipefail

STORE=$HOME/.agents/skills
LOCK=$HOME/.agents/.skill-lock.json

command -v jq >/dev/null 2>&1 || {
  echo "error: jq is required to derive the install list from $LOCK (it's in .Brewfile — brew bundle install should already have it)" >&2
  exit 1
}
[ -s "$LOCK" ] || {
  echo "error: $LOCK is missing or empty — nothing to reinstall." >&2
  echo "On a fresh machine this file is yadm content, restored by 'yadm clone'; if that ran, check 'yadm status'." >&2
  exit 1
}

skills_add() { env -u CLAUDE_CONFIG_DIR npx -y skills add "$@" -g --yes; }

# One TSV line per source package: the source string, then its skill names,
# space-joined. group_by sorts by the grouping key and each group's names are
# sorted too, so the install order — and this echo's output — is deterministic
# run to run rather than depending on the lock's on-disk key order.
groups=$(jq -r '
  .skills
  | to_entries
  | group_by(.value.source)
  | map({source: .[0].value.source, names: (map(.key) | sort)})
  | .[]
  | [.source, (.names | join(" "))]
  | @tsv
' "$LOCK")

if [ -z "$groups" ]; then
  echo "no skills recorded in $LOCK — nothing to install"
else
  while IFS=$'\t' read -r source names; do
    echo "==> $source ($names)"
    # $names is unquoted on purpose: it's a jq-built, space-joined list of bare
    # skill names (never containing spaces or shell metacharacters), and --skill
    # is variadic — it consumes every argument up to the next flag — so word
    # splitting here is what turns one string back into separate skill names.
    skills_add "$source" --skill $names
  done <<<"$groups"
fi

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
