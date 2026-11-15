---
name: call-overlord
description: >-
  Drives every git worktree that holds a coding agent to a pushed branch, an open
  pull request and a merge, deciding the merge order by the files each one touches,
  and coordinates the agents over a shared Agent Mail project instead of polling.
  Use when the user asks to call the overlord, land, merge, ship or unblock worktree
  work, e.g. "land the worktree work", "merge the agents' PRs", "get every worktree
  PR merged", "check if they are ready to commit and push", or in French "fusionne
  les PR des worktrees", "fais atterrir le travail des agents". Also starts a job in
  one of four modes: fast, hotfix, feat or ask.
compatibility: >-
  Requires git, gh, uv and python 3.11+; merging needs an authenticated gh. The mail
  protocol needs an Agent Mail MCP server reachable by every agent involved. herdr is
  optional: it adds agent state and is the only way to press a key in a pane.
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
## Pick the mode yourself

```bash
"$SKILL_DIR/scripts/overlord.py" mode [--transcript SESSION.jsonl]
```

Never ask which mode a job is: derive it. `mode` reads the work itself — branch, commits since the
base, dirty count, PR size, plan banners, and the transcript when one is given — and prints the mode
plus the step per worktree, with the evidence it used:

|signal|mode|step|
|---|---|---|
|nothing dirty, nothing ahead, no PR, no plan|`ask`|`SEE`|
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
|rename, review, plans, mail, modes|unchanged: they only need herdr and the pane|

The same target stays visible so its agent is still asked, reviewed and renamed — only the merge half
of the pipeline disappears. Nothing is guessed to fill the gap.

## Preflight

```bash
"$SKILL_DIR/scripts/overlord.py" preflight           # ok/absent per dependency
"$SKILL_DIR/scripts/overlord.py" preflight --apply   # install what brew can
```

It checks git, gh, uv, python 3.11+, the GitHub token and herdr's availability, and installs the
absent Homebrew packages. Two things it cannot finish alone: `gh auth login` needs a human, and the
Agent Mail project needs the `ensure_project` call from the mail section below.


## Jobs: pick a mode first

|mode|what happens|
|---|---|
|`feat`|the default: the whole pipeline below — plan, harden, review, rebase, merge, prune|
|`fast`|no pipeline: spawn one worker on the task and let it run; start no plan, no review, no gate|
|`hotfix`|`fast` with the failure reproduced first: insert the bug — a failing test or a scripted repro — before the worker starts|
|`ask`|change nothing: answer only, with `/skill:cite-or-refuse` or `/skill:fact-check-document`|

`overlord.py spawn --mode fast|hotfix --task "<what to build>"` creates the worktree and starts the
worker; without `--task` the script prints the command it would run.

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

## The feat pipeline, in six commands

```bash
"$SKILL_DIR/scripts/overlord.py" plans --inject --approve   # 1. review gate
"$SKILL_DIR/scripts/overlord.py" inventory                  # 2. what every worktree holds
"$SKILL_DIR/scripts/overlord.py" order                      # 3. what merges, in which order
"$SKILL_DIR/scripts/overlord.py" rename --apply             # 4. step labels on every pane
"$SKILL_DIR/scripts/overlord.py" review                     # 5. capture what awaits review
"$SKILL_DIR/scripts/overlord.py" status                     # 6. anything left? 0 = stop
"$SKILL_DIR/scripts/overlord.py" prune --apply              # 7. drop the landed worktrees
```

Each subcommand takes `--repo PATH` (repeatable, default the current directory) and `--base BRANCH`
(default `main`).

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
stacked PR after its base, and the blockers that hold each one back. Merge in that printed order.

Ordering exists only to minimise conflicts: **every open PR ends merged.** A PR that is not `ready`
yet is a job for the next pass, never a candidate to abandon.

```bash
gh pr merge <n> -R <slug> --squash --delete-branch
```

`--merge` only where squash is forbidden. A failed merge is not a merge: read the error, act on it.

## Ask the owning agent

Never edit another agent's branch.

```bash
herdr agent prompt <pane_id> "<instruction>" --wait --until idle --timeout 1800000
```

`needs-check`/`needs-pr`: rebase if stale, run the repo gate, commit its way, push, then `gh pr
create -R <slug> --base <base> --head <branch> --fill`. `conflicting`: rebase, keep both intents,
gate, `git push --force-with-lease`. `agent_blocked` owns a dialog: report it, type nothing.
`no-agent`: do the git work yourself and say so.

## Review by OCR, then chase the fixes

`review` captures the visible screen of every worktree at `REV` or `MRG` — the pane text is the OCR
of the TUI — into `$TMPDIR/overlord-review/`. Read those captures, list what is actually broken, and
message the owning agent one instruction per real defect. Drop the meaningless ones: a clipped help
line or a colour preference is not a defect. Nothing merges until the defects it reported are fixed.

## Labels and status dots

`rename --apply` prefixes every workspace and pane with its step and a short title taken from the PR
title or newest commit, and reports the same step as pane metadata so the status dot matches.

|step|symbol|colour|meaning|
|---|---|---|---|
|`SEE`|👁|`#56b6c2`|looking around, nothing started|
|`PLAN`|🗺|`#61afef`|plan mode, no plan proposed yet|
|`HRD`|🛡|`#c678dd`|plan proposed, waiting for hardening|
|`WORK`|⚒|`#e5c07b`|implementing|
|`REV`|🔍|`#d19a66`|reviewing what was built|
|`REB`|⟳|`#c678dd`|rebasing a conflicting PR|
|`MRG`|⤵|`#98c379`|PR open, waiting to merge|
|`DONE`|✔|`#7f8c8d`|merged, ready to prune|

The overlord's own dot is an eye: it watches, it does not build. The overlord is the session that
runs this skill, never a spawned agent or an extra pane: its pane is named `👁 OVERLORD`, no step
and no title (`rename --apply` labels it from `HERDR_PANE_ID`), and a second pane must never be
created to hold it.

## Mail instead of polling

One Agent Mail project per repository, keyed by the **primary checkout** path — worktree paths would
scatter into separate projects.

```text
ensure_project   human_key: /path/to/primary/checkout
register_agent   project_key: <same path>, program: omp, name: omitted
send_message     project_key: <same path>, sender_name: <your name>, to: [...]
```

Per pass: ensure the project, register, message each live agent the project key and the four moments
worth a message (PR open, needs rebase, blocked, merged), then drain your own inbox with
`fetch_inbox` at the start and the end. A report beats pane text when they disagree; one message per
decision.

## Prune, then stop

`prune --apply` removes worktrees whose PR merged and whose tree is clean, deletes their local branch
(`-D`: a squash merge puts the commits outside the base) and closes the herdr workspace. Agents still
`working` or `blocked` are never pruned.

`status --stop` ends a loop. A run with nothing landable exits 0 only after 20 minutes with no active
worktree (`--idle-minutes N` changes it): with work in flight it exits 1, so a loop keeps going
until either everything landed or the worktrees went quiet.

## Report

One table: path, branch, PR, step, action this pass, next step. Name every blocker exactly.
