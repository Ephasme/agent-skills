---
name: write-plan
description: >-
  Turns an approved spec or set of requirements into an ordered, bite-sized
  implementation plan a fresh implementer can execute without prior context to the
  codebase — file-by-file task decomposition, exact code and test steps, interfaces
  each task consumes and produces, no placeholders, plus a self-review and an
  optional independent second-reader review before handoff. Use once the design is
  settled and before touching code — when the user asks for an implementation plan,
  when a spec needs breaking into independently testable tasks, when work must be
  handed to another agent or developer to build, or when the user says "write the
  plan", "break this into tasks", or "how would we build this". Produces a plan
  document, not code.
---

# Write plan

Turn a settled design into a plan another person or agent can execute end to end, with no access to
the conversation that produced it and no need to guess. Assume the implementer is a skilled
developer who knows almost nothing about this codebase, its toolset, or its domain — and is not a
strong test designer. Every task carries the files it touches, the code to write, how to test it,
and when to commit. DRY. YAGNI. Test-first. Frequent commits.

**Save plans to** `docs/plans/YYYY-MM-DD-<topic>.md` — unless this project states its own location
for plans, in which case use that.

## Scope check

If the spec covers multiple independent subsystems, it should already have been broken into
sub-project specs during design. If it was not, stop and suggest splitting this into separate plans —
one per subsystem. Each plan must produce working, testable software on its own.

## File structure

Before defining tasks, map which files will be created or modified and what each is responsible for.
This is where decomposition is locked in.

- Design units with clear boundaries and well-defined interfaces; each file has one responsibility.
- You reason best about code you can hold in context at once, and edits are more reliable when files
  are focused. Prefer smaller, focused files over large ones that do too much.
- Files that change together live together. Split by responsibility, not by technical layer.
- In existing codebases, follow established patterns. If the codebase uses large files, do not
  unilaterally restructure — but if a file you are modifying has grown unwieldy, including a split
  in the plan is reasonable.

This structure drives task decomposition: each task produces a self-contained change that makes
sense independently.

## Task right-sizing

A task is the smallest unit that carries its own test cycle and is worth a fresh reviewer's gate.
When drawing boundaries: fold setup, configuration, scaffolding, and documentation into the task
whose deliverable needs them; split only where a reviewer could meaningfully reject one task while
approving its neighbour. Each task ends with an independently testable deliverable.

## Bite-sized steps

**Each step is one action (2-5 minutes):**

- "Write the failing test" — step
- "Run it to make sure it fails" — step
- "Implement the minimal code to make the test pass" — step
- "Run the tests and make sure they pass" — step
- "Commit" — step

## Plan document header

**Every plan starts with this header:**

```markdown
# [Feature Name] Implementation Plan

> **For the implementing agent:** Execute one task at a time. Tick each checkbox
> (`- [ ]` → `- [x]`) as you finish a step, and stop to ask if any step is unclear —
> never guess.

**Goal:** [One sentence describing what this builds]

**Architecture:** [2-3 sentences about the approach]

**Tech Stack:** [Key technologies/libraries]

**Spec:** [path to the spec/design doc this plan implements — the plan argues from
the spec, so the spec travels with it; implementers read both]

## Global Constraints

[The spec's project-wide requirements — version floors, dependency limits, naming
and copy rules, platform requirements — one line each, with exact values copied
verbatim from the spec. Every task's requirements implicitly include this section.]

---
```

## Task structure

````markdown
### Task N: [Component Name]

**Files:**
- Create: `exact/path/to/file.py`
- Modify: `exact/path/to/existing.py:123-145`
- Test: `tests/exact/path/to/test.py`

**Interfaces:**
- Consumes: [what this task uses from earlier tasks — exact signatures]
- Produces: [what later tasks rely on — exact function names, parameter and return
  types. An implementer sees only their own task; this block is how they learn the
  names and types neighbouring tasks use.]

- [ ] **Step 1: Write the failing test**

```python
def test_specific_behavior():
    result = function(input)
    assert result == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/path/test.py::test_name -v`
Expected: FAIL with "function not defined"

- [ ] **Step 3: Write minimal implementation**

```python
def function(input):
    return expected
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/path/test.py::test_name -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tests/path/test.py src/path/file.py
git commit -m "feat: add specific feature"
```
````

## No placeholders

Every step carries the actual content an implementer needs. These are **plan failures** — never
write them:

- "TBD", "TODO", "implement later", "fill in details"
- "Add appropriate error handling" / "add validation" / "handle edge cases"
- "Write tests for the above" (without the actual test code)
- "Similar to Task N" (repeat the code — the implementer may read tasks out of order)
- Steps that describe what to do without showing how (code blocks required for code steps)
- References to types, functions, or methods not defined in any task

## Self-review

After writing the complete plan, look at the spec with fresh eyes and check the plan against it.
This is a checklist you run yourself first — it is not a sub-agent dispatch.

1. **Spec coverage:** Skim each section and requirement in the spec. Can you point to a task that
   implements it? List every gap.
2. **Placeholder scan:** Search the plan for the red flags from **No placeholders** above. Fix them.
3. **Type consistency:** Do the types, method signatures, and property names used in later tasks
   match what earlier tasks defined? A function called `clearLayers()` in Task 3 but
   `clearFullLayers()` in Task 7 is a bug.

Fix issues inline as you find them — no need to re-review; fix and move on. A spec requirement with
no task gets a new task.

**Independent review (optional but cheap):** where the agent can dispatch a sub-agent, hand it the
plan and spec with the prompt template in
[references/plan-reviewer-prompt.md](references/plan-reviewer-prompt.md); where it cannot, run that
same checklist yourself as a separate pass, after a pause, without editing. Treat only issues that
would derail implementation as blocking.

## Execution handoff

After saving the plan, offer the execution choice:

> "Plan complete and saved to `docs/plans/<filename>.md`. Two execution options:
>
> 1. **Sub-agent per task (recommended)** — I dispatch a fresh sub-agent for each task and review
>    its work before starting the next. Fast iteration, clean context per task.
> 2. **Inline execution** — I execute the tasks in this session, in batches, pausing at checkpoints
>    for your review.
>
> Which approach?"

**Sub-agent per task:** dispatch one fresh sub-agent per task and review between tasks — each
implementer gets clean context, and the review catches drift before it compounds. This is the
recommended mode wherever the agent can dispatch sub-agents.

**Inline execution:** execute the tasks directly in the current session, in batches, with a review
checkpoint between batches.

**Where the agent cannot dispatch sub-agents,** there is no sub-agent mode: execute inline, and buy
the isolation with ordering and files — finish one task, review it, write down the result, then
start the next, rather than running several at once. Say so when offering the choice, and present
inline execution as the only mode.

**When the work needs an isolated workspace** — a dedicated git worktree or branch so the changes
land without disturbing the current tree — set it up before execution and finish it when the plan
completes: merge it back, or open a pull request for review.
