---
name: debug-systematically
description: >-
  Finds the root cause of a bug, test failure, build break, or unexpected behaviour
  before attempting any fix — reading the error, reproducing it, checking recent
  changes, gathering evidence at component boundaries, forming one hypothesis,
  testing it minimally, and fixing at the source with a failing test in place. It
  carries the Iron Law (no fixes without root-cause investigation first), the four
  phases, and the red-flag and rationalization tables that hold the line under time
  pressure. Use for any technical problem — test failure, production bug,
  performance regression, integration issue — and especially when the cause is
  unclear, a quick fix looks obvious, earlier fixes have not worked, or a fix must
  land under deadline. Supporting techniques for backward tracing, layered
  validation, condition-based waiting, and polling in references/.
---

# Debug systematically

**Core principle:** ALWAYS find root cause before attempting fixes. Symptom fixes are failure.

**Violating the letter of this process is violating the spirit of debugging.**

`$SKILL_DIR` in the paths below is **notation, not a variable that is already set** — it stands for
this skill's own directory, the one holding this `SKILL.md`. Export it once (`SKILL_DIR=<that path>`)
before running any command here.

## The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you have not completed Phase 1, you cannot propose fixes.

## When to use

Any technical issue: test failures, bugs in production, unexpected behaviour, performance problems,
build failures, integration issues.

**Use this ESPECIALLY when:**
- Under time pressure — emergencies make guessing tempting
- "Just one quick fix" seems obvious
- You have already tried multiple fixes
- A previous fix didn't work
- You don't fully understand the issue

**Don't skip when:**
- The issue seems simple — simple bugs have root causes too
- You are in a hurry — rushing guarantees rework
- Someone wants it fixed NOW — systematic is faster than thrashing

## The four phases

You MUST complete each phase before proceeding to the next.

### Phase 1: Root cause investigation

**BEFORE attempting ANY fix:**

1. **Read error messages carefully** — don't skip past errors or warnings; they often contain the
   exact solution. Read stack traces completely; note line numbers, file paths, error codes.
2. **Reproduce consistently** — can you trigger it reliably? What are the exact steps? Does it
   happen every time? If not reproducible, gather more data, don't guess.
3. **Check recent changes** — what changed that could cause this? Diffs, recent commits, new
   dependencies, config changes, environmental differences.
4. **Gather evidence in multi-component systems.** When several components are in play
   (CI → build → signing, API → service → database), add diagnostic instrumentation BEFORE
   proposing fixes. For EACH component boundary: log what data enters, log what data exits, verify
   environment/config propagation, check state at each layer. Run once to show WHERE it breaks,
   then analyze the evidence to identify the failing component, then investigate that component.

   ```
   # Layer 1: workflow — is the secret present?
   echo "IDENTITY: ${IDENTITY:+SET}${IDENTITY:-UNSET}"
   # Layer 2: build script
   env | grep IDENTITY || echo "IDENTITY not in environment"
   # Layer 3: signing script — keychain state
   security find-identity -v
   ```

   This reveals which layer fails (secrets → workflow ✓, workflow → build ✗).

5. **Trace data flow.** When the error is deep in the call stack, trace backward to the original
   trigger and fix at the source, not at the symptom. Full technique:
   [references/root-cause-tracing.md](references/root-cause-tracing.md).

   Quick version: where does the bad value originate? What called this with the bad value? Keep
   tracing up until you reach the source.

### Phase 2: Pattern analysis

**Find the pattern before fixing:**

1. **Find working examples** — locate similar working code in the same codebase. What works that is
   similar to what is broken?
2. **Compare against references** — if implementing a pattern, read the reference implementation
   COMPLETELY. Don't skim; read every line. Understand it fully before applying it.
3. **Identify differences** — what differs between working and broken? List every difference,
   however small. Don't assume "that can't matter".
4. **Understand dependencies** — what other components, settings, config, environment does this
   need? What assumptions does it make?

### Phase 3: Hypothesis and testing

**Scientific method:**

1. **Form a single hypothesis** — state clearly "I think X is the root cause because Y". Write it
   down. Be specific, not vague.
2. **Test minimally** — the SMALLEST possible change that tests the hypothesis. One variable at a
   time. Don't fix multiple things at once.
3. **Verify before continuing** — did it work? Yes → Phase 4. No → form a NEW hypothesis. Don't
   stack more fixes on top.
4. **When you don't know** — say "I don't understand X". Don't pretend. Ask for help. Research
   more.

### Phase 4: Implementation

**Fix the root cause, not the symptom:**

1. **Create a failing test case** — the simplest possible reproduction; an automated test, or a
   one-off script if there is no framework. It MUST exist before the fix. Write the failing test
   first, watch it fail, then fix — a test written after the fix proves nothing.
