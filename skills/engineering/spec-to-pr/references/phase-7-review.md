# Phase 7 — REVIEW

Get the **whole change** reviewed by reviewers that are **not you**. You just spent eight phases
becoming invested in this plan being right; that's exactly the state of mind that misses its flaws.
The value here comes from the reviewers' independence, so run them and take the findings seriously.

**This is not a repeat of Phase 4's task reviews.** Those were *task-scoped gates*: each judged
one task's diff against one task's brief, deliberately blind to the rest of the codebase. Every
one of them could pass while the assembled change is still wrong — because no task reviewer ever
saw the whole thing. This is the first pass that looks at the change **as a whole**, across the
task boundaries, which is precisely where this kind of build's characteristic failures live: a
contract two tasks agreed on that neither got quite right, a duplicated helper three tasks each
wrote their own copy of, an abstraction that made sense per task and reads as incoherent
assembled.

## The call

Run `/engineering-perso:two-axis-review --since <merge-base> --spec <plan-file>`, with the
arguments filled in so it skips its own discovery. Hand it:

- **The fixed point** — the feature branch's merge-base with the default branch, so the review
  sees the whole branch and nothing else. Resolve the base ref in this order, and **keep the
  remote-tracking form** (`origin/main`) rather than stripping the prefix — the local branch of
  that name may not exist in this checkout:

      base_ref=$(git symbolic-ref --quiet --short refs/remotes/origin/HEAD) \
        || base_ref=$(git rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null) \
        || base_ref=""
      [ -n "$base_ref" ] && git merge-base HEAD "$base_ref"

  `refs/remotes/origin/HEAD` is **not always set** — a `--single-branch` clone or a manually
  added remote leaves it absent, and then the first command fails rather than printing a wrong
  answer. If neither resolves, **ask** which branch the work forked from; don't guess `main`.
- **The spec** — the hardened plan file. The ticket's acceptance criteria are the authority behind
  it; name them too, because a reviewer that knows what the change was *supposed* to do catches
  the most dangerous class of bug in this pipeline: code that is internally correct but doesn't do
  what was asked.
- **The deferred Minors** from Phase 4, for re-triage. Pass them as prose alongside the
  invocation and ask which of them must be fixed before merge, now that they can be seen
  together. Three Minors that each looked like polish in isolation can be one Major when they turn
  out to be the same smell in three places. **A roll-up nobody reads is a silent discard** — this
  is where it gets read.

**There is no fallback.** `two-axis-review` is a sibling skill in this plugin; if it isn't in this
session's skill list, the install is broken — stop and say so (Operating rules). A self-review is
not a substitute, and calling it one in a receipt is worse than skipping the phase.

## Enumerate the findings

The two axes come back as separate reports and stay separate — don't merge them into one ranked
list. End the phase with the findings written out and **triaged by severity**:

- **critical / major** → blocking. These drive Phase 8's loop.
- **minor / nice-to-have** → non-blocking. These go to the Phase-9 handoff notes.

Don't silently drop a finding you disagree with. Verify the claim against the code first: read
what the reviewer read. Then either fix it, or say plainly why you reject it, with your reasoning
— performative agreement and quiet dismissal are the same failure wearing different clothes. A
finding you reject on inspection is a fine outcome; a finding you quietly ignore is not.

**Exit:** two reports, findings enumerated and triaged.

**Exit receipt example:**
`✅ Phase 7 (REVIEW) — engineering-perso:two-axis-review on abc1234...HEAD — Standards: 3 findings (1 major); Spec: 2 findings (1 critical: rate limit applied per key, AC says per tenant)`
