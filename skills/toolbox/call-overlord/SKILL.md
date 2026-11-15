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
  one of four modes: fast, hotfix, feat or ask.
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

Calling this skill binds the session for the rest of it: you are the overlord, and you stay the
overlord on every later turn without being asked again. The role survives the turn that invoked
it — a follow-up message, a task, a review request or a complaint all arrive to the overlord, and
each is handled by dispatching a worker, merging, or running a gate, never by writing code here.

What that rules out: editing files, running builds or committing in this pane, spawning an agent
other than Oh My Pi (`--kind omp`), and creating the worktree as a herdr worktree. Work happens in
a plain herdr workspace on a git worktree, with a worker this skill starts (`spawn`), and comes
back to this pane as a report.

It reports on and merges inside the realm only: what you named, adopted, spawned or opened in
herdr. Nothing else is scanned.

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this `SKILL.md`.

Every fact and every ordering decision comes from `$SKILL_DIR/scripts/overlord.py`. Run it, read its
output, act on it. Never re-derive what it already computed, and never carry a list of handled items
into the next pass.
Starting a job means creating a worktree and giving one worker the task: `git worktree add -b
worktree/<slug> <path> origin/<base>`, then start an agent there and hand it the task. In `hotfix`
the repro comes first, as the first instruction, so the worker watches the failure before fixing it.

## The overlord's pane merges, it does not build

The overlord's own pane runs `overlord.py` and merges. Every code change, gate run and commit
happens in a herdr agent pane inside a git worktree: a fix made in the overlord's pane has no
worktree, no branch and no PR, so nothing can review it, land it or prune it.

## Pick the mode yourself

```bash
"$SKILL_DIR/scripts/overlord.py" mode [--transcript SESSION.jsonl]
```

Never ask which mode a job is: derive it. `mode` reads the work itself — branch, commits since the
base, dirty count, PR size, plan banners, and the transcript when one is given — and prints the mode
plus the step per worktree, with the evidence it used:

|signal|mode|step|
|---|---|---|
|nothing dirty, nothing ahead, no PR, no plan|`ask`|`IDLE`|
|bug words in the commits or the conversation, one commit or two files, no plan|`hotfix`|`WORK`, with the repro unanswered|
|a plan, several commits, review evidence, more than one worktree|`feat`|the pipeline step|
|anything else already in motion|`fast`|`WORK`|

Same facts in, same answer out: the rules are ordered and fixed, and every row prints why it chose.

## Targets that are not repositories

A directory with no git in it is still a target: `adopt /some/folder` registers it, and the pass
keeps it in the inventory with its VCS facts off (`branch -`, zero ahead, no PR). What that switches
off, exactly:

|feature|without git|
|---|---|
|branch, ahead, upstream, dirty count, PR state|absent: shown as `-`|
|merge, rebase, readiness|not applicable: `status` never counts it as landable|
|prune|never removes it|
|rename, review, plans, modes|unchanged: they only need herdr and the pane|

The same target stays visible so its agent is still asked, reviewed and renamed — only the merge half
of the pipeline disappears. Nothing is guessed to fill the gap.

## Preflight

```bash
"$SKILL_DIR/scripts/overlord.py" preflight           # ok/absent per dependency
"$SKILL_DIR/scripts/overlord.py" preflight --refresh # check again, then store the verdict
"$SKILL_DIR/scripts/overlord.py" preflight --apply   # install what brew can
```

It checks git, gh, uv, python 3.11+, the gh logins and herdr's availability, and installs the
absent Homebrew packages. The verdict is stored under `preflight:` in `~/.overlord/config.yaml` and
reprinted on later runs, so a pass never re-probes: `--refresh` and `--apply` are the only ways to
check again, and deleting that block does the same. A stored `ok` outlives a revoked token — the
GitHub API says so on the first request. One thing preflight cannot finish alone: `gh auth login`
needs a human.


## Realm: what a pass sees

A repository enters the realm when you name it with `--repo`, adopt it, spawn a job in it, or hold
it open in herdr — the last without an `adopt`. No directory is scanned for others: a repository
outside that set is invisible to every command. `order` and `status` read that set, and `prune`
deletes only what the registry owns.


## Jobs: pick a mode first

|mode|what happens|
|---|---|
|`feat`|the default: the whole pipeline below — plan, harden, review, rebase, merge, prune|
|`fast`|no pipeline: spawn one worker on the task and let it run; start no plan, no review, no gate|
|`hotfix`|`fast` with the failure reproduced first: insert the bug — a failing test or a scripted repro — before the worker starts|
|`ask`|change nothing: answer only, with `/skill:cite-or-refuse` or `/skill:fact-check-document`|

