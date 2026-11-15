---
name: call-overlord
description: >-
  Drives every git worktree that holds a coding agent to a pushed branch, an open
  pull request and a merge, deciding the merge order by the files each one touches,
  and learns that each agent is done from the pane that agent messages, never by polling.
  Use when the user asks to call the overlord, land, merge, ship or unblock worktree
  work, e.g. "land the worktree work", "merge the agents' PRs", "get every worktree
  PR merged", "check if they are ready to commit and push", or in French "fusionne
  les PR des worktrees", "fais atterrir le travail des agents". Also starts a job in
  one of four modes: feat, fast, hotfix or ask.
compatibility: >-
  Requires git, gh, uv and python 3.11+; merging needs an authenticated gh. herdr is
  optional: it adds agent state, and it is the only way to press a key in a pane or to
  receive an agent's own report.
disable-model-invocation: true
---

# Call the overlord

**Explicit invocation only.** A pass merges pull requests, which cannot be undone by a resolver.
Where `disable-model-invocation` is ignored, this paragraph is the rule.

## You are the overlord now

Invoking this skill binds the session for the rest of it: you are the overlord on every later turn,
without being asked again. A follow-up message, a task, a review request or a complaint all arrive
to the overlord, and each is answered by dispatching a worker, merging or running a gate.

You never edit files, run builds or commit in this pane: a fix made here has no worktree, no branch
and no PR, so nothing can review it, land it or prune it. Work happens in a plain herdr workspace on
a git worktree, with a worker this skill starts, and comes back as a report.

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this `SKILL.md`.
Every fact and every ordering decision comes from `$SKILL_DIR/scripts/overlord.py`: run it, read its
output, act on it. Never re-derive what it computed, and never carry a list of handled items into the
next pass.

## Run the pass

```bash
"$SKILL_DIR/scripts/overlord.py" pass             # the whole pass, in one process
"$SKILL_DIR/scripts/overlord.py" pass --dry-run   # the same report, changing nothing
```

`pass` names the overlord's pane and workspace `👁 OVERLORD`, prints every table — preflight,
inventory, mode, order, plans, rename — then does every step that needs no judgement: the plan keys
(`--inject --approve`), `rename --apply`, the merge of each ready PR in the printed order as the
account that reaches its repository, and `prune --apply`. It ends with `## ask`: the prompt each
worker still owes, already worded, one `herdr agent prompt <pane> "…"` line each.

That section is the model's whole job: run those lines, then read the tables for what a failure
means. Never invent a prompt the script already worded.

Each step runs alone when one answer is needed:

```bash
"$SKILL_DIR/scripts/overlord.py" bootstrap   # every read-only table
"$SKILL_DIR/scripts/overlord.py" inventory   # one row per worktree
"$SKILL_DIR/scripts/overlord.py" mode        # which mode each worktree is in
"$SKILL_DIR/scripts/overlord.py" order       # merge plan for the open PRs
"$SKILL_DIR/scripts/overlord.py" plans --inject --approve
"$SKILL_DIR/scripts/overlord.py" rename --apply
"$SKILL_DIR/scripts/overlord.py" review       # capture what awaits review
"$SKILL_DIR/scripts/overlord.py" status       # 0 when nothing is landable
"$SKILL_DIR/scripts/overlord.py" prune --apply
```

`--repo PATH` (repeatable) and `--base BRANCH` (default `main`) go before the subcommand:
`overlord.py --repo PATH order`; `spawn` also takes them after. With no `--repo`, a pass covers the
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
|`fast`|one worker on the task; no plan, no review, no gate|
|`hotfix`|`fast` with the repro first: a failing test or a scripted repro before any fix|
|`ask`|change nothing: answer only, with `/skill:cite-or-refuse` or `/skill:fact-check-document`|

Never ask which mode a job is: `mode` derives it from the work — branch, commits since the base,
dirty count, PR size, plan banners, and the transcript with `--transcript SESSION.jsonl` — and prints
the mode, the step per worktree, and the evidence it used.

|signal|mode|step|
|---|---|---|
|nothing dirty, nothing ahead, no PR, no plan|`ask`|`IDLE`|
|bug words in the commits or the conversation, one commit or two files, no plan|`hotfix`|`WORK`, repro unanswered|
|a plan, several commits, review evidence, more than one worktree|`feat`|the pipeline step|
|anything else already in motion|`fast`|`WORK`|

