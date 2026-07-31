---
name: executing-autonomously
description: Runs a queue of plans or phases to completion without check-ins, re-hardening each plan before executing it and stopping only on a hard physical block. Use when Loup hands off work to finish unattended and tells you to run in complete autonomy — "don't stop", "don't ask", "do it until it's done", "use your judgment", "don't wait for me", "just keep going", "do all of this on your own", to work through the remaining plans/phases yourself, or otherwise signals they won't be available to answer until the work is complete.
---

# Executing autonomously

Loup has handed off a multi-step build — often a queue of plans or phases — to complete on your own. They won't be answering questions; they will follow your recommendations. Run it to completion.

**The letter and the spirit are the same: stopping to ask when you could have decided is a failure, not caution.**

## The loop

1. Finish the task in progress.
2. Take the next plan/phase in the queue.
3. **Re-harden it before executing** — fold in everything you learned implementing the previous phase(s); assumptions it made may now be known-true or known-false, so fix the plan first. (Use the `plan-hardening` skill with `--fix` if it is installed — the flag is what makes it amend the plan rather than just report. Otherwise re-read the plan against the code yourself and correct it in place.)
4. Implement it inline, fully — then verify it: run the tests, run the thing, and confirm the acceptance criteria hold. "Implemented" is not "verified".
5. Repeat until the queue is empty.

## Autonomy rules

1. **Decide, don't ask.** For any choice you could reasonably make yourself, make it and proceed. A recommendation you act on beats a question you wait on.
2. **The only valid stop is a hard physical block** — something you literally cannot do without Loup: a secret/credential only they hold, an external approval or access you don't have, a payment, or an irreversible/destructive action outside your authority.
3. When blocked, **exhaust everything else first**, then record the blocker precisely (exactly what you need and why). Don't halt the whole run over one gap — park it and keep working the rest.
4. **Don't stop, don't ask, don't wait for confirmation.** No mid-run check-ins for permission. Keep going until it's done.

## Not valid reasons to stop

| Rationalization | Reality |
|---|---|
| "I should confirm this approach first" | You have judgment and a standing sign-off. Decide and go. |
| "This is a big / ambiguous decision" | Make the best call, note it in your final report, continue. |
| "Let me check in on progress" | They're away. Progress reports mid-run waste the autonomy you were given. |
| "The plan is unclear here" | Harden it (step 3), resolve the ambiguity yourself, proceed. |
| "This might not be exactly what they want" | Recommend + act. They'll steer afterward if needed. |

## Red flags — you're about to break autonomy

- Writing a question you could answer yourself
- Stopping at a plan/phase boundary to "get the go-ahead"
- Pausing to report progress rather than to report a true blocker
- Treating a reversible decision as if it needed sign-off

**All of these mean: make the call and keep going.**

## Done

Every plan in the queue is implemented and verified. Report the outcome **once**, at the end — not a running commentary, and not a request for permission to continue.
