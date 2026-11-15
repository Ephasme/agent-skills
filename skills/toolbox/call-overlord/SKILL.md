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

It checks git, gh, uv, python 3.11+, the GitHub token and herdr's availability, and installs the
absent Homebrew packages. The verdict is stored under `preflight:` in `~/.overlord/config.yaml` and
reprinted on later runs, so a pass never re-probes: `--refresh` and `--apply` are the only ways to
check again, and deleting that block does the same. A stored `ok` outlives a revoked token — the
GitHub API says so on the first request. One thing preflight cannot finish alone: `gh auth login`
needs a human.


## Discovery: only the roots you name

A pass covers `--repo`, the ownership registry, and the repositories discovery found. Nothing is
found until `~/.overlord/config.yaml` names the directories to look in:

```yaml
discovery:
  roots:
    - ~/code/perso
```

`discover` lists each checkout directly under a root — its slug, its base branch, and whether this
token can read it — and writes `~/.overlord/caches/discovery.yaml`. That cache serves passes for
24 h, then a rescan replaces it; `discover --refresh` rescans now, and `--root DIR` scans a root the
config does not name. A repository the token cannot read stays listed as `gh no`, so its pull
requests are named as invisible instead of missing.


## Jobs: pick a mode first

|mode|what happens|
|---|---|
|`feat`|the default: the whole pipeline below — plan, harden, review, rebase, merge, prune|
|`fast`|no pipeline: spawn one worker on the task and let it run; start no plan, no review, no gate|
|`hotfix`|`fast` with the failure reproduced first: insert the bug — a failing test or a scripted repro — before the worker starts|
|`ask`|change nothing: answer only, with `/skill:cite-or-refuse` or `/skill:fact-check-document`|

`overlord.py spawn --mode fast|hotfix --task "<what to build>"` creates the worktree and starts the
worker; with `--dry-run` the script prints the command it would run and creates nothing.
The handover is not the bare task: `spawn` reads `$SKILL_DIR/prompts/` and sends `preamble.md`,
`work.md`, then the task, inserting `hotfix.md` between the rules and the task in `hotfix` mode so
the repro is the first instruction the worker reads. A prompt file that is missing or empty stops
`spawn` with the file named, rather than sending a shorter handover. Those files are runtime
behaviour: edit them to change how a worker behaves, never as documentation.

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

## The feat pipeline, in six commands

`bootstrap` prints every read-only table — preflight, discover, inventory, mode, order, plans, and
the labels `rename` would set — in one process: one GitHub round trip and one git probe per
worktree, instead of one of each per command. Run the single commands when you need one answer.

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
discovered repository. Top-level flags precede the subcommand: `overlord.py --repo PATH order`.
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

`order` prints the merge plan: clusters of PRs whose files intersect, smallest file set first, a
stacked PR after its base, and the blockers that hold each one back. Every open PR of every
repository in scope is listed, checked out locally or not; the `worktree` column names the local
checkout or `-`, which is a PR to adopt a worktree for, not one to skip. Merge in that printed order.

Ordering exists only to minimise conflicts: **every open PR ends merged.** A PR that is not `ready`
yet is a job for the next pass, never a candidate to abandon.

```bash
gh pr merge <n> -R <slug> --squash --delete-branch
```

`--merge` only where squash is forbidden. A failed merge is not a merge: read the error, act on it.

## Ask the owning agent

Never edit another agent's branch.

```bash
herdr agent prompt <pane_id> "<instruction>"
```

The prompt returns as soon as it is delivered. The owning agent answers when it is done, in this
overlord's own pane, as described in "Report back": nothing here waits on a pane, and nothing here
starts a background task to watch one.

`needs-check`/`needs-pr`: rebase if stale, run the repo gate, commit its way, push, then `gh pr
create -R <slug> --base <base> --head <branch> --fill`. `conflicting`: send it
`$SKILL_DIR/prompts/rebase.md` with the two refs, then gate and `git push --force-with-lease`.
`agent_blocked` owns a dialog: report it, type nothing. `no-agent`: do the git work yourself and say
so.

Defects are chased with `$SKILL_DIR/prompts/review.md`: trace an input through the change, anchor
each finding at `file:line`, fix at most twice.

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
