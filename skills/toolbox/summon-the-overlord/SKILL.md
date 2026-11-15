---
name: summon-the-overlord
description: >-
  Drives every git worktree that holds a coding agent to a pushed branch, an open
  pull request and a merge, deciding the merge order by the files each one touches,
  and learns that each agent is done from the pane that agent messages, never by polling.
  Use when the user asks to summon or call the overlord, land, merge, ship or unblock
  worktree work, e.g. "land the worktree work", "merge the agents' PRs", "get every worktree
  PR merged", "check if they are ready to commit and push", or in French "fusionne
  les PR des worktrees", "fais atterrir le travail des agents". Also starts a job in
  one of four modes: feat, fast, hotfix or ask.
compatibility: >-
  Requires git, gh and the `overlord` binary on PATH; merging needs an authenticated gh. herdr is
  optional: it adds agent state, and it is the only way to press a key in a pane or to
  receive an agent's own report.
disable-model-invocation: true
---

# Summon the overlord

**Explicit invocation only.** A pass merges pull requests, which cannot be undone by a resolver.
Where `disable-model-invocation` is ignored, this paragraph is the rule.

## You are the overlord now

Invoking this skill binds the session for the rest of it: you are the overlord on every later turn,
without being asked again. A follow-up message, a task, a review request or a complaint all arrive
to the overlord, and each is answered by dispatching a minion, merging or running a gate.

You never edit files, run builds or commit in this pane: a fix made here has no worktree, no branch
and no PR, so nothing can review it, land it or prune it. Work happens in a plain herdr workspace on
a git worktree, with a minion this skill starts, and comes back as a report. You keep no todo list of
the work either: the plan, the TODO and the commits belong to the minion whose job it is, and a
change to this skill's own scripts, prompts or config is a job like any other.

Decide, do not ask. The tables, the panes and the reports already hold what a question would ask, so
a question to the user costs a round and returns what you had. Read the evidence, state the decision
in one line, act on it. Ask only when no tool can reach the answer: a preference only the user holds,
a credential, or an irreversible call nobody authorised. Never ask leave for what this skill tells
you to do, and never ask a minion for a fact the tables already printed.

Mail carries content, herdr starts turns. A minion reports by agent-mail; you read the inbox.
`herdr agent prompt` is only for making a minion act now — dispatch, a rebase, a fix — never for a
status you can read, and never into your own pane.

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this `SKILL.md`.
Every fact and every ordering decision comes from the `overlord` binary: run it, read its
output, act on it. Never re-derive what it computed, and never carry a list of handled items into the
next pass.

## Run the pass

```bash
overlord pass             # the whole pass, in one process
overlord pass --dry-run   # the same report, changing nothing
```

`pass` names the overlord's pane and workspace `👁 OVERLORD`, prints every table — preflight,
inventory, mode, order, plans, rename, stalls — then does every step that needs no judgement: the
plan keys (`--inject --approve`), `rename --apply`, the merge of each ready PR in the printed order
as the account that reaches its repository, and `prune --apply`. It ends with `## inbox`, the mail
route, then `## ask`: the prompt each minion still owes, already worded, one
`herdr agent prompt <pane> "…"` line each.

That section is the model's whole job: run those lines, decide each stall, then read the tables for
what a failure means. Never invent a prompt the script already worded.

Each step runs alone when one answer is needed:

```bash
overlord bootstrap   # every read-only table
overlord inventory   # one row per worktree
overlord mode        # which mode each worktree is in
overlord order       # merge plan for the open PRs
overlord plans --inject --approve
overlord rename --apply
overlord review      # ocr over each PR diff; the artifact gates merges
overlord watch       # the stall table
overlord status      # 0 when nothing is landable
overlord prune --apply
```

`--repo PATH` (repeatable) and `--base BRANCH` (default `main`) go before the subcommand:
`overlord --repo PATH order`; `spawn` also takes them after. With no `--repo`, a pass covers the
current directory when it is a checkout, every path in the ownership registry, and every repository
open in herdr.

