# Agent Instructions

Catalog of portable agent skills in the [Agent Skills](https://agentskills.io/specification) format.
One directory per skill: `skills/<category>/<skill>/SKILL.md`.

## Critical constraints

- `node scripts/validate.mjs` must exit 0 before every commit.
- Reinstall from the repo root with `npx -y skills@latest add . --skill '*' -g --yes --agent
  universal`. `--agent universal` is required next to `-g`: without it the CLI also targets
  `promptscript`, which has no global skills dir, and reports a failure per skill.
- Keep the repo dependency-free: no package manager, no build step, no runtime dependency for
  `scripts/validate.mjs`.
- Keep every `SKILL.md` at `skills/<category>/<skill>/SKILL.md`. The CLI also installs any
  `SKILL.md` sitting directly inside a repo subdirectory, so a copy left outside `skills/` ships
  as a skill. Retire a skill by deleting it — git history is the archive, never an `archive/`
  directory.

## Commands

| Task | Command |
|------|---------|
| Validate the catalog | `node scripts/validate.mjs` |
| Validate quietly (errors only) | `node scripts/validate.mjs --quiet` |
| Reinstall the store from this working tree | `npx -y skills@latest add . --skill '*' -g --yes --agent universal` |
| Install the MCP servers into both agents | `node mcp/install.mjs` |

`scripts/validate.mjs` takes no path argument; it always walks the whole catalog. CI runs it on
Node 22.
The install copies into `~/.agents/skills/<name>`, which omp reads directly, so the installed
skill is live immediately — no activation step, no per-profile links.

## Key Conventions

- Categories: `cases`, `engineering`, `finance`, `health`, `helpers`, `legal`, `meta`,
  `research`, `toolbox`. Adding one means editing `CATEGORIES` in `scripts/validate.mjs`.
- `name`: 1–64 chars, lowercase alphanumeric with single internal hyphens, equal to its
  directory, unique across the catalog, free of `claude` and `anthropic`.
- `description`: 1–1024 chars, no XML tags, third person. `compatibility`, when present, ≤500 chars.
- Frontmatter keys: `name`, `description`, `license`, `compatibility`, `metadata`,
  `allowed-tools`, plus the one extension `disable-model-invocation`. Nothing else.
- `SKILL.md` body under 500 lines; overflow goes to `references/`.
- Every `references/*.md` is linked from `SKILL.md` directly — one level deep, never
  reference-to-reference. Every `scripts/…`, `references/…` and `assets/…` path a `SKILL.md`
  mentions must exist.
- A `references/*.md` over 100 lines with 2+ sections carries a `## Contents` list.
- `$SKILL_DIR` is notation for the skill's own directory, not an exported variable; a skill that
  uses it says so once.
- Name capabilities, not products: no agent brand names, model versions, harness-only variables
  (`${CLAUDE_PLUGIN_ROOT}`), harness-specific tool or dispatch names, or hard-coded agent config
  dirs. A skill whose subject is one product declares it in `compatibility`.
- `CLAUDE.md` is a symlink to `AGENTS.md`; name it only on a line that also names `AGENTS.md`.
- No absolute home path with a real user name (`/Users/<you>/…`, `/home/<you>/…`), no
  `__pycache__` or `*.pyc`, no file over 1 MiB.
- Skills are self-contained: helpers live in the skill's own `scripts/`, copied per skill rather
  than shared, because skills install independently.
- A skill that fans work out across sub-agents states a serial fallback for agents that have none.
- `agents/*.md` are omp sub-agent definitions, exempt from the portability contract and not
  installed by the `skills` CLI; symlink one into `~/.omp/agent/agents/` to activate it.
- MCP servers live in `mcp/servers.json`, installed into omp and Claude Code by `mcp/install.mjs`.
  Write no credential into a config file: `mcp/servers.json` names each one as `${VAR}`, the value
  rests in `mcp/secrets.sops.yaml` (age-encrypted, `.sops.yaml` holds the recipient), and
  `mcp/secret.sh` / `mcp/headers.mjs` read it at connect time. Name a server's secret after its
  header (`WHATSAPP_CF_ACCESS_CLIENT_ID`), not after the host.

## External References

| Need | File |
|------|------|
| Portability contract, install, authoring loop | `README.md` |
| Every rule the validator enforces, with rationale | `scripts/validate.mjs` |
| Discovery smoke test and portability install, beyond the validator | `.github/workflows/validate.yml` |
| Working papers for `assess-true-quality` (plans, research, testing) | `docs/` |
| MCP server list, installer, and the two secret helpers | `mcp/` |
