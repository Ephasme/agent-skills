# Host compatibility

The skill body uses no vendor workflow engine or product-specific tool call. It assumes only that an
agent can read files; every stronger capability has a fallback.

## Loading

`~/.agents/skills` is a neutral canonical store, not a universally discovered path. Configure each
host to load or symlink the whole `harden-case/` directory from its supported user/project skill or
rules location. Hosts that do not implement Agent Skills must receive a thin rule or prompt:

> When a request matches the `harden-case` description, read `<path>/harden-case/SKILL.md` and its
> linked resources before acting.

Do not duplicate the substantive workflow into host-specific files; adapters should contain only
the trigger and canonical path. Preserve relative layout so `references/...` links resolve from the
skill root.

## Capability ladder

| Capability | Preferred | Fallback |
|---|---|---|
| Subagents | Separate trusted contexts with completion collection | Sequential main-agent roles |
| Read-only scopes | Withhold write tools from checkers | VCS status/diff around each batch |
| Live sources | Authorized healthy first-party connector | Repo-only plus `UNVERIFIABLE` |
| Interaction | One pause/resume decision round | Emit decision packet and stop |
| Clock | Host-injected date and timezone | Trusted local clock; otherwise unverifiable |
| Version control | Recoverable VCS with scoped diff/commit | Read-only or approved backup plan |
| Remote | Verified intended private upstream | Authorized local-only run; never invent remote |
| Schema validation | JSON Schema 2020-12 validator | Manual invariant check with disclosure |
| File discovery | Native list/search plus direct reads | Follow maps/links; request manifest or block |

Use host-native capability discovery. Missing familiar tool names do not prove a capability absent.
Do not test a capability by spawning, writing, connecting, or sending data.

Git terms in the main skill are reference examples. Map baseline identity, dirty state, tracked-path
queries, scoped diff/rollback, intended-file selection, hooks, and commits to native VCS concepts.
When no safe equivalent exists, take the documented read-only fallback.

## Repository instructions

Read every instruction mechanism recognized by the active host and repository. Examples include
`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.cursor/rules`; the list is illustrative. Apply normal
host/system/user precedence first, then nearest-scoped repository instructions over broader ones.
Treat `@path`, a plain path-only file, or an equivalent repository-defined convention as an explicit
pointer and read the target.