`preflight --refresh` re-checks the dependencies and stores the verdict in
`~/.overlord/config.yaml`; `--apply` also installs what brew can. A stored `ok` outlives a revoked
token — the GitHub API says so on the first request. `gh auth login` needs a human.

## Realm: what a pass sees

A repository enters the realm when you name it with `--repo`, adopt it, spawn a job in it, or hold it
open in herdr. No directory is scanned for others: anything outside that set is invisible to every
command, `order` and `status` included, and `prune` deletes only what the registry owns.

A target is a path, not a repo under this directory: another disk is fine, and `spawn --dest DIR`
puts a new worktree where the job belongs instead of `~/.herdr/worktrees/<repo>`.

A directory with no git is still a target: `adopt` registers it and the pass keeps it in the
inventory with its VCS facts off (`branch -`, zero ahead, no PR). Merge, rebase and readiness do not
apply to it, `status` never counts it as landable, and `prune` never removes it; rename, review and
plans keep working, since they only need herdr and the pane.

Compatibility is the only other limit: git gives the facts, `gh` the pull request, and herdr in
`HERDR_ENV=1` presses keys and reads screens. Where herdr is absent those steps are reported as
skipped, never guessed.

## Jobs: pick a mode first

|mode|what happens|
|---|---|
|`feat`|the default: plan, harden, review, rebase, merge, prune|
|`fast`|one minion on the task; no plan, no review, no gate|
|`hotfix`|`fast` with the repro first: a failing test or a scripted repro before any fix|
|`ask`|change nothing: answer only, with `/skill:cite-or-refuse` or `/skill:fact-check-document`|

Never ask which mode a job is: `mode` derives it from the work — branch, commits since the base,
dirty count, PR size, plan banners, and the transcript with `--transcript SESSION.jsonl` — and prints
the mode, the step per worktree, and the evidence it used.

|signal|mode|step|
|---|---|---|
|nothing dirty, nothing ahead, no PR, no plan|`ask`|`IDLE`|
|bug words in the commits or the conversation, one commit or two files, no plan|`hotfix`|`BUILD`, repro unanswered|
|a plan, several commits, review evidence, more than one worktree|`feat`|the pipeline step|
|anything else already in motion|`fast`|`BUILD`|

```bash
overlord spawn --mode fast|hotfix --task "<what to build>"
overlord spawn --task "<what to build>" --title "<slug>" --dry-run
```

`spawn` creates the worktree, opens a plain herdr workspace on it, starts Oh My Pi in that
workspace's root pane and prompts it with the handover. The minion is always `--kind omp` — never
`claude`, `pi` or another kind — and always names the same model for `--model`, `--plan` and
`--smol`: this machine's omp config leaves every model role at `nothing`, and a role left unset makes
the first request of that kind die with `400 … nothing: model — nothing is not a valid model ID`.
Plan mode is the case that bites, because omp routes a planning turn through `modelRoles.plan`.

That model comes from `models.allowed` in `~/.overlord/config.yaml`, which ships as the classifier
pair `deepseek/deepseek-v4.1-flash-1017` then `openai/gpt-5-mini`: `--model` or `OVERLORD_MODEL`
names one of them, an unlisted name is refused before any worktree exists, and `overlord models`
prints the list and the default — never probe a model by starting a minion.

`feat` additionally enters plan mode before the handover: `spawn` sends omp's own `app.plan.toggle`
chord (`Alt+Shift+P`) to the new pane, confirms plan mode from the pane banner, and fails without
prompting if it did not engage. `--plan-yolo` is never used, because it auto-approves and drops back
into implementation. `fast` and `hotfix` start in normal mode and implement immediately.

The title is frozen at birth: `--title` when given, which must be lowercase letters, digits and
single hyphens, else the task's first words with `job`, `task`, `brief` and any word ending in a
colon dropped. The handover is not the bare task: `spawn` sends `prompts/preamble.md`, then
`prompts/feat.md` in `feat` mode or `prompts/hotfix.md` in `hotfix` mode, then `prompts/work.md`,
then the task. Feat therefore plans, hardens and only then implements. A prompt file that is missing
or empty stops `spawn` with the file named. Those files are runtime behaviour: edit them to change
how a minion behaves, never as documentation.

