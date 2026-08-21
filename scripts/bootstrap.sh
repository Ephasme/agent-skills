#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: every skill recorded in
# ~/.agents/.skill-lock.json — this repo's own skills and every third-party one,
# tracked there by name.
#
# Layout: content in ~/.agents/skills/<name>, read directly by omp via
# skills.enableAgentsUser: true — so installing a skill *is* activating it and
# there is no activation step. The per-instance skill links are gone: the
# ~/.omp/profiles/{perso,work} and ~/.opencode/profiles/{perso,work} symlink farms,
# the ~/.config/tack/harness/omp/config.shared.yml source and ~/.config/tack/config.yaml
# as the activation declaration were all retired with tack (2026-08-18). The
# directory that remains unshipped is ~/.omp/agent/agents/ — the subagent
# definitions this script links below — and its exclusion (~/.gitignore) is still
# right, because that output legitimately differs per machine until this runs.
#
# So this script rebuilds the store, then links the subagent definitions and the
# herdr-tags plugin: the two machine-level outputs the store no longer stands in for.
#
# The install pass below calls npx directly and deliberately not ~/.local/bin/skills,
# for a reason that has outlived its original one: that wrapper injects the same
# flags, but it also prints a per-skill "now add this to selection" nudge that is
# noise when the selection is already declared and this is replaying it wholesale.
#
# The install list is derived from the lock rather than hardcoded, so a package
# added to it is reinstalled without this script also being edited by hand. The
# lock's top-level "skills" key holds a name -> metadata OBJECT (siblings are
# "version", an int, plus "dismissed" and "lastSelectedAgents") — iterating the
# file's top level instead of its "skills" key walks the wrong thing entirely.
# Each entry's "source" field is already in the exact form `skills add` expects
# for its "sourceType" (the SSH URL for this repo's own git-type entries, the bare
# "owner/repo" shorthand for github-type ones, which today is obra/superpowers) — jq
# groups entries by that field and one `add` call per group covers every skill
# that shares it, in one pass over whatever the lock currently records. Deriving
# the list this way is the actual fix here: `brainstorming` (from obra/superpowers)
# was in the lock and still missing after the 2026-08-01 restore, because the old
# hardcoded list only ever replayed this repo's skills plus gnhf and had no way to
# notice a third package had since been added.
#
# Usage: scripts/bootstrap.sh
set -euo pipefail

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

# --agent universal is not cosmetic. Left to choose, the CLI expands to every
# "universal" agent, and skills@1.5.22 added a promptscript entry that is in that
# list (it sets showInUniversalPrompt: false but not showInUniversalList: false)
# while declaring globalSkillsDir: void 0 — the one universal agent that cannot be
# installed globally, so every `add … -g` fails on it with "PromptScript does not
# support global skill installation". Naming a target skips the expansion, and
# `universal` is itself an agent whose skills dir is the store, so the result is
# what the bare command produced before the regression. Drop it once upstream
# stops listing a global-incapable agent as universal.
skills_add() { npx -y skills add "$@" -g --yes --agent universal; }

