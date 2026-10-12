# agent-skills

One folder per skill, each self-contained, in the [Agent Skills](https://agentskills.io) open
format — the same `SKILL.md` contract Claude Code, Codex, Cursor, Gemini CLI, opencode, Copilot,
Goose and others read. Installed with the [`skills`](https://github.com/vercel-labs/skills) CLI.

Public at [`Ephasme/agent-skills`](https://github.com/Ephasme/agent-skills). That SSH URL is the
source string throughout this document:

```
git@github.com:Ephasme/agent-skills.git
```

- [The portability contract](#the-portability-contract)
- [Install](#install)
- [MCP servers](#mcp-servers)
- [Authoring](#authoring)
- [What the validator enforces, and why](#what-the-validator-enforces-and-why)
- [Catalog](#catalog)
- [Third-party skills](#third-party-skills)
- [The `agents/` directory](#the-agents-directory)

## The portability contract

A skill works the same in every agent that reads the format. That is deliberate, not accidental,
and `scripts/validate.mjs` enforces the parts of it a script can check. CI proves the rest: it
installs the whole catalog for `codex`, `cursor`, `opencode` and `gemini-cli`, none of which the
catalog is written against.

**Name the capability, never the product.** Ask for "a structured multiple-choice prompt", not
`AskUserQuestion`; for "the strongest model available", not a model by brand and version; for the
repo's agent instructions as a set (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `.cursor/rules`), never
one alone. A product name bets the reader is one particular agent, and that bet is usually wrong.

**Degrade, don't fail.** A skill that fans work across sub-agents says what to run instead when the
agent has none: the same units, in series, with results written to files between them. Parallelism
is an optimisation; the isolation it buys is the point, and files and ordering buy it too.

**Declare hard requirements in `compatibility`.** An external binary, a credential, a network
dependency, or a target product belongs in the spec's optional `compatibility` field —
`hand-off-session` declares its Unix-like host with `tar`, `ssh` and `rsync`/`scp` there.

**Frontmatter stays inside the standard.** `name` and `description` are required; `license`,
`compatibility`, `metadata` and `allowed-tools` are the rest. One client extension is allowed,
`disable-model-invocation`, because an agent that ignores it still behaves correctly: every skill
carrying it also says "explicit invocation only" in prose.

**No path that only resolves in one place.** No `${CLAUDE_PLUGIN_ROOT}`, no `$CLAUDE_CONFIG_DIR`,
no absolute home path. A skill refers to its own files as `$SKILL_DIR/scripts/x` and says once that
`$SKILL_DIR` is notation for its own directory, not an exported variable.

## Install

```sh
SRC=git@github.com:Ephasme/agent-skills.git

npx -y skills@latest add "$SRC" --skill scan-code-quality -g --yes --agent universal
npx -y skills@latest add "$SRC" --skill '*'              -g --yes --agent universal
npx skills list                                          # what is installed
npx skills update                                        # pull newer versions into the store
```

Each skill lands in `~/.agents/skills/<name>`. omp reads that store directly, so an install is
live immediately — no activation step. The store is machine state and is not chezmoi-tracked; what
is tracked, in the dotfiles, is `~/.config/skills/sources` — one `skills add` argument list per
line, covering the catalog and every skill installed from another repo — applied by
`.chezmoiscripts/run_after_repos.sh` on every `chezmoi apply`.

`--agent universal` is not cosmetic. Left to choose, the CLI expands its universal agents, and that
set includes `promptscript`, which declares no global skills dir — so a bare `-g` prints
`PromptScript does not support global skill installation` once per skill (verified on skills@1.7.2).
Naming `universal` installs the same content, because `universal`'s own skills dir **is**
`~/.agents/skills`, without the failures.

## MCP servers

`mcp/servers.json` lists them — 18 remote HTTP servers, no credentials. `mcp/install.mjs` writes
that list into both agents' own config files and leaves every other key in them alone.

```sh
node mcp/install.mjs --dry-run     # what would change
node mcp/install.mjs               # omp's ~/.omp/agent/mcp.json, Claude Code's ~/.claude.json
node mcp/install.mjs --only omp    # one of them
```

Credentials live in `mcp/secrets.sops.yaml`, age-encrypted, key at `~/.config/sops/age/keys.txt`;
`mcp/servers.json` names them as `${VAR}`. Neither config file ever holds a value, because neither
agent expands an unset `${VAR}` — omp sends the literal text, Claude Code warns and does the same:

| Agent | What the config gets | When the value is read |
| --- | --- | --- |
| omp | `"Authorization": "!sh mcp/secret.sh 'Bearer ' APIFY_API_TOKEN"` | at connect; the header is dropped when the key is absent |
| Claude Code | `"headersHelper": "<path>/mcp/headers.mjs"` | on every connection, printing the headers as JSON |

Rotating a credential is then `sops mcp/secrets.sops.yaml` and a restart of omp — Claude Code runs
the helper on every connection, while omp caches a header once it resolves and retries a failed one
after 30 s. Slack is the one server whose OAuth client secret Claude Code keeps in its keychain
rather than its config, so register that once with
`claude mcp add --transport http slack … --client-secret`; the installer prints the command after
it runs.

The ciphertext is committed here, where the repo is public — the secrets rest entirely on the age
key, which is not.

## Authoring

```sh
git -C ~/code/perso/agent-skills pull
$EDITOR skills/<category>/<skill>/SKILL.md
node scripts/validate.mjs
# reinstall the store from the working tree
npx -y skills@latest add ~/code/perso/agent-skills --skill '*' -g --yes --agent universal
```

The install **copies** into `~/.agents/skills/<name>`, so edits in this working tree are not live —
re-run the add, or `skills update` once pushed, to pick them up. `scripts/validate.mjs` takes no
path argument; it always walks the whole catalog, and `--quiet` prints errors only.

Always pass `--agent universal` alongside `-g`; without it the run ends in `promptscript` failures —
see [Install](#install).

## What the validator enforces, and why

Spec limits — [agentskills.io/specification](https://agentskills.io/specification):

1. `name`: 1–64 chars, lowercase alphanumeric with single internal hyphens, equal to its directory,
   unique across the catalog (installs flatten to `~/.agents/skills/<name>`, so a collision
   silently overwrites), and free of the reserved words `claude` and `anthropic`.
2. `description`: 1–1024 chars, no XML tags, third person. It is the only field loaded at startup
   and the only thing an agent uses to decide whether the skill applies — it must say both what the
   skill does and when to reach for it.
3. `compatibility`, when present: ≤500 chars.
4. Frontmatter keys: the six spec fields — `name`, `description`, `license`, `compatibility`,
   `metadata`, `allowed-tools` — plus the one declared extension. Nothing else.

Progressive disclosure — [skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices):

5. `SKILL.md` body under 500 lines; past that, detail moves into `references/`.
6. Reference chains one level deep: every `references/*.md` is linked from `SKILL.md` directly, so
   an agent that follows a link reads the whole file rather than previewing a file it reached
   through another file.
7. A reference file over 100 lines with two or more sections carries a `## Contents` list, so a
   partial read still shows its scope.
8. Every `scripts/…`, `references/…` and `assets/…` path a skill mentions exists.

Portability — [the contract above](#the-portability-contract):

9. No harness-only variable, no hard-coded agent config directory, no harness product name, no model
   brand or version, no harness-specific tool or dispatch API, no plugin-namespaced skill reference.
   A skill whose subject genuinely is one product declares it in `compatibility` and is exempt.
10. `CLAUDE.md` is only ever named on a line that also names `AGENTS.md`.

Hygiene:

11. No absolute home paths, no `__pycache__`, no file over 1 MiB.
12. Only the nine categories below.

A skill is **self-contained**: anything it runs lives in its own `scripts/`. Where two skills need
the same helper, each ships a copy — they install independently and cannot reach each other.

## Catalog

| Category | Skills |
| --- | --- |
| `cases` | harden-case, sync-case |
| `engineering` | brainstorm-design, clean-git-repo, create-cleanup-roadmap, debug-systematically, execute-plan, harden-plan, refine-document, review-pr-list, scan-code-quality, strip-legacy-content, ui-ux-playbook, write-plan |
| `finance` | generate-payment-qr-code |
| `health` | cbt |
| `helpers` | move-workspace-files, post-deploy-changelog |
| `legal` | french-insurance-law |
| `meta` | dispatch-worktree-agents, execute-autonomously, hand-off-session, schedule-prompt, tighten-responses |
| `research` | assess-true-quality, cite-or-refuse, fact-check-document |
| `toolbox` | assume-aws-admin, build-mobileconfig, free-disk-space, set-filevault-recovery-key, ship-production |

32 skills. The CLI discovers a `SKILL.md` at any depth under `skills/`, and any `SKILL.md` sitting
directly inside a repo subdirectory; this repo uses `skills/<category>/<skill>/SKILL.md`, so no
manifest file is needed. Categories organise this repo only; installed skills are flat.

## Third-party skills

Nine skills in the store — `agents-md`, `caveman`, `find-skills`, `gnhf`, `lavish`,
`migrate-radix-to-base`, `ponytail`, `shadcn`, `skill-creator` — come from other repos and are not
vendored here, since a copy would fork them off upstream updates. Their sources are named in the
list described under [Install](#install): nothing about a skill is tracked in the dotfiles beyond
that list.

## The `agents/` directory

`cbt-expert.md`, `french-insurance-law-expert.md` and `quality-scout.md` are omp sub-agent
definitions, not skills — a subagent definition is a per-product format the portability contract
does not reach. Each sits beside the skill it drives and autoloads that skill rather than restating
it. The `skills` CLI installs skills only, so activation is one hand-made symlink:

```sh
ln -s ~/code/perso/agent-skills/agents/cbt-expert.md ~/.omp/agent/agents/
```