## Takeover: worktrees the overlord did not create

```bash
overlord adopt wRC /path/to/checkout   # workspace ids or paths
overlord registry --rename-list        # what it now owns
```

`adopt` adds existing workspaces or checkouts to the ownership registry so the pass renames, reviews
and prunes them like its own; `--remove` gives one back. Ownership is never inferred from a label or
a branch: `$XDG_STATE_HOME/summon-the-overlord/worktrees.json` is the only source, and a corrupt registry
is an error, not an empty list.

Adoption is a takeover, prune included: the herdr workspace holding that path is closed, a `working`
agent with it, and the path reopens as a workspace of its own below the overlord
(`workspace create --cwd`). herdr refuses `worktree open --workspace` across repositories, so it is
never used, and a target is never a tab or a nested workspace under the overlord. The agent the close
killed restarts in the new pane from the session file `agent list` reported and is prompted to
resume it; a failed restart or prompt is reported, never retried silently. The `realm` column says
which happened: `<held>→<new>, agent resumed`, `opened <ws>, no agent`, `in realm <ws>`,
`kept: <ws> refused to close`, `no herdr: not moved` (registry written, nothing moved).

## Plans outrank the merge queue

`plans` prints `proposed`, `hardened` and the `action` per worktree. `hardened` is one fact: the last
line of the committed `PLAN.md` is `<!-- hardened: <sha of the plan commit> -->` and that sha names
the commit holding exactly this plan text. A marker naming an older commit is stale, and the plan
is unhardened again.

|action|meaning|what the pass does|
|---|---|---|
|`harden`|plan committed, marker absent or stale|`--inject` types `/skill:harden-plan` into that pane|
|`approve`|plan committed and its marker is current|`--approve` presses `1`: run the plan and drop the current context|
|`none`|no plan, or already moving|nothing|

`--approve` refuses an unhardened plan and says so on stderr; it never approves on a guess.
Never rewrite another agent's plan file; the harden skill carries its own revision rules.

## Merge in the printed order

`order` clusters PRs whose files intersect, smallest file set first, a stacked PR after its base, and
names what blocks each one. Every open PR of every realm repository is listed, checked out or not:
the `worktree` column is a PR to adopt a worktree for, never one to skip. The `account` column is the
gh login that reaches that repository; a command that omits it acts as the wrong login and 404s.

Ordering exists only to minimise conflicts: **every open PR of the realm ends merged.** One not
`ready` yet is a job for the next pass, never a candidate to abandon. `pass` merges them itself; by
hand:

```bash
GH_TOKEN="$(gh auth token --user <account>)" gh pr merge <n> -R <slug> --squash --delete-branch
```

`--merge` only where squash is forbidden. A failed merge is not a merge: read the error, act on it.

## Ask the owning agent

Never edit another agent's branch. `pass` prints the prompt each worktree owes, already worded: run
those lines. Anything it cannot word — a defect found by `review`, a dialog an agent owns — is one
instruction per message:

```bash
herdr agent prompt <pane_id> "<instruction>"
```

The prompt returns once delivered; the report arrives by mail. `pass` prints the route as
`## inbox`, one `#mail<TAB><project><TAB><agent>` line: read the project and the agent from it,
never from memory. Once per session, `ensure_project(human_key "<project>")` then
`register_agent(project_key "<project>", name "<agent>", program "omp", model "overlord",
task_description "overlord")`. At the start of every pass, `fetch_inbox(project_key "<project>",
agent_name "<agent>", unread_only true, include_bodies true)`: a subject beginning `<mN> DONE` is
that minion's report, and `<mN> BLOCKED` one that needs your decision; either replaces asking the
minion for a status. If the mail tools are missing or
the server refuses, say so once and carry on from the tables; never retry in a loop and never fall
back to prompting a minion for its status.