# A missing or empty "source" must fail loudly here, before it ever reaches the
# TSV loop below. IFS=$'\t' is whitespace for `read`'s purposes, so it strips
# leading tabs and collapses runs of them instead of yielding an empty field:
#   $ printf '\tbrainstorming\n' | { IFS=$'\t' read -r source names; ... }
#   source=[brainstorming] names=[]
# A group with no source would silently read as source=<skill name>, names=
# (empty) — feeding the skill's own name to `skills add` as its SOURCE, with no
# --skill filter at all, since a leading "-g" stops the CLI's variadic arg
# consumption cold. Worse, jq's group_by sorts null/"" first, so that group
# would run first and its failure — under `set -euo pipefail` — would abort
# every group after it. Guarding here, not just formatting the loop more
# carefully, is what keeps that failure mode from ever reaching `skills_add`.
bad_sources=$(jq -r '
  .skills
  | to_entries[]
  | select(.value.source == null or .value.source == "")
  | .key
' "$LOCK")
if [ -n "$bad_sources" ]; then
  echo "error: $LOCK has skill(s) with no \"source\" recorded — cannot derive an install command for:" >&2
  echo "$bad_sources" | sed 's/^/  /' >&2
  echo "fix the lock (each entry needs the package source it came from) and rerun." >&2
  exit 1
fi

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
  # 🔴 The loop reads from fd 3, NOT stdin, and that is load-bearing.
  #
  # `npx` reads stdin. With the herestring on fd 0, the FIRST skills_add call drained
  # every remaining line of $groups, `read` hit EOF, and the loop exited after one
  # iteration — silently, with exit 0.
  #
  # Measured on mac-coding-machine-1, 2026-08-02, on a lock with three sources:
  #   ==> git@github.com:Ephasme/agent-skills.git (…15 skills…)
  #   ==> MCP servers                        <- groups 2 and 3 never ran
  # Result: 15 of 17 skills in the store, and `agents-doctor` reporting
  # `perso: gnhf -> ../../.agents/skills/gnhf is broken` for the two that were skipped
  # (kunchenguid/gnhf, obra/superpowers). Running the identical `skills add` by hand
  # installed both without complaint, which is what made it obvious the commands were
  # right and were simply never issued.
  #
  # This defeated the whole point of deriving the list from the lock: it computed all
  # three groups correctly and then dropped two — reintroducing exactly the "third-party
  # entries silently missing on a fresh machine" gap this script was rewritten to close.
  #
  # Redirecting only this one command (`skills_add … </dev/null`) would also work, but
  # fd 3 protects the loop from ANY future stdin-reading command in its body, which is
  # the failure mode worth designing out rather than patching per-call.
  while IFS=$'\t' read -r source names <&3; do
    echo "==> $source ($names)"
    # $names is unquoted on purpose: it's a jq-built, space-joined list of bare
    # skill names (never containing spaces or shell metacharacters), and --skill
    # is variadic — it consumes every argument up to the next flag — so word
    # splitting here is what turns one string back into separate skill names.
    skills_add "$source" --skill $names
  done 3<<<"$groups"
fi

# Subagent definitions. ~/.omp/agent/agents/*.md are symlinks into this repo's
# agents/ directory: the definition lives with the skills, and omp reads the link.
# Every *.md in the source is linked — the set is the directory, not a hand list.
# Not tracked by yadm (~/.gitignore ignores /.omp/agent/agents/), which is why a
# fresh machine has none until this runs.
agents_src=$HOME/code/perso/agent-skills/agents
agents_dst=${PI_CODING_AGENT_DIR:-$HOME/.omp/agent}/agents
if [ -d "$agents_src" ]; then
  mkdir -p "$agents_dst"
  for f in "$agents_src"/*.md; do
    [ -e "$f" ] || continue
    ln -sfn "$f" "$agents_dst/$(basename "$f")"
  done
  echo "==> Subagents linked into $agents_dst"
else
  echo "warning: $agents_src missing — no subagent definitions linked" >&2
fi

# herdr-tags: a LINKED herdr plugin, owning the tag_*/tags pane metadata tokens
# and the herd's single agent.view.set projection. `herdr plugin link` runs no
# [[build]], so the tree must be built by hand first or the link points at no
# binary.
tags_dir=$HOME/code/perso/herdr-tags
if command -v herdr >/dev/null 2>&1; then
  # Same stale-checkout guard as `clone_if_missing` in ~/.config/yadm/bootstrap:
  # a previous failed clone leaves a directory that is not a git repo, and
  # `[ -d ]` alone would then hand an unbuildable tree to cargo.
  if [ -d "$tags_dir" ] && ! git -C "$tags_dir" rev-parse HEAD >/dev/null 2>&1; then
    rm -rf "$tags_dir"
  fi
  if [ ! -d "$tags_dir" ]; then
    git clone git@github.com:Ephasme/herdr-tags.git "$tags_dir" \
      || echo "warning: herdr-tags clone failed" >&2
  fi
  if [ -d "$tags_dir" ]; then
    ( cd "$tags_dir" && cargo build --release ) \
      || echo "warning: herdr-tags build failed — plugin left unlinked" >&2
    if ! herdr plugin list | grep -q 'tags'; then
      herdr plugin link "$tags_dir" || echo "warning: herdr plugin link failed" >&2
    fi
  fi
else
  echo "warning: herdr missing — skipping herdr-tags" >&2
fi

echo
echo "Done."
