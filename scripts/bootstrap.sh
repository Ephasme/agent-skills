#!/usr/bin/env bash
# Reinstall the full skill set on a fresh machine: every skill recorded in
# ~/.agents/.skill-lock.json — this repo's own skills and every third-party one,
# tracked there by name — plus the MCP servers rendered into every agent that is
# installed.
#
# Layout: content in ~/.agents/skills/<name>, and one symlink per skill per instance
# — one harness × one identity. Today that is
# ~/.omp/profiles/{perso,work}/agent/skills/<name> and
# ~/.opencode/profiles/{perso,work}/config/opencode/skills/<name>; codex reads
# ~/.agents/skills natively and is posted no link at all. For omp those
# links are the only user-level skill source it reads (~/.config/tack/harness/omp/config.shared.yml
# turns the foreign ones off). The CLI produces the store on its own — every
# "universal" agent's skills dir *is* ~/.agents/skills — and it links the agents it
# detects. It detects none of those four directories, so installing a skill activates
# it nowhere. That is deliberate: each identity links only the skills that belong in
# it, and work and perso do not get the same set.
#
# So this script rebuilds the store, then hands activation to tack. Which identity
# gets which skill is not in the lock and never was: it is declared in
# ~/.config/tack/config.yaml — yadm content, like the lock — and `tack apply` is the
# only thing that turns that declaration into symlinks. The symlinks themselves are
# not tracked: ~/.gitignore excludes each harness's activation directory, because an
# output that can disagree with its source has no business being carried. So a fresh
# machine clones the declaration and none of the links, and closing that gap is this
# script's second half.
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

# Activation, and the MCP servers with it. Both are one command now: the store is
# content, and which profile gets which skill — and which harness gets which MCP
# server, extension and shell shortcut — is declared in ~/.config/tack/config.yaml.
# `tack apply` is the one code path that turns that declaration into symlinks and
# rendered files, and it is called rather than reimplemented here because it knows
# the three things this script does not: which harnesses are installed, which read
# ~/.agents/skills natively and get no link at all, and which are residue and must
# never be written into.
#
# The MCP render used to be a separate `node install-mcp.mjs` pass over
# mcp/servers.json. That manifest and that renderer were deleted on 2026-08-16 when
# config.yaml became the only record; apply writes those files now, and like the old
# pass it needs no credentials — what it writes are references to environment
# variables, not their values — so it is correct before `yadm decrypt` has restored
# ~/.config/secrets.zsh.
echo
if ! command -v tack >/dev/null 2>&1; then
  # Loud on purpose. A store that cannot be activated leaves every skill installed
  # and visible nowhere: this script's worst outcome and its least visible one.
  echo "error: tack is not on PATH — install it with \`uv tool install ~/code/perso/tack\`, then re-run." >&2
  exit 1
fi
echo "==> Activation, MCP and shortcuts (tack apply)"
# No redirection or fd juggling needed: this is outside the fd-3 loop above, and
# `tack apply` reads no stdin with --yes. A non-zero exit aborts the script under
# `set -e` (line 51), which is the intent — a failed reconciliation is not a
# cosmetic problem. It is idempotent: on a converged machine it prints "nothing to
# do", which is why it is not gated on any file existing.
tack apply --yes

echo
echo "Done. Verify with: tack doctor"
