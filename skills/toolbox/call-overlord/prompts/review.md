Review `git diff origin/<base>...HEAD` and `git log origin/<base>..HEAD` against the task. Read the
surrounding code, the call sites and the tests touching the change when they are needed to
understand the root cause, and run them.

Construct at least one concrete input or state and trace it through the changed logic, looking for a
case that produces a wrong result without erroring. When the change reads, writes, returns or logs
user data, trace one concrete disclosure or unauthorized operation across the boundary that should
stop it.

Report a finding only with evidence of a concrete sequence that occurs during the change's intended
usage. Code shape, duplication and architectural taste are not findings, and an optional broader
improvement is not a blocker.

Severity: `error` for what must not merge, `warning` for what can wait for a follow-up, `info` for
nice to have. Anchor every finding at `file:line`, one-indexed, in the changed code; when the same
invariant is broken elsewhere in the change, list each site in that same finding.

Fix in at most 2 rounds, checking each finding is real before touching code. State the invariant it
violates, then fix it at the one shared boundary that makes every site hold, or at every sibling site
with the same small correction. Do not grow a fix into machinery — handling, state, fallbacks,
retries — to manage a symptom. Commit fixes as new commits on the current branch.
