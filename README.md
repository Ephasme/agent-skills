# agent-skills

Every hand-written agent skill, in one place, installable into any agent.

One folder per skill, each self-contained, following the [Agent Skills](https://agentskills.io)
open format — the same `SKILL.md` contract Claude Code, Codex, Cursor, Gemini CLI, opencode,
Copilot, Goose and dozens of others read. Installed with the
[`skills`](https://github.com/vercel-labs/skills) CLI, which discovers this repo's
`skills/<category>/<skill>/` layout natively.

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

## The portability contract

A skill here works the same in every agent that reads the format. That is a property the catalog
maintains deliberately, not a happy accident, and `scripts/validate.mjs` enforces it.

**Name the capability, never the product.** A skill asks for "a structured multiple-choice prompt
if this agent has one", not for `AskUserQuestion`. It asks for "the strongest model available",
not for a model by brand and version. It reads "the repo's agent instructions (`AGENTS.md`,
`CLAUDE.md`, `GEMINI.md`, `.cursor/rules`)", never one of those alone. Product names in an
instruction are a bet that the reader is one particular agent, and that bet is wrong most of the
time.

**Degrade, don't fail.** Most of these skills fan work out across sub-agents. Where they do, they
say what to run instead when the agent has none — the same units, in series, with results written
to files between them. Parallelism is an optimisation; the isolation it buys is the thing that
matters, and it can be bought with files and ordering. The two exceptions are stated outright:
`spec-to-pr` stops rather than let one context implement and review its own work, and
`code-quality-scan` refuses to merge its find and check passes.

**Declare hard requirements in `compatibility`.** The spec's optional `compatibility` field is
where an external binary, a credential, a network dependency, or a specific target product
belongs. `plugin-config` configures Claude Code plugins — that's its subject, declared in the
field, and it still runs from any agent because it drives the `claude` CLI rather than living
inside it.

**Frontmatter stays inside the standard.** `name` and `description` are required;
`license`, `compatibility`, `metadata` and `allowed-tools` are the rest of the field set. One
client extension is allowed — `disable-model-invocation`, which suppresses autonomous loading in
Claude Code — because an agent that ignores it still behaves correctly: every skill that carries
it also says "explicit invocation only" in prose, where every agent reads it.

**No path that only resolves in one place.** No `${CLAUDE_PLUGIN_ROOT}` (it exists only for
plugin-loaded skills and expands to nothing elsewhere), no `$CLAUDE_CONFIG_DIR` for a skill's own
data — use `${XDG_CONFIG_HOME:-$HOME/.config}/<skill>/` — and no absolute home paths. A skill
refers to its own files as `$SKILL_DIR/scripts/x`, and says once that `$SKILL_DIR` is notation for
its own directory rather than an exported variable.

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
npx skills add "$SRC" -g -a codex -a cursor -a opencode -a gemini-cli -s '*' -y
npx skills add "$SRC" -s two-axis-review   # one skill, project scope
```

Agent names are the CLI's own (`gemini-cli`, not `gemini`); `npx skills add . -a bogus` prints
the full list of the ~75 it accepts. Multiple `-a` targets that share the `.agents/skills/`
store install once and are seen by all of them.

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

### What the validator enforces, and why

Spec limits — [agentskills.io/specification](https://agentskills.io/specification):

1. `name`: 1–64 chars, lowercase alphanumeric with single internal hyphens, matching its directory,
   unique across the catalog (installs flatten to `~/.agents/skills/<name>`, so a collision
   silently overwrites), and free of the reserved words `claude` and `anthropic`.
2. `description`: 1–1024 chars, no XML tags, third person. It is the only thing loaded at startup
   and the only thing an agent uses to decide whether the skill applies — it must carry both what
   the skill does and when to reach for it.
3. `compatibility`, when present: ≤500 chars.
4. Frontmatter keys: the six spec fields plus the one declared extension. Nothing else.

Progressive disclosure — [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

5. `SKILL.md` body under 500 lines. Past that, detail moves into `references/`.
6. Reference chains one level deep: every `references/*.md` is linked from `SKILL.md` directly, so
   an agent following a link reads the whole file instead of previewing a file it reached through
   another file.
7. A reference file over 100 lines with two or more sections carries a `## Contents` list, so a
   partial read still shows the full scope.
8. Every `scripts/…`, `references/…` and `assets/…` path a `SKILL.md` mentions exists.

Portability — the contract above:

9. No harness-only variable, no hard-coded agent config directory, no product name, no model
   brand or version, no harness-specific tool or dispatch API, no plugin-namespaced skill
   reference. A skill whose subject genuinely is one product declares it in `compatibility` and is
   exempt.
10. `CLAUDE.md` is only ever named on a line that also names `AGENTS.md`.

Hygiene:

11. No absolute home paths (`/home/you/…`, `/Users/you/…`), no `__pycache__`, nothing over 1 MiB.
12. Only the nine categories below.

A skill must be **self-contained**: anything it runs lives in its own `scripts/`. Where two skills
need the same helper, both ship a copy (`spec-to-pr` and `two-axis-review` each carry
`review-package` + `build-workspace`) — they install independently and cannot reach each other.

## Catalog

| Category | Skills |
| --- | --- |
| `engineering` | code-quality-scan, document-codebase, greenfield, linear-project-sync, plan-hardening, prune-branches, spec-to-pr, two-axis-review, update-documentation, writing-technical-specs |
| `finance` | bank-actual-import, payment-qr, receipt-split |
| `research` | cite-or-refuse, fact-check-document |
| `setup` | free-disk-space, git-multi-identity-setup, plugin-config |
| `trackers` | harden-case, track-case |
| `meta` | executing-autonomously, handoff, no-verbose |
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

**`agents/tcc-expert.md`.** The one file here that is not portable: subagent definitions are a
per-product format, and this one is Claude Code's. It is kept beside the corpus it drives. The
`skills` CLI installs skills only — symlink it into `~/.claude-<profile>/agents/` by hand.

**Machine infrastructure.** `track-case` drives the `trackers` CLI, which cron invokes too, so it
belongs to the machine rather than to the skill. The skill looks for it on PATH, then at
`~/.agents/plugins/trackers/scripts/trackers`, and stops if neither resolves — which is the case
right now, since that store was removed in `1803e8c`.
