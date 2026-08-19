# agent-skills

Every hand-written agent skill and MCP server, in one place, installable into any agent.

One folder per skill, each self-contained, following the [Agent Skills](https://agentskills.io)
open format — the same `SKILL.md` contract Claude Code, Codex, Cursor, Gemini CLI, opencode,
Copilot, Goose and dozens of others read. Installed with the
[`skills`](https://github.com/vercel-labs/skills) CLI, which discovers this repo's
`skills/<category>/<skill>/` layout natively.

Self-hosted and private, on the Forgejo at `git.loup-peluso.com` — several skills carry personal
detail (a medical research corpus, a hardening workflow over private case records, response-style
rules written for one person), and none of it needs to sit on someone else's server. Managed with
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
matters, and it can be bought with files and ordering. The exception is stated outright:
`code-quality-scan` refuses to merge its find and check passes.

**Declare hard requirements in `compatibility`.** The spec's optional `compatibility` field is
where an external binary, a credential, a network dependency, or a specific target product
belongs. `handoff` needs a Unix-like local and remote host with `tar`, `ssh`, and `rsync`/`scp` —
that's a hard requirement, declared in the field, and it still runs from any agent because it
drives whatever transfer tools the host's shell offers rather than assuming one.

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

Upstream CLI. Install into the store, then link the skill into the profiles that should have
it — two steps, because work and perso do not get the same set.

```sh
SRC=git@github.com:Ephasme/agent-skills.git

npx -y skills add "$SRC" --skill code-quality-scan -g --yes    # 1. into the store
ln -s ~/.agents/skills/code-quality-scan \
      ~/.omp/profiles/perso/agent/skills/               # 2. activate, per profile
ln -s ~/.agents/skills/code-quality-scan \
      ~/.omp/profiles/work/agent/skills/

npx -y skills list                       # what is installed
npx -y skills update                     # pull newer versions into the store
```

On Loup's machines `~/.local/bin/skills` wraps those three commands — `skills add "$SRC"
--skill code-quality-scan [-t perso|-t work]`, both profiles by default — and links only what the run
introduced, so a `--skill '*'` refresh does not flatten existing per-profile choices. Anything
that is not `add` passes straight through.

**Pass no `--agent`.** With none, the CLI adds its *universal* agents — whose skills dir **is**
`~/.agents/skills` — so it sees more than one target directory and symlinks into that store
instead of copying (`dist/cli.mjs`: `ensureUniversalAgents`, then `uniqueDirs.size <= 1` is what
forces copy mode). Naming a single agent is what makes it copy. `--skill '*'` takes the whole
catalog.

Step 1 also links the agents the CLI *detects*. It does not detect
`~/.omp/profiles/{perso,work}/agent`, so an install activates a skill in neither profile — hence
step 2. That tree is also the whole of activation: `~/.config/tack/harness/omp/config.shared.yml` sets
`skills.enableClaudeUser`, `enableCodexUser` and `enableAgentsUser` to `false`, so a profile's own
`agent/skills` directory is the only user-level source omp reads. A skill in the store that no
profile links is installed and offered to nothing, silently. The link is absolute, like every
other link in that directory.

The step-2 symlinks are derived output, not yadm content: `~/.config/tack/config.yaml` records
which profile gets which skill, under its `selection:` block, and `tack apply` rebuilds every
activation link from it — the same operation `scripts/bootstrap.sh` runs on a fresh machine.

Other agents are named the same way — the CLI's own names (`gemini-cli`, not `gemini`);
`npx skills add . -a bogus` prints the full list of the ~75 it accepts.

```sh
npx skills add "$SRC" -g -a cursor -a gemini-cli -s '*' -y   # extra non-universal agents
npx skills add "$SRC" -s code-quality-scan                          # one skill, project scope
```

`scripts/bootstrap.sh` runs the whole set for a fresh machine.

## MCP servers

They are no longer in this repo. `mcp/servers.json` and `scripts/install-mcp.mjs` were deleted on
2026-08-16: the servers are declared in the `mcp:` block of `~/.config/tack/config.yaml` and
rendered into each installed harness's own config by `tack apply`, which is also what posts the
activation symlinks above. One record, one command, one place to look when a server is missing
somewhere.

```sh
tack plan                # what would change, including every MCP file
tack apply               # write it
tack doctor              # every {env: NAME} exported, every stdio command on PATH
```

### Turning one off

`enabled: false` on a server parks it — rendered nowhere, and removed from every harness that
already has it the next time `tack apply` runs.

```yaml
  bank:
    enabled: false
    note: "2026-07-31: bank.loup-peluso.com has no A record — the host is gone, not
      just down. Re-enable once it resolves."
    transport: http
    url: https://bank.loup-peluso.com/mcp
```

Deleting the entry uninstalls it too, and the difference is the definition: most reasons to switch
a server off are temporary (the origin is down, the upstream package is broken, it is noisy in one
season of work), and re-adding it later means reconstructing the URL and the header names from
nothing. Parked is the recoverable version of the same act.

`note` is required on a disabled server, and tack refuses to load a config without it. A parked entry with no
stated reason is the one that never gets switched back on, because nobody is left knowing what
would have to be true first — so the note says what that is, with the date it stopped being true.
`--list` prints them.

Four are parked today: `bank` (host no longer resolves), `playwright` and `brightdata` (origin
returns Cloudflare 502 — Access accepts the credentials, the service behind it does not answer),
and `n8n` (`npx -y n8n-mcp` exits with `Cannot find module 'zod'`, broken upstream).

Removal runs off `~/.agents/.mcp-lock.json`, not off the manifest — by the time the renderer sees
a disabled server, the only record that it was ever installed is the lock. Both the disabling and
the re-enabling are idempotent, and `--list` reports what is currently parked.

### Why a manifest and not a store

Skills get portability for free because they are inert files: one store, one symlink per agent.
MCP configuration cannot work that way. It is structured state, and every agent keeps it in its
own file, under its own key, in its own dialect — there is nothing to symlink, so the manifest has
to be **written** rather than linked. That renderer is the whole mechanism.

### Credentials decide what is portable

A credential is never a value in the manifest. It is `{"env": "NAME"}` — a reference to an
environment variable, resolved by the agent at connect time. Every `NAME` has an `export` in
`~/.config/secrets.zsh`, which yadm keeps gpg-encrypted. That indirection is what makes the
manifest safe to commit, and it is also the thing the agents disagree about:

| Agent | Config file | stdio `env` | HTTP headers |
| --- | --- | --- | --- |
| Oh My Pi | `$PI_CONFIG_DIR/agent/mcp.json` → `mcpServers` | `${NAME}` | `${NAME}` |
| opencode | `~/.config/opencode/opencode.json` → `mcp` | `{env:NAME}` | `{env:NAME}` |
| VS Code | `~/.config/Code/User/mcp.json` → `servers` | `${env:NAME}` | `${env:NAME}` |
| Codex | `~/.codex/config.toml` → `[mcp_servers]` | literal only — shimmed, see below | `env_http_headers`, `bearer_token_env_var` |
| Cursor | `~/.cursor/mcp.json` → `mcpServers` | `${env:NAME}` | unresolved for remote servers |
| Gemini CLI | `~/.gemini/settings.json` → `mcpServers` | `$NAME` | literal only |

Oh My Pi's two rows are verified by reading 17.2.9: its loader maps a `${NAME}` /
`${NAME:-default}` expander over the whole parsed `mcpServers` object, so every string at any
depth is substituted and an unresolved reference is left literal rather than emptied. The rest
are the agents' own documentation and open issues. Fifteen of the seventeen
servers are HTTP with the secret in a header, so those last two rows are not a detail — **Cursor
and Gemini CLI can only take the two stdio servers.** They are skipped with a printed reason
rather than written with a literal `${TOKEN}` that would go out as a credential. Codex is the
mirror image: its `env_http_headers` covers all fifteen HTTP servers, and its stdio `env` covers
none of them.

Process inheritance does not save the stdio ones there, as it does elsewhere: **Codex scrubs the
environment** before it spawns one. Probed on codex-cli 0.146.0 with
a server whose command was `env`: the child sees exactly `HOME LANG LOGNAME PATH PWD SHELL TERM
USER` plus the literal `[mcp_servers.x.env]` table, and nothing the launching shell exported.
`shell_environment_policy.inherit = "all"` does not reach it either — the probed environment was
identical.

So for Codex the reference is resolved one level down, by the launch instead of by the agent
(`env: 'shim'`, `envShimCommand` in the renderer). The command becomes `sh -c`, which sources the
same `~/.config/secrets.zsh` and re-execs the real program through `env -i` carrying Codex's own
core set plus *only* the variables that server's manifest entry names — so config.toml still holds
no secret, and sourcing a file of thirty-odd exports leaks none of the others into the server. A
variable unset at spawn time is dropped rather than passed empty: `BW_SESSION` is minted per shell
by `bwunlock` and exists on no disk, so under Codex the Bitwarden server starts locked and its own
`unlock` tool establishes the session.

`--materialize` writes the real values instead, for a target that cannot reference them. It is
opt-in, chmods the file to `0600`, and warns: it turns a committed-safe reference into a secret at
rest, and rotating a credential then means re-running the renderer.

### What it will not clobber

Every target belongs to its agent, not to this repo — `opencode.json` and Gemini's
`settings.json` hold that agent's entire configuration, and the MCP servers are one key in it.
So the JSON targets are merged key-scoped and written through a temp file, with a `.bak` of the
previous contents, and the rename is refused outright if the file changed on disk between the
read and the write: an agent that has it open would otherwise lose whatever it wrote in the
meantime. `config.toml` cannot be merged structurally without a TOML
parser, and this repo stays dependency-free, so the Codex adapter owns a delimited block and
leaves hand-written TOML above and below it alone. `~/.agents/.mcp-lock.json` records what was
written where — alongside `.skill-lock.json`, and for the same reason: a server dropped from the
manifest has to be removed from the agents too, and the installed artefacts are disposable while
the record of them is not.

## Authoring

```sh
git -C ~/code/perso/agent-skills pull
$EDITOR skills/<category>/<skill>/SKILL.md
node scripts/validate.mjs
# reinstall the store from the working tree
npx -y skills add ~/code/perso/agent-skills --skill '*' -g --yes
```

The install **copies** into `~/.agents/skills/<name>`; edits in this working tree are not live.
Re-run the add (or `skills update` once pushed) to pick them up. The profile symlinks point at
the store, so they need no touching — a re-add refreshes what they already resolve to.

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
12. Only the eight categories below.

A skill must be **self-contained**: anything it runs lives in its own `scripts/`. Where two skills
need the same helper, both ship a copy rather than sharing one — they install independently and
cannot reach each other.

## Catalog

| Category | Skills |
| --- | --- |
| `engineering` | code-quality-scan, greenfield, plan-hardening, prune-branches |
| `finance` | payment-qr |
| `research` | cite-or-refuse, fact-check-document, harden-case, true-quality |
| `toolbox` | free-disk-space |
| `meta` | executing-autonomously, handoff, no-verbose |
| `health` | tcc |
| `legal` | assurance-fr |
| `helpers` | workspace-attachments |

`skills/<category>/<skill>/SKILL.md` is discovered natively — the CLI walks one extra level inside
`skills/` for exactly this catalog layout. No manifest file is needed. Categories organise the
repo only; installed skills are flat.

## What is deliberately not here

**Eleven retired skills.** `1password-passkey-audit`, `bank-actual-import`, `cancel-trial-courses`,
`document-codebase`, `git-multi-identity-setup`, `plugin-config`, `receipt-split`, `track-case`,
`two-axis-review`, `update-documentation` and `writing-technical-specs` were removed on 2026-07-31.
Git history is the archive — nothing is vendored into an `archive/` directory, because the `skills`
CLI discovers any `SKILL.md` two levels down from the repo root and would reinstall them. Restore
one with `git checkout 9c9c809 -- skills/<category>/<skill>`. Their departure emptied the
`ops` and `security` categories, which went with them.

**Two more retired skills.** `linear-project-sync` and `spec-to-pr` were removed on 2026-08-17.
Restore either with `git checkout 65cd4c3 -- skills/engineering/<skill>`.

**The `trackers` category and its CLI.** `track-case` was the only thing that ever shelled out to
`~/.agents/plugins/trackers/scripts/trackers`, so retiring it left the plugin with no caller — no
cron entry, no timer, and no `~/.claude-trackers` state dir referenced it either. The plugin is
gone from the machine and from the dotfiles. `harden-case` outlived the category because it never
used the CLI: it reads a case directory and whatever conventions that repository declares, so it
moved to `research` beside the other verification skills.

**A second reviewer per task.** `spec-to-pr` used to run a spec reviewer and a quality reviewer in
parallel on every task, then delegate a whole-branch pass to `two-axis-review`. Both collapsed into
one general reviewer that answers both questions — per task in Phase 4, and once over the assembled
branch in Phase 7. The independence that mattered was the reviewer not being the implementer, which
one agent in a fresh context provides just as well as two.

**A GitHub mirror.** This lived briefly at `Ephasme/agent-skills` before moving here. There is no
mirror and no sync — Forgejo is the only remote.

**`.mcp.json` files.** The nineteen servers in `mcp/servers.json` came from the purpose-plugins
that used to carry these skills, removed from the dotfiles on 2026-07-31 in yadm commit `1803e8c`
(still restorable with `yadm checkout debe473 -- .agents/plugins`). They are not stored in that
shape any more, because a plugin's `.mcp.json` is loaded only by the agent whose plugin system
ships it — and it was carrying the servers for exactly one of them. The manifest plus the
renderer was the agent-neutral replacement: every harness's MCP file rendered rather than
hand-maintained, from one declaration. Both moved into `~/.config/tack/config.yaml` on
2026-08-16 — same design, one record fewer.

**Third-party skills.** One is installed: `gnhf`, from `kunchenguid/gnhf`, tracked by name in
`~/.agents/.skill-lock.json` rather than vendored here — a copy in this repo would fork it off
upstream updates. `tamagui`, `find-skills` and `web-design-guidelines` were dropped on 2026-07-31;
they were recorded in the lock but present nowhere on disk, so the record was removed and
`scripts/bootstrap.sh` no longer reinstalls them. Copies sit in `~/code/perso/ai-backups/skills.bkp/`.

**The `agents/` directory.** `tcc-expert.md` and `assurance-fr.md` are the two files here that the
portability contract does not reach: a subagent definition is a per-product format, and these are
written to omp's task-agent contract — `autoloadSkills`, a full `model` selector, `thinking-level`,
`read-summarize`. Each is kept beside the skill it drives and autoloads that skill rather than
restating it, which is why the pair lives here instead of in the omp config. The `skills` CLI
installs skills only, so activation is a symlink made by hand, per profile that should see the
agent:

```sh
ln -s ~/code/perso/agent-skills/agents/tcc-expert.md \
      ~/.omp/profiles/perso/agent/agents/
```
