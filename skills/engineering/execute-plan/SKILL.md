---
name: execute-plan
description: >-
  Executes a written implementation plan to completion in a focused session —
  loading the plan and reviewing it critically first, working each task in order with
  the verifications it specifies, and closing out the branch. Isolated execution is
  the default: one fresh sub-agent per task with a review between tasks where the
  agent can dispatch sub-agents, otherwise an inline pass in the current session with
  review checkpoints. Finishes by confirming the full suite passes on the branch,
  then presenting merge, pull request, keep-as-is, or delete to the user. Use when
  the user says "execute the plan", "implement this plan", "work through the plan",
  or hands over a plan file — conventionally a dated file under `docs/plans/` —
  written by a prior planning session. Stops and asks on blockers rather than
  guessing.
---

# Execute plan

Take a written implementation plan and drive it to a finished, verified branch. Load the plan,
review it critically before executing anything, work each task in order with its verifications, then
close out the branch. Stop and ask whenever reality contradicts the plan.

## Choose the execution mode

Two ways to work the plan. When both are available, say which you recommend and let the user choose
before starting:

- **One fresh sub-agent per task, with a review between tasks** — where the agent can dispatch
  sub-agents, this is the recommended default. Each task runs in a clean context, the review catches
  drift before it compounds, and independent tasks can run in parallel.
- **Inline, in the current session, with review checkpoints** — where it cannot dispatch sub-agents,
  work the tasks in order here, pausing at the same checkpoints to review before moving on.

## Step 1 — Load and review the plan

1. Ensure an isolated workspace before touching code: a dedicated git worktree or branch. Verify the
   existing one if the project already created it. Never implement on the default branch
   (`main`/`master`) without the user's explicit consent.
2. Read the plan file in full — conventionally `docs/plans/YYYY-MM-DD-<topic>.md`, unless this
   project states its own location.
3. Review it critically: open questions, gaps, wrong assumptions, tasks that cannot be verified.
4. If anything concerns you, raise it with the user before starting. Do not begin on a plan you
   doubt.
5. If nothing does, create a task per plan item and proceed.

## Step 2 — Execute the tasks

For each task, in order:

1. Mark it in progress.
2. Follow its steps exactly — plans are written in bite-sized steps for a reason.
3. Run the verification the task specifies. Do not skip it, and do not substitute a weaker one.
4. Mark it completed.
5. In sub-agent mode, review the task's output against the plan before dispatching the next one.

## Step 3 — Finish the branch

Once every task is complete and verified:

1. Confirm the full test suite passes on the finished branch. If it fails, fix it — a branch that
   does not pass is not finished, and finishing is not a step to skip.
2. Present the options to the user: merge, open a pull request, keep the branch as-is, or delete it.
3. Execute the choice.

## When to stop and ask

**Stop executing immediately when:**

- You hit a blocker — a missing dependency, a failing test, an instruction you cannot follow.
- The plan has critical gaps that prevent starting.
- You do not understand an instruction.
- Verification fails repeatedly.

Ask for clarification rather than guessing. A wrong guess costs more than the question.

## When to revisit an earlier step

**Return to Step 1 when:**

- The user updates the plan based on your feedback.
- The fundamental approach needs rethinking.

Do not force through a blocker — stop and ask.

## Remember

- Review the plan critically before executing a single step.
- Follow the plan's steps exactly; do not improvise around them.
- Never skip a verification.
- Stop when blocked, do not guess.
- Never start implementation on the default branch without explicit consent.
