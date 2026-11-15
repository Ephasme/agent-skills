# Worktree steps

A label is `<symbol> <STEP> <name> <frozen-title>`, built only from step facts and the registry
identity recorded at birth. herdr's agent state stays in herdr: it is never copied into a label or a
registry field.

## Hardening marker

Last line of `PLAN.md`, exact: `<!-- hardened: <sha of the plan commit> -->`. The plan commit is the
commit whose `PLAN.md` equals the current file without that last line, so committing the marker once
more does not invalidate it; any later edit of the plan does. Same line, same bytes, in every
implementation.

A committed plan whose marker is absent or names an older commit is `HRD`. A committed plan whose
marker is present and current is `WORK`/`BUILD`, and only then may `plans --approve` press `1`;
`plans --inject` keeps sending `/skill:harden-plan` while the plan is unhardened.

## Step decision table

|Priority|Step|Observable facts|
|---:|---|---|
|1|`DONE`|PR merged, tree clean, prune pending.|
|2|`REB`|PR open and conflicting with base.|
|3|`REV`|PR open and not green, or exact `REVIEWING` marker present while the minion reviews its own diff. `REVIEW_CLEAR` ends the review exception.|
|4|`MRG`|PR open, non-draft, green, unmerged, and no review in progress.|
|5|`HRD`|`PLAN.md` committed and its marker absent or stale.|
|6|`BUILD`|No open PR, and the marker is present and current.|
|7|`PLAN`|Registered minion started, plan absent or uncommitted.|
|8|`IDLE`|No plan, no commits ahead, clean tree, no PR, no registered minion in flight. `IDLE` is not rendered as a step.|

Evaluate rows top to bottom. An uncommitted plan stays `PLAN`, never `HRD`. Pane prose is never step
evidence.

`rename` and `watch` never fight the birth label: a freshly spawned feat minion is `PLAN` with the
plan-mode prompt pending, and it stays `PLAN` until a plan file exists and is committed. Only then
does the step move, to `HRD` without a current marker or to `BUILD` with one.

## Stalls

|Step|idle|
|---|---|
|`PLAN`|normal: awaiting the plan or its first commit|
|`HRD`|stall: hardening never ran or never converged|
|`BUILD`|serious stall|
|`REV`|stall|
|`REB`|stall|
|`MRG`|stall|
|`DONE`|normal: awaiting prune|

A stall is a decision the overlord is expected to make, usually without asking anyone. `watch` and
`pass` print one `stall` row per stalled minion: name, step, title, seconds idle, last commit subject
and age, dirtiness, PR state and checks, and whether the last non-empty pane line is a question.
`--alert` prompts the overlord pane once per newly detected stall, deduplicated by minion+step in the
state directory and cleared when agent state or step changes. The tool alerts only: it never renames,
respawns or kills on its own. Ask a human only for genuinely irreversible actions or conflicting
evidence: force-push, merge with failing or unknown checks, deleting uncommitted work, an ambiguous
target.

## Test cases

Every decision-table row; label bytes stable across two renders of identical facts; marker absent,
current and stale selecting `HRD`, `BUILD`, `HRD`; `plans --approve` refusing an unhardened plan;
spawn argv order start -> `Alt+Shift+P` -> prompt for feat, start -> prompt for fast.