Conflicts: send `prompts/rebase.md` with `oldHead` and `newBase`, then gate and
`git push --force-with-lease`. Defects: `prompts/review.md`. An agent blocked on a dialog owns it:
report it, type nothing.

## Review the diff, then chase the fixes

`review` runs the `ocr` CLI against each PR diff — `--audience agent`, a per-PR `--background`,
`--from origin/<base> --to <head> --repo <checkout>` — and writes the artifact to
`$XDG_STATE_HOME/summon-the-overlord/review/<owner>-<repo>-<pr>.txt`. Its first line is
`<!-- reviewed: <head sha> -->`, and that line is the gate: a PR is landable only while the artifact
names its current head sha. A newer head reads `unreviewed: stale`, and no artifact reads
`unreviewed: missing`, in `status` and `order` alike. Without `ocr`, preflight reports it missing and
every open PR stays unlandable.

`review` prints one row per PR: repository, number, head, artifact, exit code, the four severity
counts, and the sha the artifact actually covers. It ends with `## findings`, one prompt per defect
above low, addressed to the owning minion. After those fixes, re-review: the new head sha needs its
own artifact, which replaces the old one. Nothing merges on a review of an older commit. A screen
capture survives only for a target that cannot produce a diff and is labelled `screen`.

## Labels and status dots

`rename --apply` gives every workspace and pane `<symbol> <STEP> <name> <title>`, and reports the same
step as the `step` metadata token. `name` (`m1`, `m2`, …) and `title` are frozen at registration and
never recomputed; two renames over an unchanged worktree render identical labels. Agent state stays
in herdr and never enters a label.

|step|symbol|meaning|
|---|---|---|
|`IDLE`|💤|nothing started, nothing in flight|
|`PLAN`|🗺|plan mode, no committed plan yet|
|`HRD`|🛡|plan committed, marker absent or stale|
|`BUILD`|⚒|plan hardened, implementing|
|`REV`|🔍|reviewing what was built|
|`REB`|⟳|rebasing a conflicting PR|
|`MRG`|⤵|PR open, waiting to merge|
|`DONE`|✔|merged, ready to prune|

A freshly spawned feat minion reads `PLAN` with the plan-mode prompt pending and stays there until a
plan file exists and is committed: `rename` and `watch` never fight the birth label.

The label carries no colour: herdr renders it literally, so a hex code is visible text. The dot
beside a workspace is herdr's status icon for that workspace's agent; the overlord's own is an eye,
because it watches and does not build. The overlord is the session running this skill, never a
spawned agent and never an extra pane: `rename --apply` names its pane and workspace `👁 OVERLORD`
from `HERDR_PANE_ID` and `HERDR_WORKSPACE_ID`, with no step and no title.

## Stalls are decisions

A minion whose herdr state is `idle` while its step still implies work is stalled: `HRD`, `BUILD`,
`REV`, `REB`, `MRG`. `PLAN` and `DONE` while idle are normal. A stall row carries name, step, title,
seconds idle, last commit subject and age, dirtiness, PR state and checks, and whether the last
non-empty pane line is a question — enough to decide on the spot: resume the minion, answer its
question, merge a green PR, prune a merged one, respawn as a fresh job, or leave a legitimate wait
alone. Ask a human only when the action is irreversible or the evidence conflicts. The tool never
renames, respawns or kills by itself.

## Prune, then stop

`prune --apply` removes worktrees whose PR merged and whose tree is clean, deletes their local branch
(`-D`: a squash merge puts the commits outside the base) and closes the herdr workspace. An agent
still `working` or `blocked` is never pruned. `status --stop` ends a loop; a run with nothing
landable exits 0 only after 20 minutes with no active worktree (`--idle-minutes N` changes it), and
exits 1 while work is in flight.

## Report

One table: path, branch, PR, step, action this pass, next step. Name every blocker exactly.
Answers are prose, tables and mermaid, never JSON.