`overlord.py spawn --mode fast|hotfix --task "<what to build>"` creates the worktree, opens a plain
herdr workspace on it, starts Oh My Pi in that workspace's root pane and prompts it with the
handover; with `--dry-run` it prints the commands it would run and creates nothing. The worker is
always `--kind omp` — never `claude`, `pi` or any other kind — and always starts with an explicit
`--model`: this machine's omp config leaves every model role at `nothing`, so a worker started
without one dies on its first request. `OVERLORD_MODEL` overrides the default
(`omniroute/anthropic/claude-opus-4.5`). The handover is not the bare task: `spawn` reads
`$SKILL_DIR/prompts/` and sends `preamble.md`, then `hotfix.md` in `hotfix` mode, then `work.md`,
then the task: the repro is the first thing the worker does, never after it starts implementing. A
prompt file that is missing or empty stops `spawn` with the file named, rather than sending a
shorter handover. Those files are runtime behaviour: edit them to change how a worker behaves, never
as documentation.

## Reach: anywhere the tools work

A target is a path, not a repo in this directory tree. `--repo PATH` accepts any checkout, and every
path in the ownership registry is scanned as well, so an adopted worktree in another repository or
another disk is overseen without naming its repo. `spawn --dest DIR` puts a new worktree wherever the
job belongs instead of under `~/.herdr/worktrees/<repo>`.

Compatibility is the only limit: a target needs git for its facts, `gh` for its pull request, and
herdr in `HERDR_ENV=1` for the parts that press a key or read a screen. Where herdr is absent those
steps are skipped and reported as skipped, never guessed.

The rename tool obeys the same rule: it renames any workspace or worktree the overlord requires —
registry-owned only — wherever it lives, and refuses anything it does not own, rather than inferring
ownership from a label.

## Takeover: worktrees the overlord did not create

```bash
"$SKILL_DIR/scripts/overlord.py" adopt wRC /path/to/checkout   # workspace ids or paths
"$SKILL_DIR/scripts/overlord.py" registry --rename-list        # what it now owns
```

`adopt` adds existing workspaces or checkouts to the ownership registry, so the pass renames,
reviews and prunes them like its own. Ownership is never inferred from a label or a branch: the
registry at `$XDG_STATE_HOME/call-overlord/worktrees.json` is the only source, `--remove` gives one
back, and a corrupt registry is an error rather than an empty list. Adoption is a takeover, prune
included: a merged, clean, idle adopted worktree is removed like any other.

Adoption moves the target into the overlord's own realm, unconditionally: the herdr workspace
holding that path is closed — a `working` agent included — and the path reopens as a new workspace
below the overlord (`workspace create --cwd`). herdr refuses `worktree open --workspace` across
repositories, so it is never used, and a target is never a tab or a nested workspace under the
overlord: it gets a workspace of its own. The agent the close killed is restarted in the new pane
from the session file `agent list` reported (`agent_session.value`) and prompted to resume that
file; a restart or prompt that fails is reported, never retried silently.

The `realm` column says what happened: `<held>→<new>, agent resumed`, `opened <ws>, no agent`,
`in realm <ws>`, `kept: <ws> refused to close`, and `no herdr: not moved` without `HERDR_ENV=1`,
where the registry is written but nothing moves.

## One command runs the pass

```bash
"$SKILL_DIR/scripts/overlord.py" pass             # everything below, in one process
"$SKILL_DIR/scripts/overlord.py" pass --dry-run   # the same report, changing nothing
```

`pass` runs the scripted pipeline: it names the overlord's own pane and workspace `👁 OVERLORD`,
prints every table — preflight, inventory, mode, order, plans, rename — then does the steps no
judgement is needed for: the plan keys (`--inject --approve`), `rename --apply`, the merge of every
ready PR in the printed order with the account that reaches its repository, and `prune --apply`.
It ends with `## ask`: the prompt each worker still owes, already worded, one
`herdr agent prompt <pane> "…"` line per worktree.

That last section is the model's whole job: run those commands, then read the tables for what a
failure means. Never re-derive a decision the script already printed, and never invent a prompt it
already worded. One GitHub round trip and one git probe per worktree, instead of one of each per
command.

Each step stays runnable alone, when one answer is needed or a failure needs a judgement:

