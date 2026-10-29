# Agent Instructions

Personal catalog of portable agent skills in the [Agent Skills](https://agentskills.io/specification)
format, one directory per skill at `skills/<category>/<skill>/SKILL.md`. The repo is public.

## Critical constraints

- `node scripts/validate.mjs` must exit 0 before every commit.
- Keep the repo dependency-free: no package manager, no build step, nothing `scripts/validate.mjs`
  needs at runtime.
- Every `SKILL.md` lives at `skills/<category>/<skill>/SKILL.md`. The CLI also installs any
  `SKILL.md` sitting directly inside a repo subdirectory, so a stray copy outside `skills/` ships
  as a skill. To retire a skill, delete it; git history is the archive.
- Never commit a plaintext secret. See [Secrets](#secrets).

## Commands

| Task | Command |
|------|---------|
| Validate the catalog | `node scripts/validate.mjs` (`--quiet` for errors only) |
| Install this working tree into the store | `npx -y skills@latest add . --skill '*' -g --yes --agent universal` |
| Edit or rotate a secret | `sops mcp/secrets.sops.yaml` |

Always pass `--agent universal` with `-g`. Without it the CLI also targets `promptscript`, which has
no global skills directory, and fails once per skill. The install copies into
`~/.agents/skills/<name>`, so edits here aren't live until you re-run it.

## Conventions

- Categories are the ones in `CATEGORIES` in `scripts/validate.mjs`; adding one means editing that
  list.
- `name`: 1–64 chars, lowercase alphanumerics with single internal hyphens, matching its directory,
  unique across the catalog, and free of `claude` and `anthropic`.
- `description`: 1–1024 chars, no XML tags, third person. `compatibility`, if present, ≤500 chars.
- Frontmatter keys: `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`,
  plus one extension, `disable-model-invocation`. Nothing else.
- `SKILL.md` body stays under 500 lines; the rest goes in `references/`, each file linked straight
  from `SKILL.md`, never from another reference. A reference over 100 lines with two or more
  sections starts with a `## Contents` list.
- Every `scripts/…`, `references/…` and `assets/…` path a `SKILL.md` mentions must exist.
- `$SKILL_DIR` is notation for the skill's own directory, not an exported variable; a skill that
  uses it says so once.
- Name capabilities, not products: no agent brands, model versions, harness-only variables
  (`${CLAUDE_PLUGIN_ROOT}`), harness-specific tools or hard-coded agent config directories. A skill
  whose subject is one product declares it in `compatibility`.
- Skills are self-contained. Helpers live in the skill's own `scripts/`, copied rather than shared,
  because skills install independently.
- A skill that fans work out to sub-agents gives a serial fallback for agents that have none.
- `CLAUDE.md` is a symlink to `AGENTS.md`; only mention it on a line that also names `AGENTS.md`.
- No absolute home paths with a real user name, no `__pycache__` or `*.pyc`, no file over 1 MiB.
- `agents/*.md` are omp sub-agent definitions. They're exempt from the portability rules and the
  `skills` CLI doesn't install them; activate one by symlinking it into `~/.omp/agent/agents/`.
- Other catalogs install skills from here rather than copying them, and get every push to `main` on
  their next `skills update`. Renaming or deleting a skill breaks their install command: treat a
  skill's name as public API.

## Secrets

MCP credentials live in `mcp/secrets.sops.yaml`, a SOPS store encrypted with age. The ciphertext is
committed to this public repo, so the secrets are only as safe as the age key.

- `.sops.yaml` names the age recipient, so `sops` encrypts new values without `--age`.
- The age key is read from `$SOPS_AGE_KEY_FILE`, otherwise
  `~/Library/Application Support/sops/age/keys.txt` on macOS or `~/.config/sops/age/keys.txt`
  elsewhere. It never goes in the repo.
- A secret's key in the store is the env var or header placeholder that uses it. Name a new header
  secret after the header it fills (`WHATSAPP_CF_ACCESS_CLIENT_ID`), not after the host.
- Agent configs are edited by hand from `mcp/servers.json` and hold references, never values. Run
  the agent from the repo root, or make the `mcp/…` paths absolute.
  - **stdio servers** read their token from the environment. Their entry runs
    `sops exec-env mcp/secrets.sops.yaml "<server command>"`, which decrypts the store into the
    server's environment only. Non-secret settings (base URLs) go in the entry's `env`.
  - **HTTP servers** carry `${VAR}` in a header, filled by a `sops` call in the agent config:
    - omp: `"!sh v=$(sops -d --extract '[\"<VAR>\"]' <store>) && printf '<prefix>%s' \"$v\""`. A
      missing key prints nothing, and omp then drops the header.
    - Claude Code: `"headersHelper": "sops exec-env <store> 'printf \"{\\\"<Header>\\\":\\\"<prefix>%s\\\"}\" \"${<VAR>:?}\"'"`,
      one `%s` and one `${<VAR>:?}` per header. `:?` makes a missing key fail instead of sending
      an empty value.
    Never write a bare `${VAR}`: neither agent expands it, so the literal text gets sent.
- After rotating a secret, restart omp. stdio servers read the store when they start; omp caches a
  resolved header.
- Never print, paste or commit a decrypted value.

## References

| Need | File |
|------|------|
| Portability contract, install, catalog | `README.md` |
| Every rule the validator enforces | `scripts/validate.mjs` |
| CI: discovery smoke test and cross-agent install | `.github/workflows/validate.yml` |
| Which skill depends on which | `dependencies.md` |
| Working papers for `assess-true-quality` | `docs/` |
| MCP server list and SOPS store | `mcp/` |
