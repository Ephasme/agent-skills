# Agent Instructions

Catalog of portable agent skills in the [Agent Skills](https://agentskills.io/specification) format.
One directory per skill: `skills/<category>/<skill>/SKILL.md`.

## Commands

| Task | Command |
|------|---------|
| Validate the catalog | `node scripts/validate.mjs` |
| Validate quietly (errors only) | `node scripts/validate.mjs --quiet` |
| Reinstall the store from this tree | `npx -y skills add . --skill '*' -g --yes` |

No package manager, no dependencies, no build. Node 22 in CI.
`scripts/validate.mjs` takes no path argument — it always walks the whole catalog.

## External References

| Need | File |
|------|------|
| Portability contract, install, authoring loop | `README.md` |
| Every rule the validator enforces, with rationale | `scripts/validate.mjs` |
| CI checks beyond the validator | `.github/workflows/validate.yml` |

## Key Conventions

- Categories are fixed: `engineering`, `finance`, `health`, `helpers`, `legal`, `meta`,
  `research`, `toolbox`. Adding one means editing `CATEGORIES` in `scripts/validate.mjs`.
- `name` must equal the directory name and be unique across all categories.
- Frontmatter: the six spec fields plus `disable-model-invocation`. Nothing else.
- `SKILL.md` body under 500 lines; overflow goes to `references/`, linked from `SKILL.md`
  directly (one level deep, never reference-to-reference).
- A `references/*.md` over 100 lines with 2+ sections needs a `## Contents` list.
- Skills are self-contained: helpers live in the skill's own `scripts/`, duplicated rather
  than shared, because skills install independently.
- Name capabilities, not products. No agent brand names, model versions, harness-only
  variables (`${CLAUDE_PLUGIN_ROOT}`), or hard-coded agent config dirs. A skill whose
  subject genuinely is one product declares it in `compatibility`.
- `CLAUDE.md` may only appear on a line that also names `AGENTS.md`.
- Sub-agent fan-out must state a serial fallback for agents that have none.
- Retired skills live in git history only — no `archive/` directory; the CLI would
  reinstall anything with a `SKILL.md` two levels down.
- `agents/*.md` are omp-specific sub-agent definitions, exempt from the portability
  contract and not installed by the `skills` CLI.

## Before Committing

Run `node scripts/validate.mjs`. CI also asserts the `skills` CLI discovers every
`SKILL.md` and installs the whole catalog for `codex`, `cursor`, `opencode`, `gemini-cli`.
