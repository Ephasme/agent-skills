# Worktree steps

A left-panel label is `<symbol> <STEP> <name> <title>` and may end with one parenthesised fact:
`🔍 REV m8 ocr-review-pr13 (PR #13 - m2)` while m8 reviews the PR m2 opened, `⚒ WORK m1
overlord-rust-port (PR #1)` in any other step, `⤵ MRG m7 overlord-panel-rows (PR #2 · merged)` once
merged, and no parentheses at all without a PR.

The owner appears in REV only, because a reviewer is the one who needs to know whose work it
reviews, and it is never read off the current worktree. It comes from the registry field
`pr_owner`, written by whichever minion opened the PR: every PR carries the human account, so `gh`
cannot say it. Unknown prints `(PR #13 - ?)`.

The agent panel reads the `step`, `name` and `title` tokens, published bare, so it shows
`REV · m8 · ocr-review-pr13`. herdr's agent state stays in herdr: it is never copied into a label or
a registry field.

The minion id in parentheses belongs to one other place, the pull request title, appended by the
minion that owns that PR: `summon-the-overlord: enforced plan mode (m2)`.

Slugs are tool-first, target second: `ocr-review-pr13`. Spawn derives the title from the task's first
words; pass `--title` when the job is better named than its brief.

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

`rename --apply` is the only thing that restores a label: a worktree whose herdr workspace was closed
and reopened comes back labelled with its directory name, and `rename` reads the registry identity
through the live pane's directory, so the label returns without re-registering anything.

## Review, and the merge gate

A review is `ocr review --audience agent --background "<per-PR context>" --from <base> --to <head>
--repo <checkout> --output <artifact>` over the diff, never a screenshot. The artifact path is
`$XDG_STATE_HOME/summon-the-overlord/review/<owner>-<repo>-<pr>.txt`, and its first line is
`<!-- reviewed: <head sha> -->`. That header is the whole cross-implementation contract: the tool
that writes the artifact and the tool that gates the merge agree even when they are the Python
toolbelt and the Rust port.

A PR is landable only when an artifact exists and its header names the current head sha. An artifact
for an older sha is stale, so the PR reads `unreviewed: stale` in `status` and `order`; a missing
artifact reads `unreviewed: missing`. Without `ocr` on the machine, `preflight` reports the row as
missing and every open PR stays unlandable rather than merging unreviewed.

Findings above low go to the owning minion one instruction per defect, then the PR is re-reviewed at
the new head sha and the new artifact replaces the old one. A screen capture survives only for a
target that cannot produce a diff and is labelled `screen`, never `review`.

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

## Stale-label classifier

Primary `deepseek/deepseek-v4.1-flash-1017`, fallback `openai/gpt-5-mini`, both in `models.allowed`
and both printed by `models`. The pick rests on error direction and cost, not on an accuracy win:
batch 0.960 [0.902-0.984] against Mini's 0.890 [0.814-0.937], false-updated 11 against 22 per 1000
(the silent error, at half the rate), 11.6 against 95.6 micro-USD per 1000 bare-API calls. Those
intervals overlap; do not claim an accuracy win.

The step glossary ships inside the prompt. It fixed MRG-with-merged-PR for both finalists and broke
the completed-rebase case: on the 40-case fixture DeepSeek went 0.900 to 0.970 and Mini stayed
neutral, so the glossary is a requirement with a known cost.

The guard is code, before any call: no pane, an empty pane or an unreadable one returns `not_sure`
with its reason and never reaches a model, because both finalists answer `updated` on empty
evidence — the one failure that leaves a stale label lying. A sweep with nothing stale spends
nothing; cost per sweep is `stale minions × 11.6 micro-USD`. The call has its own timeout (median
7.3 s, tail past 100 s) and never blocks the sweep from finishing.

## Test cases

Every decision-table row; label bytes stable across two renders of identical facts; marker absent,
current and stale selecting `HRD`, `BUILD`, `HRD`; `plans --approve` refusing an unhardened plan;
spawn argv order start -> `Alt+Shift+P` -> prompt for feat, start -> prompt for fast.
