---
name: two-axis-review
description: >-
  Review the changes since a fixed point (commit, branch, tag, or merge-base) along two
  independent axes — Standards (does the code follow this repo's documented standards, plus
  a code-smell baseline?) and Spec (does it match what the originating spec, issue, or PRD
  asked for?). The two axes run as parallel subagents so neither pollutes the other's
  context, and the reports are presented side by side without cross-axis reranking. Use
  when the user wants to review a branch, a PR, work-in-progress changes, or says "review
  since main", "review this branch", or "check this against the spec". Read-only — it
  reports findings and changes nothing.
---

# two-axis-review — Standards ‖ Spec

Review the diff between `HEAD` and a fixed point along two axes that run **in parallel** and are
reported **separately**:

- **Standards** — does the diff follow this repo's documented standards, plus a fixed code-smell
  baseline?
- **Spec** — does the diff faithfully implement the originating spec: nothing missing, nothing
  extra, nothing implemented wrongly?

**The separation is the point.** A change can pass one axis and fail the other:

- Code that follows every convention but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what was asked in a style the repo forbids → **Spec pass, Standards fail.**

Merging the reports lets one axis mask the other, and reranking across them buries a real Spec
failure under a pile of style notes. So this skill never merges and never re-ranks across axes.

Running them as separate subagents matters for the same reason: one agent holding both jobs in one
context will let a clean verdict on one axis soften a finding on the other.

## Inputs

```
/engineering-perso:two-axis-review --since <ref> [--spec <path>] [--model <model>]
```

`--since` is the fixed point. A bare positional argument is accepted as `--since` (so
`/two-axis-review main` works). Everything else is discovered per the table below. Anything the
caller can't express as a flag — a roll-up of previously deferred findings, for instance — is
passed as prose alongside the invocation, and read as additional context.

| Input | Resolution |
|---|---|
| **Fixed point** | The argument, if given (SHA / branch / tag / `HEAD~5`). Otherwise the merge-base with the repo's default branch — **derive it and say so**, don't ask for what you can compute. |
| **Spec** | An explicit `--spec` path → else a `spec-to-pr` plan file → else issue references parsed from `git log` (`#123`, `Closes #45`) fetched with `gh` → else ask. If there is genuinely no spec, **skip the Spec axis** and say so in the report. |
| **Standards** | The repo's `CLAUDE.md` / `AGENTS.md`, `CONTRIBUTING.md`, `CODING_STANDARDS.md`, plus lint/format configs — the configs read to learn **what tooling already enforces, so the axis can skip it**. Always plus the smell baseline. |
| **`--model`** | Model for both axis agents. Default: the most capable available — only two agents run, and this is the last gate before a human's time is spent. |

## Step 1 — Pin the fixed point

Resolve the base ref, keeping the **remote-tracking form** (`origin/main`) rather than stripping
the prefix — the local branch of that name may not exist in this checkout:

```bash
base_ref=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD) \
  || base_ref=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null) \
  || base_ref=""
```

`refs/remotes/origin/HEAD` is **not always set** — a `--single-branch` clone or a manually added
remote leaves it absent. If neither resolves, **ask** which branch the work forked from; don't
guess `main`.

Then confirm the fixed point resolves and the diff is non-empty:

```bash
git rev-parse --verify "$fixed_point"
git diff --stat "$fixed_point"...HEAD
```

Three dots, so the comparison is against the merge-base. **Fail here, loudly.** A bad ref or an
empty diff must not be discovered inside two subagents that have already been paid for.

## Step 2 — Package the diff as a file

> **`$SKILL_DIR` is notation, not a variable that is already set.** It stands for this skill's own
> directory — the absolute path printed in the skill preamble. Export it once
> (`SKILL_DIR=<that path>`) before running the command.

```bash
$SKILL_DIR/scripts/review-package <fixed-point> HEAD
```

It writes the commit list, stat summary, and full diff to one file and prints the path. Hand
**both** agents that path. The diff never enters your context, and both axes read the same
artifact — so their findings are about the same bytes.

## Step 3 — Resolve spec and standards sources

Per the Inputs table. **List what you found** before dispatching, so the reader knows what the
change was judged against. "No standards file found, baseline only" is a useful thing to say out
loud; silently reviewing against nothing is not.

## Step 4 — Dispatch both axes in parallel

**One message, two `Agent` calls**, using
[`references/prompts/standards-axis.md`](references/prompts/standards-axis.md) and
[`references/prompts/spec-axis.md`](references/prompts/spec-axis.md).

Set **`model` and `effort` explicitly on both** — an omitted model silently inherits the session's,
usually the most expensive.

Paste [`references/smell-baseline.md`](references/smell-baseline.md) into the Standards prompt
**in full**: the subagent has no other access to it.

If there is no spec, dispatch only the Standards axis and say the Spec axis was skipped.

## Step 5 — Aggregate

Present the two reports under `## Standards` and `## Spec`, verbatim or lightly cleaned.

**Do not merge them. Do not re-rank across them.** Close with one line per axis: the finding count,
and the worst issue *within that axis*. Don't pick a single winner across axes — that is precisely
the reranking the separation exists to prevent.

## Severity

`critical` / `major` / `minor`, blocking down to non-blocking:

- **critical** — the change is wrong: it breaks behaviour, loses data, or fails a requirement the
  spec states outright.
- **major** — it works but leaves significant risk, or breaches a documented standard.
- **minor** — polish, naming, nice-to-haves.

Orthogonal to severity, mark each finding **hard violation** (a documented standard, or a spec
requirement, is breached) or **judgement call**. Two rules bind the Standards axis:

- **The repo overrides the baseline.** Where a documented standard endorses something the baseline
  would flag, suppress the smell.
- **Baseline findings are always judgement calls**, never hard violations.

## Guardrails

- **Read-only.** No edits, no commits, no working-tree, index, HEAD or branch mutation — by this
  skill or by either subagent. The deliverable is findings.
- **Skip what tooling enforces.** Formatting, import order, anything the linter or formatter
  already catches. A review that repeats the linter spends the reader's attention on nothing.
- **Evidence per finding.** `file:line` for Standards, a quoted spec line for Spec. A finding
  without evidence is a preference.
