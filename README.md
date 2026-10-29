# agent-skills

My agent skills, one self-contained directory each, in the open
[Agent Skills](https://agentskills.io) format: the same `SKILL.md` contract read by Claude Code,
Codex, Cursor, Gemini CLI, opencode, Copilot, Goose and others. They're installed with the
[`skills`](https://github.com/vercel-labs/skills) CLI.

- [Portability](#portability)
- [Install](#install)
- [Catalog](#catalog)
- [MCP servers](#mcp-servers)
- [Sub-agents](#sub-agents)
- [Authoring](#authoring)

## Portability

A skill behaves the same in every agent that reads the format. `scripts/validate.mjs` enforces what
a script can check, and CI installs the whole catalog for `codex`, `cursor`, `opencode` and
`gemini-cli` to prove the rest.

- **Name the capability, not the product.** Ask for "a structured multiple-choice prompt", not
  `AskUserQuestion`; for "the strongest model available", not a model name. When a skill refers to
  repo instructions, it names the whole set (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
  `.cursor/rules`), never just one.
- **Degrade instead of failing.** A skill that fans work out to sub-agents says what to do without
  them: the same units run in series, with results written to files in between.
- **Put hard requirements in `compatibility`.** External binaries, credentials, network access or a
  target product go in that optional frontmatter field.
- **Stay inside the standard frontmatter.** The one extension, `disable-model-invocation`, is safe
  because every skill that sets it also says "explicit invocation only" in its text.
- **No path that only resolves on one machine or in one agent.** A skill refers to its own files as
  `$SKILL_DIR/…` and explains that notation once.

## Install

```sh
npx -y skills@latest add git@github.com:Ephasme/agent-skills.git --skill '*' -g --yes --agent universal
npx -y skills@latest add git@github.com:Ephasme/agent-skills.git --list   # see what's available
npx skills update                                                         # pull newer versions
```

Swap `'*'` for a skill name to install just that one. Skills land in `~/.agents/skills/<name>`,
which omp reads directly, so they're live straight away. Keep `--agent universal`: without it the
CLI also targets `promptscript`, which has no global directory, and fails once per skill.

On my machines, `~/.config/skills/sources` (managed by chezmoi) lists every catalog to install,
including third-party skills, and `chezmoi apply` installs them. Third-party skills aren't copied
into this repo, so they keep getting upstream updates.

## Catalog

Each skill lives at `skills/<category>/<skill>/SKILL.md`. Categories only organise this repo;
installed skills are flat. `dependencies.md` shows which skills call which, including two edges into
the Sherpas catalog (`Les-Sherpas/agent-skills`), which holds the work skills.

## MCP servers

`mcp/servers.json` lists my MCP servers, with credentials referenced as `${VAR}` and never inlined.
I copy entries into each agent's config by hand: omp's `~/.omp/agent/mcp.json` and Claude Code's
`~/.claude.json`.

Credentials are stored in `mcp/secrets.sops.yaml`, encrypted with age, and decrypted by a `sops`
call in each agent's config when it connects. The rules are in [`AGENTS.md`](AGENTS.md#secrets). To
edit or rotate one:

```sh
sops mcp/secrets.sops.yaml
```

`mcp/slack-app-manifest.json` is the manifest for the Slack app behind the `slack` server.

## Sub-agents

`agents/*.md` are omp sub-agent definitions, not skills. Several drive a skill from this catalog
and load it rather than repeating it. The `skills` CLI doesn't install them, so activate one with a
symlink:

```sh
ln -s ~/code/perso/agent-skills/agents/<name>.md ~/.omp/agent/agents/
```

## Authoring

```sh
$EDITOR skills/<category>/<skill>/SKILL.md
node scripts/validate.mjs        # must exit 0 before you commit
npx -y skills@latest add . --skill '*' -g --yes --agent universal   # install your working tree
```

The full rule set, with the reason for each rule, is in `scripts/validate.mjs`.
