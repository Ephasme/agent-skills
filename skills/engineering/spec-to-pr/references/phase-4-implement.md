# Phase 4 — IMPLEMENT  *(the code freeze lifts here — and only here)*

Hand the hardened, reviewed plan to a **per-task build loop that this skill owns outright**: a
fresh implementer subagent per task, **one independent reviewer** after each — judging both spec
compliance and code quality — a fix loop until that task's review is clean, then the next task. One
task in flight at a time — no worktree-per-task swarm, no wave gates, no task graph. Every task is
built by one agent and checked by another before the next one starts.

**Why subagents:** each task goes to an agent with isolated context that you construct exactly —
the task brief, the interfaces it touches, the global constraints, nothing else. It never inherits
your session history, which keeps it focused and preserves your context for coordination.

**Stop after the last task's review comes back clean.** This phase covers task-by-task
implementation only. Do **not** run a broad whole-branch review here, and do **not** offer a
merge/PR/discard menu — Phases 5–9 of *this* skill own verification, the PR, the whole-branch
review, and the handoff. Adding those here duplicates them and hands the integration decision to
the wrong place.

**This is where the Rule Zero code freeze lifts** — and the only place it does. Every line of
product code in this run is written here, by an implementer working one plan task at a time,
reviewed by an independent reviewer. That is the whole point of the phases of restraint that
precede it: nothing reaches the PR that didn't come through this door. (Phases 5–8 stay unfrozen
too — verification fixes and review fixes are code — but they amend what this phase built; they
don't smuggle in what it never saw.)

## Contents