2. **Implement a single fix** — address the root cause identified. ONE change at a time. No
   "while I'm here" improvements, no bundled refactoring.
3. **Verify the fix** — test passes now? No other tests broken? Is the issue actually resolved?
   Verify against the original reproduction before claiming success.
4. **If the fix doesn't work** — STOP. Count the fixes tried. Fewer than 3 → return to Phase 1 and
   re-analyze with the new information. **3 or more → STOP and question the architecture (step 5).**
   Don't attempt fix #4 without an architectural discussion.

5. **If 3+ fixes failed, question the architecture.**

   The pattern: each fix reveals new shared state, coupling, or a problem in a different place;
   fixes need "massive refactoring"; each fix creates new symptoms elsewhere.

   STOP and question fundamentals: is this pattern sound, or is it being kept through inertia?
   Should the architecture be refactored rather than more symptoms fixed?

   Discuss with the user before attempting more fixes. This is not a failed hypothesis — it is a
   wrong architecture.

## Red flags — STOP and follow the process

If you catch yourself thinking:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run tests"
- "Skip the test, I'll verify manually"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "The pattern says X but I'll adapt it differently"
- Listing fixes without investigation
- Proposing solutions before tracing data flow
- **"One more fix attempt" (when 2+ have already failed)**
- **Each fix reveals a new problem in a different place**

**All of these mean: STOP. Return to Phase 1.** If 3+ fixes have failed, question the architecture.

## Signals you're doing it wrong

Watch for these from the user:

- "Is that not happening?" — you assumed without verifying
- "Will it show us…?" — you should have added evidence gathering
- "Stop guessing" — you're proposing fixes without understanding
- "Ultra-think this" — question fundamentals, not just symptoms
- "We're stuck?" (frustrated) — the approach isn't working

**When you see these:** STOP. Return to Phase 1.

## Common rationalizations

| Excuse | Reality |
|--------|---------|
| "Issue is simple, don't need process" | Simple issues have root causes too. Process is fast for simple bugs. |
| "Emergency, no time for process" | Systematic debugging is FASTER than guess-and-check thrashing. |
| "Just try this first, then investigate" | The first fix sets the pattern. Do it right from the start. |
| "I'll write the test after confirming the fix works" | Untested fixes don't stick. A test first proves it. |
| "Multiple fixes at once saves time" | Can't isolate what worked. Causes new bugs. |
| "Reference too long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding root cause. |
| "One more fix attempt" (after 2+ failures) | 3+ failures = architectural problem. Question the pattern, don't fix again. |

## Quick reference

| Phase | Key activities | Success criteria |
|-------|---------------|------------------|
| **1. Root cause** | Read errors, reproduce, check changes, gather evidence | Understand WHAT and WHY |
| **2. Pattern** | Find working examples, compare | Identify differences |
| **3. Hypothesis** | Form theory, test minimally | Confirmed, or a new hypothesis |
| **4. Implementation** | Create test, fix, verify | Bug resolved, tests pass |

## When the process reveals "no root cause"

If systematic investigation shows the issue is truly environmental, timing-dependent, or external:

1. You have completed the process
2. Document what you investigated
3. Implement appropriate handling — retry, timeout, error message
4. Add monitoring/logging for future investigation

**But:** 95% of "no root cause" cases are incomplete investigation.

## Supporting techniques

- [references/root-cause-tracing.md](references/root-cause-tracing.md) — trace a bug backward
  through the call stack to its original trigger, and instrument when the trace cannot be done by
  hand.
- [references/defense-in-depth.md](references/defense-in-depth.md) — once the root cause is known,
  add validation at every layer the bad data passes through, so the bug becomes structurally
  impossible.
- [references/condition-based-waiting.md](references/condition-based-waiting.md) — replace arbitrary
  delays and timeouts with polling for the actual condition. Complete helper implementation:
  [references/condition-based-waiting-example.ts](references/condition-based-waiting-example.ts).
- `$SKILL_DIR/scripts/find-polluter.sh <file_or_dir_to_check> <test_pattern>` — bisect a test suite
  to find which test creates unwanted state. Needs a test runner and a shell; there is no fallback.

## Validating this skill

Three scenario files hold the pressure situations this process was verified against. Rerun them
after editing this skill, and check the rails still hold:

- [references/pressure-test-1.md](references/pressure-test-1.md) — an emergency production fix,
  where a two-minute retry patch competes with a half-hour investigation.
- [references/pressure-test-2.md](references/pressure-test-2.md) — sunk cost and exhaustion after
  four hours of failed timeout tweaks.
- [references/pressure-test-3.md](references/pressure-test-3.md) — authority and social pressure,
  where a senior engineer and a tech lead push a symptom fix.