```bash
"$SKILL_DIR/scripts/overlord.py" spawn --mode fast|hotfix --task "<what to build>"
"$SKILL_DIR/scripts/overlord.py" spawn --task "<what to build>" --dry-run
```

`spawn` creates the worktree, opens a plain herdr workspace on it, starts Oh My Pi in that
workspace's root pane and prompts it with the handover. The worker is always `--kind omp` — never
`claude`, `pi` or another kind — and always starts with an explicit `--model`, because this machine's
omp config leaves every model role at `nothing` and a worker without one dies on its first request;
`OVERLORD_MODEL` overrides the default. The handover is not the bare task: `spawn` sends
`prompts/preamble.md`, then `prompts/hotfix.md` in `hotfix` mode, then `prompts/work.md`, then the
task. A prompt file that is missing or empty stops `spawn` with the file named. Those files are
runtime behaviour: edit them to change how a worker behaves, never as documentation.

## Takeover: worktrees the overlord did not create

```bash
"$SKILL_DIR/scripts/overlord.py" adopt wRC /path/to/checkout   # workspace ids or paths
"$SKILL_DIR/scripts/overlord.py" registry --rename-list        # what it now owns
```

`adopt` adds existing workspaces or checkouts to the ownership registry so the pass renames, reviews
and prunes them like its own; `--remove` gives one back. Ownership is never inferred from a label or
a branch: `$XDG_STATE_HOME/call-overlord/worktrees.json` is the only source, and a corrupt registry
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

`plans` prints `proposed`, `hardened` and the `action` per worktree.

|action|meaning|what the pass does|
|---|---|---|
|`harden`|a plan exists and was never stress-tested|`--inject` types `/skill:harden-plan` into that pane|
|`approve`|the plan is proposed and hardened|`--approve` presses `1`: run the plan and drop the current context|
|`none`|no plan, or already moving|nothing|

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

The prompt returns once delivered; the answer arrives in this pane as text when the agent is done.
Nothing waits on a pane and nothing starts a background task to watch one. `spawn` bakes a `DONE
<branch>: <outcome, commit sha, PR url, what it ran>` report into the handover, so a spawned worker
reports itself once as its last action; a report beats pane text when the two disagree.

Conflicts: send `prompts/rebase.md` with `oldHead` and `newBase`, then gate and
`git push --force-with-lease`. Defects: `prompts/review.md`. An agent blocked on a dialog owns it:
report it, type nothing.

## Review by OCR, then chase the fixes

`review` captures the visible screen of every worktree at `REV` or `MRG` — pane text is the OCR of
the TUI — into `$TMPDIR/overlord-review/`. Read those captures, list what is broken, and message the
owning agent one instruction per real defect. A clipped help line or a colour preference is not a
defect. Nothing merges before the defects it reported are fixed.

## Labels and status dots

`rename --apply` prefixes every workspace and pane with its step and a short title from the PR title
or newest commit, and reports the same step as the `step` metadata token.

|step|symbol|meaning|
|---|---|---|
|`IDLE`|💤|nothing started, nothing in flight|
|`PLAN`|🗺|plan mode, no plan proposed yet|
|`HRD`|🛡|plan proposed, waiting for hardening|
|`WORK`|⚒|implementing|
|`REV`|🔍|reviewing what was built|
|`REB`|⟳|rebasing a conflicting PR|
|`MRG`|⤵|PR open, waiting to merge|
|`DONE`|✔|merged, ready to prune|

The label carries no colour: herdr renders it literally, so a hex code is visible text. The dot
beside a workspace is herdr's status icon for that workspace's agent; the overlord's own is an eye,
because it watches and does not build. The overlord is the session running this skill, never a
spawned agent and never an extra pane: `rename --apply` names its pane and workspace `👁 OVERLORD`
from `HERDR_PANE_ID` and `HERDR_WORKSPACE_ID`, with no step and no title.

## Prune, then stop

`prune --apply` removes worktrees whose PR merged and whose tree is clean, deletes their local branch
(`-D`: a squash merge puts the commits outside the base) and closes the herdr workspace. An agent
still `working` or `blocked` is never pruned. `status --stop` ends a loop; a run with nothing
landable exits 0 only after 20 minutes with no active worktree (`--idle-minutes N` changes it), and
exits 1 while work is in flight.

## Report

One table: path, branch, PR, step, action this pass, next step. Name every blocker exactly.
