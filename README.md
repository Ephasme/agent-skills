# agent-skills

Every hand-written agent skill, in one place, installable into any agent.

These used to live inside Claude Code purpose-plugins in the yadm dotfiles, which meant only
Claude Code could load them. They are now a plain skill package: one folder per skill, each
self-contained, installed with the [`skills`](https://github.com/vercel-labs/skills) CLI into
Claude Code, Codex, Cursor, opencode, Copilot, or any of the ~75 agents it supports.

Private repo. Several skills carry personal or employer-adjacent detail — bank import recipes,
a medical research corpus, a production-database runbook. Keep it that way.

## Install

```sh
# everything, into this shell's Claude profile, global
skills add Ephasme/agent-skills -g -a claude-code -s '*' -y

# other agents — same repo, no repackaging
skills add Ephasme/agent-skills -g -a codex -a cursor -a opencode -s '*' -y

# one skill, project scope → ./.claude/skills/ + ./.agents/skills/
skills add Ephasme/agent-skills -s two-axis-review

skills list      # what is installed, and where
skills update    # pull newer versions
```

`-g` installs to the **canonical store** `~/.agents/skills/<name>` and symlinks each agent's own
skills dir at it. For Claude Code that dir is `$CLAUDE_CONFIG_DIR/skills`, so the two-profile
split works without extra flags — whichever profile's env is loaded is the one that gets the
symlink. To do both from one shell:

```sh
CLAUDE_CONFIG_DIR=$HOME/.claude-perso skills add Ephasme/agent-skills -g -a claude-code -s '*' -y
CLAUDE_CONFIG_DIR=$HOME/.claude-work  skills add Ephasme/agent-skills -g -a claude-code -s '*' -y
```

`scripts/bootstrap.sh` runs the whole set for a fresh machine.

### Private-repo access

The CLI clones over SSH when `gh auth status` reports the ssh protocol, into a temp directory
where `~/.gitconfig`'s `includeIf gitdir:~/code/perso/` never fires. That include is the only
place the perso key is named for GitHub, so without an `~/.ssh/config` entry the clone fails with
*Permission denied (publickey)* even though pushing from a checkout works:

```
Host github.com
  User git
  IdentityFile "~/.ssh/id_ed25519_perso"
  IdentitiesOnly yes
```

From a plain terminal also set `GH_CONFIG_DIR=$HOME/.config/gh-perso`; inside a Claude session
`claude-profile` already exports it.

## Authoring

```sh
git -C ~/code/perso/agent-skills pull
$EDITOR skills/<category>/<skill>/SKILL.md
node scripts/validate.mjs
skills add ~/code/perso/agent-skills -g -a claude-code -s '*' -y   # reinstall
```

A global install **copies** into `~/.agents/skills/<name>`; edits in this working tree are not
live. Re-run `skills add` (or `skills update` once pushed) to pick them up.

Rules the validator enforces, and why:

1. `SKILL.md` frontmatter must have string `name` + `description`. The CLI silently skips a skill
   whose frontmatter is missing either, with only a one-line warning.
2. `name` must equal its directory name, and be unique across all categories — installs flatten
   to `~/.agents/skills/<name>`, so a collision silently overwrites.
3. No `${CLAUDE_PLUGIN_ROOT}`. It only exists for plugin-loaded skills; installed anywhere else it
   expands to nothing and every script path breaks. Write `$SKILL_DIR/scripts/x` and say once in
   the skill that `$SKILL_DIR` is notation for the skill's own directory, whose absolute path the
   preamble prints.
4. Every `scripts/…` and `references/…` path a `SKILL.md` mentions must exist.
5. No absolute home paths (`/home/you/…`, `/Users/you/…`), no `__pycache__`, nothing over 1 MiB.
6. Only the ten categories below.

A skill must be **self-contained**: anything it runs lives in its own `scripts/`. Where two skills
need the same helper, both ship a copy (`spec-to-pr` and `two-axis-review` each carry
`review-package` + `build-workspace`) — they install independently and cannot reach each other.

## Catalog

| Category | Skills |
| --- | --- |
| `engineering` | code-quality-scan, document-codebase, greenfield, linear-project-sync, plan-hardening, prune-branches, spec-to-pr, two-axis-review, update-documentation, writing-technical-specs |
| `finance` | bank-actual-import, payment-qr, receipt-split |
| `claude-tools` | handoff, plugin-config |
| `research` | cite-or-refuse, fact-check-document |
| `setup` | free-disk-space, git-multi-identity-setup |
| `trackers` | harden-case, track-case |
| `meta` | executing-autonomously, no-verbose |
| `health` | tcc |
| `ops` | cancel-trial-courses |
| `security` | 1password-passkey-audit |

`skills/<category>/<skill>/SKILL.md` is discovered natively — the CLI walks one extra level inside
`skills/` for exactly this catalog layout. No manifest file is needed. Categories organise the
repo only; installed skills are flat.

## What is deliberately not here

**MCP servers.** The eight purpose-plugins (`engineering`, `research`, `finance`, `communication`,
`workspace`, `navigation`, `automation`, `security`, `trackers`) stay in the yadm dotfiles at
`~/.agents/plugins/<purpose>/`, now MCP-only. No agent outside Claude Code consumes `.mcp.json`,
and their credentials are `${KEY}` env vars from `~/.config/secrets.zsh`.

**Third-party skills.** `tamagui`, `find-skills`, `web-design-guidelines` and `gnhf` are installed
from their own upstreams and tracked in `~/.agents/.skill-lock.json`. Vendoring them here would
fork them off upstream updates.

**`agents/tcc-expert.md`.** A Claude Code subagent, kept here beside the corpus it drives. The
`skills` CLI installs skills only — symlink it into `~/.claude-<profile>/agents/` by hand.

**Machine infrastructure.** `track-case` drives the `trackers` CLI, which stays in the dotfiles
plugin because cron invokes it too; the skill resolves it at
`~/.agents/plugins/trackers/scripts/trackers`.
