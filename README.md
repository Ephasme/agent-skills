# agent-skills

Every hand-written agent skill, in one place, installable into any agent.

These used to live inside Claude Code purpose-plugins in the yadm dotfiles, which meant only
Claude Code could load them. They are now a plain skill package: one folder per skill, each
self-contained, installed with the [`skills`](https://github.com/vercel-labs/skills) CLI into
Claude Code, Codex, Cursor, opencode, Copilot, or any of the ~75 agents it supports.

Self-hosted and private, on the Forgejo at `git.loup-peluso.com` — several skills carry personal
or employer-adjacent detail (bank import recipes, a medical research corpus, a production-database
runbook), and none of it needs to sit on someone else's server. Managed with
[`tea`](https://gitea.com/gitea/tea), not `gh`.

```
ssh://git@git-ssh.loup-peluso.com:2222/loup/agent-skills.git
```

The `skills` CLI has no shorthand for a self-hosted host, so that full URL is the source string
everywhere below. It falls through to the CLI's generic git path and is cloned with plain
`git clone` — no forge API, no token. Access is the `git-ssh.loup-peluso.com` block already in
`~/.ssh/config`, which names the perso key and the `:2222` port; without it a clone from a temp
directory fails *Permission denied (publickey)* even though pushing from a checkout works, because
`~/.gitconfig`'s `includeIf gitdir:~/code/perso/` never fires outside the checkout.

## Install

On Loup's machines `skills` is the wrapper at `~/.local/bin/skills`, not the upstream CLI. It runs
upstream once per Claude profile with `CLAUDE_CONFIG_DIR` set, and pairs `claude-code` with a
universal store-agent so upstream symlinks natively into `~/.agents/skills` instead of copying.
**Do not pass `-a` yourself** — that suppresses the store-agent injection and you get real copies
in each profile instead of symlinks into one store.

```sh
SRC=ssh://git@git-ssh.loup-peluso.com:2222/loup/agent-skills.git

skills add "$SRC" -s '*' -y              # both profiles
skills --target=perso add "$SRC" -s '*' -y
skills list                              # what is installed, and where
skills update                            # pull newer versions
```

Result: content in `~/.agents/skills/<name>`, with `~/.claude-perso/skills/<name>` and
`~/.claude-work/skills/<name>` as relative symlinks at it.

Anywhere else — another machine, another agent — use the upstream CLI directly:

```sh
npx skills add "$SRC" -g -a codex -a cursor -a opencode -s '*' -y
npx skills add "$SRC" -s two-axis-review   # one skill, project scope
```

`scripts/bootstrap.sh` runs the whole set for a fresh machine.

## Authoring

```sh
git -C ~/code/perso/agent-skills pull
$EDITOR skills/<category>/<skill>/SKILL.md
node scripts/validate.mjs
skills add ~/code/perso/agent-skills -s '*' -y   # reinstall from the working tree
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

**A GitHub mirror.** This lived briefly at `Ephasme/agent-skills` before moving here. There is no
mirror and no sync — Forgejo is the only remote.

**MCP servers.** The purpose-plugins that used to carry these skills also carried `.mcp.json`
files (`engineering`, `research`, `finance`, `communication`, `workspace`, `navigation`,
`automation`, `security`, `trackers`). The whole `~/.agents/plugins/` store was removed from the
dotfiles on 2026-07-31 in yadm commit `1803e8c`; it is restorable with
`yadm checkout debe473 -- .agents/plugins`. Whether that MCP layer comes back is a separate
decision — it does not belong here either way, since no agent outside Claude Code consumes
`.mcp.json` and their credentials are `${KEY}` env vars from `~/.config/secrets.zsh`.

**Third-party skills.** `tamagui`, `find-skills`, `web-design-guidelines` and `gnhf` are installed
from their own upstreams and tracked in `~/.agents/.skill-lock.json`. Vendoring them here would
fork them off upstream updates.

**`agents/tcc-expert.md`.** A Claude Code subagent, kept here beside the corpus it drives. The
`skills` CLI installs skills only — symlink it into `~/.claude-<profile>/agents/` by hand.

**Machine infrastructure.** `track-case` drives the `trackers` CLI, which cron invokes too, so it
belongs to the machine rather than to the skill. The skill looks for it on PATH, then at
`~/.agents/plugins/trackers/scripts/trackers`, and stops if neither resolves — which is the case
right now, since that store was removed in `1803e8c`.
