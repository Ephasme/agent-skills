Review `git diff origin/<base>...HEAD` and `git log origin/<base>..HEAD` against the task. Read the
surrounding code, the call sites and the tests when the root cause needs them, and run them.

Construct at least one concrete input or state and trace it through the changed logic, looking for a
wrong result that does not error. When the change reads, writes, returns or logs user data, trace one
concrete disclosure or unauthorized operation across a boundary that should stop it.

Report a finding only with evidence of a sequence that occurs during the change's intended usage.
Code shape, duplication and taste are not findings; a broader improvement is not a blocker.

Severity: `critical` and `high` block the merge; `medium` and `low` do not. Anchor every finding at
`file:line`, one-indexed, in changed code; when one invariant breaks in several places, list each
site in the same finding.

Fix in at most 2 rounds, checking each finding is real before touching code. State the invariant it
violates, then fix at the one shared boundary that covers every site, or at every sibling site with
the same small correction. Never grow a fix into handling, state, fallbacks or retries to manage a
symptom. Commit fixes as new commits on the current branch.