- [The procedure (owned — every step dispatched to a sub-agent)](#the-procedure-owned-every-step-dispatched-to-a-sub-agent)
- [Freeze check, first](#freeze-check-first)
- [Create the feature branch](#create-the-feature-branch)
- [Pre-flight gate — say the cost before you spend it](#pre-flight-gate-say-the-cost-before-you-spend-it)
- [The per-task loop](#the-per-task-loop)
- [Handling implementer status](#handling-implementer-status)
- [Model selection](#model-selection)
- [Constructing the reviewer prompt — the discipline](#constructing-the-reviewer-prompt-the-discipline)
- [File handoffs](#file-handoffs)
- [Durable progress](#durable-progress)
- [Handling a stuck task](#handling-a-stuck-task)

---

## The procedure (owned — every step dispatched to a sub-agent)

1. **Read the plan once.** Note the scene-setting context and the **Global Constraints** section
   (you'll hand those to every reviewer). Create a todo per task.
2. **Pre-flight plan scan.** Before dispatching Task 1, scan the plan once for conflicts: tasks that
   contradict each other or the Global Constraints, or anything the plan mandates that the review
   rubric treats as a defect (a test that asserts nothing, verbatim duplication of a logic block).
   Present everything you find as **one batched question** — each finding beside the plan text that
   mandates it, asking which governs — before execution begins, not one interrupt per discovery
   mid-plan. If the scan is clean, proceed without comment.
3. **Per task, in plan order,** run the loop below. One task in flight; never dispatch two
   implementers in parallel (they conflict).
4. **Last-resort fallback (no subagent dispatch available at all):** implement the plan yourself,
   task by task, running each task's verification as you finish it — and **say so**. You are then
   your own implementer and reviewer, which is materially weaker evidence, and the handoff should
   admit it.

## Freeze check, first

Before dispatching anything, verify Rule Zero held through Phases 0–3:

```
git status --porcelain
```

The working tree must show **nothing but the plan file**. Anything else means an agent broke the
freeze upstream ([`rule-zero-no-code.md`](rule-zero-no-code.md)) — revert it, say what was reverted
and which phase produced it, fold it back in as a plan amendment, and only then proceed.

## Create the feature branch

Implementers commit — so create the feature branch now, before dispatching Task 1. Never run this
phase on the default branch. Name it `<ticket-key>-<slug>` so the Linear/GitHub integrations can
associate the branch with the issue later (Phase 6). Creating a branch is content-free, so it's
fine this early (Rule Zero).

## Pre-flight gate — say the cost before you spend it

Count the plan's tasks (its `### Task N` headings). Project the agent count:

- **Floor:** `2T` — one implementer and one reviewer per task.
- **Realistic:** `~3T` once fix rounds are counted in.

This is the **fan-out cost guard** (SKILL Operating rules): above **~20 agents**, say the number and
confirm before launching, regardless of pre-authorization. Below that, still **pause for go-ahead**
on starting Phase 4 at all unless the human pre-authorized hands-off completion — this is the last
cheap checkpoint before an agent starts writing code against the plan.

## The per-task loop

For each task, everything moves as **files**, not pasted text — anything you paste into a dispatch,
or a subagent prints back, stays resident in your context for the rest of the session. The bundled
scripts live at `$SKILL_DIR/scripts/` — where **`$SKILL_DIR` is notation, not a variable that is
already set**: it stands for this skill's own directory, the absolute path printed in the skill
preamble. Export it once (`SKILL_DIR=<that path>`) before running any of them, and hand subagents
the resolved absolute paths rather than the notation.

1. **Record BASE.** `git rev-parse HEAD` — the commit before this task. You need it for the review
   package; never use `HEAD~1`, which silently drops all but the last commit of a multi-commit task.
2. **Extract the brief.** Run `$SKILL_DIR/scripts/task-brief PLAN_FILE N` — it writes the task's full text to a
   file and prints the path. The brief is the single source of requirements; exact values (numbers,
   magic strings, signatures, test cases) live only there.
3. **Dispatch the implementer** using [`prompts/implementer.md`](prompts/implementer.md). Your
   dispatch carries: one line on where this task fits; the brief path ("read this first — it is your
   requirements, with the exact values to use verbatim"); interfaces/decisions from earlier tasks
   the brief can't know; your resolution of any ambiguity you saw in the brief; and the report-file
   path. Name the report file after the brief (`…/task-N-brief.md` → `…/task-N-report.md`). Do **not**
   paste prior-task summaries — a fresh subagent needs its task, its interfaces, and the constraints,
   nothing else.
4. **Handle the implementer's status** (see below) until it reports DONE.
5. **Build the review package.** `$SKILL_DIR/scripts/review-package BASE HEAD` — writes the commit list, stat
   summary, and full diff to one file and prints the path. It never enters your context.
6. **Dispatch the task reviewer** using [`prompts/task-reviewer.md`](prompts/task-reviewer.md). Hand
   it three paths — the brief, the implementer's report, and the review package — plus the Global
   Constraints that bind this task, copied verbatim. It judges both questions on this diff: does the
   change match what was asked, and is it well-built. Set `model` and `effort` explicitly.

   **It must be a fresh context.** The reviewer's whole value is that it never watched the code
   being written, so it reads what is there rather than what was intended. Never review a task in
   the implementer's context, and never review it in your own — a controller that reviews the work
   it just dispatched is the self-review this loop exists to replace.
7. **Fix loop.** Dispatch a fix subagent for the reviewer's **Critical and Major** findings — one
   fixer with the complete list, not one per finding: parallel fixers on one tree produce
   conflicting edits. The fix subagent carries the implementer contract: re-run the tests covering
   its change and append results to the report file. Then re-review (a fresh `review-package` for
   the new range). Repeat until the reviewer returns clean — spec ✅ and quality Approved. Record
   Minor findings in the ledger for the Phase 7 whole-branch review to triage.

   **Don't let one verdict suppress the other.** The reviewer returns a spec verdict and a quality
   verdict, and a task is clean only when both are. A ✅ on spec compliance never downgrades a Major
   quality finding, and Approved quality never excuses a missed requirement — they are two gates
   that happen to be judged by one agent, not one gate with two labels.
8. **Mark the task complete** in the todo list and append one line to the ledger (see Durable
   progress). Then move to the next task.

## Handling implementer status

Implementers report one of four statuses:

- **DONE:** proceed to the review package and task reviewer.
- **DONE_WITH_CONCERNS:** read the concerns first. If they're about correctness or scope, address
  them before review; if they're observations ("this file is getting large"), note them and proceed.
- **NEEDS_CONTEXT:** provide the missing information and re-dispatch.
- **BLOCKED:** assess the blocker — context problem → provide more and re-dispatch same model;
  needs more reasoning → re-dispatch a more capable model; task too large → split it; **the plan
  itself is wrong** → escalate (see Handling a stuck task). Never force the same model to retry
  unchanged, and never ignore an escalation.

**Reviewer ⚠️ items.** The reviewer may report "⚠️ Cannot verify from diff" — requirements
that live in unchanged code or span tasks. These don't block, but resolve each yourself before marking
the task complete (you hold the cross-task context the reviewer lacks). A confirmed gap is a failed
spec review — send it back to the implementer and re-review.

## Model selection

Use the least powerful model that can handle each role — **always set it explicitly** (an omitted
model inherits the session's, usually the most expensive). Turn count beats token price: the
cheapest models often take 2–3× the turns on multi-step work.

- **Transcription implementer** (the plan text contains the complete code to write; single-file
  mechanical fix): cheapest tier.
- **Prose-description implementer / reviewer:** mid-tier as the floor.
- **Integration/judgment implementer** (multi-file coordination, debugging): standard model.
- **Reviewer:** scale to the diff — a small mechanical diff doesn't need the top model; a subtle
  concurrency change does. It is the only check on the task, so don't cut below the mid tier to
  save a few tokens.

The model/effort operating rule binds every dispatch here — this loop is the one you dispatch.

## Constructing the reviewer prompt — the discipline

Per-task reviews are task-scoped gates; the broad review happens once, at Phase 7. When you fill
the reviewer template:

- **Copy the Global Constraints verbatim** from the plan into the reviewer's constraints block —
  exact values, formats, and stated relationships between components ("same layout as X"). That
  block is the reviewer's attention lens; the template already carries the process rules.
- **Never pre-judge.** Don't tell a reviewer what not to flag, don't pre-rate a finding's severity
  ("at most Minor"), don't ask it to skip an issue. If a prompt you're writing contains "do not
  flag," "the plan chose," or "treat as Minor" — stop; you're sparing yourself a review loop. Let
  the reviewer raise it and adjudicate in the loop.
- **Don't ask it to re-run tests** the implementer already ran on the same code — the report carries
  that evidence. Don't add open-ended directives ("check all uses") without a concrete reason.
- **A plan-mandated finding is the human's call.** If a finding conflicts with what the plan's text
  requires, present both and ask which governs — don't dismiss it, and don't dispatch a fix that
  contradicts the plan without asking.

## File handoffs

- **Task brief** (`$SKILL_DIR/scripts/task-brief`) — the implementer's and reviewer's
  single source of requirements.
- **Report file** — the implementer writes its full report there and returns only status, commits, a
  one-line test summary, and concerns. Fix dispatches append their fix report (with test results) to
  the same file.
- **Review package** (`$SKILL_DIR/scripts/review-package`) — the reviewer's view of the
  diff, in one Read.

## Durable progress

Conversation memory does not survive compaction; controllers that lost their place have
re-dispatched entire completed task sequences — the single most expensive failure. Keep a ledger
file, not only todos.

- At phase start, check for one: `cat "$(git rev-parse --show-toplevel)/.stpr/build/progress.md"`.
  Tasks marked complete there are DONE — don't re-dispatch; resume at the first not marked complete.
  (`$SKILL_DIR/scripts/build-workspace` creates `.stpr/build/` as git-ignored scratch.)
- When a task's review comes back clean, append one line:
  `Task N: complete (commits <base7>..<head7>, review clean)`.
- The ledger is your recovery map: the commits it names exist in git even when your context no
  longer remembers creating them. After compaction, trust the ledger and `git log` over recollection.

## Handling a stuck task

Most stuck states resolve via the status handling above (more context, a stronger model, a smaller
split). The one thing that escalates past this loop: a task blocked because **the plan itself is
wrong** — not a context gap, not a sizing problem. That's a finding for the orchestrator — stop, go
back to **Phase 2**, run the change through hardening, and re-open the todos you went back to.

**Exit:** every task in the plan implemented and reviewed clean (spec + quality), committed, on the
feature branch — nothing merged, pushed, or opened yet; that's Phase 6.

**Exit receipt example:**
`✅ Phase 4 (IMPLEMENT) — owned per-task loop, 7 tasks, reviewer clean on each — 7 commits on abc-123-rate-limiting`