```bash
"$SKILL_DIR/scripts/overlord.py" bootstrap                  # 1. where everything stands
"$SKILL_DIR/scripts/overlord.py" plans --inject --approve   # 2. review gate
"$SKILL_DIR/scripts/overlord.py" rename --apply             # 3. step labels on every pane
"$SKILL_DIR/scripts/overlord.py" review                     # 4. capture what awaits review
"$SKILL_DIR/scripts/overlord.py" status                     # 5. anything left? 0 = stop
"$SKILL_DIR/scripts/overlord.py" prune --apply              # 6. drop the landed worktrees
```

Each subcommand takes `--repo PATH` (repeatable) and `--base BRANCH` (default `main`). With no
`--repo`, a pass covers the current directory when it is a checkout, plus every registry and
repository open in herdr. Top-level flags precede the subcommand: `overlord.py --repo PATH order`.
`survey`, `labels`, `relabel` and `verify` are dispatched before argparse, so they take those global
flags as well as their own.

## Plans outrank the merge queue

`plans` prints `proposed`, `hardened` and the `action` per worktree.

|action|meaning|what the pass does|
|---|---|---|
|`harden`|a plan exists and was never stress-tested|`--inject` types `/skill:harden-plan` into that pane|
|`approve`|the plan is proposed and hardened|`--approve` presses `1`: run the plan and drop the current context|
|`none`|no plan, or already moving|nothing|

Never rewrite another agent's plan file; the harden skill carries its own revision rules.

## Order by touched files, and merge everything

`order` prints the merge plan for the realm: clusters of PRs whose files intersect, smallest file set
first, a stacked PR after its base, and the blockers that hold each one back. Every open PR of every
realm repository is listed, checked out locally or not; the `worktree` column names the local
checkout or `-`, which is a PR to adopt a worktree for, not one to skip. The `account` column names
the gh login that reaches that repository: gh holds one active account per host, so a command that
omits it acts as the wrong login and 404s. Merge in that printed order.

Ordering exists only to minimise conflicts: **every open PR of the realm ends merged.** A PR that is
not `ready` yet is a job for the next pass, never a candidate to abandon.

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

The prompt returns as soon as it is delivered; the answer arrives in this pane when the agent is
done. Nothing here waits on a pane, and nothing starts a background task to watch one.

Conflicts: send `$SKILL_DIR/prompts/rebase.md` with `oldHead` and `newBase`, then gate and
`git push --force-with-lease`. Defects: `$SKILL_DIR/prompts/review.md`. An agent blocked on a dialog
owns it: report it, type nothing.

## Review by OCR, then chase the fixes

`review` captures the visible screen of every worktree at `REV` or `MRG` — the pane text is the OCR
of the TUI — into `$TMPDIR/overlord-review/`. Read those captures, list what is actually broken, and
message the owning agent one instruction per real defect. Drop the meaningless ones: a clipped help
line or a colour preference is not a defect. Nothing merges until the defects it reported are fixed.

## Labels and status dots

`rename --apply` prefixes every workspace and pane with its step and a short title taken from the PR
title or newest commit, and reports the same step as the `step` metadata token.

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

The label carries no colour, and must not: herdr renders a label literally, so a hex code in it is
visible text. The dot beside a workspace is herdr's own status icon for that workspace's agent.

The overlord's own dot is an eye: it watches, it does not build. The overlord is the session that
runs this skill, never a spawned agent or an extra pane: `rename --apply` names both its pane and
the workspace holding it `👁 OVERLORD` — from `HERDR_PANE_ID` and `HERDR_WORKSPACE_ID` — with no
step and no title, and a second pane must never be created to hold it.

## Report back

The overlord never waits on a pane and never starts a background task to watch one. It sends its
instruction and moves on; the answer arrives as text in its own pane, which it reads when its turn
resumes:

```bash
herdr agent prompt <overlord_pane> "DONE <branch>: <outcome, commit sha, PR url, what it ran>"
```

`spawn` bakes that clause into the handover with the overlord's pane id, so a spawned worker reports
itself once, as its last action. Outside a spawned job the same line is the answer to any
instruction: one message per decision, and a report beats pane text when the two disagree.

## Prune, then stop

`prune --apply` removes worktrees whose PR merged and whose tree is clean, deletes their local branch
(`-D`: a squash merge puts the commits outside the base) and closes the herdr workspace. Agents still
`working` or `blocked` are never pruned.

`status --stop` ends a loop. A run with nothing landable exits 0 only after 20 minutes with no active
worktree (`--idle-minutes N` changes it): with work in flight it exits 1, so a loop keeps going
until either everything landed or the worktrees went quiet.

## Report

One table: path, branch, PR, step, action this pass, next step. Name every blocker exactly.
