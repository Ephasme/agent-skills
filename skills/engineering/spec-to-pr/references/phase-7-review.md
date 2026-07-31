# Phase 7 — REVIEW

Get the **whole change** reviewed by a reviewer that is **not you**. You just spent eight phases
becoming invested in this plan being right; that's exactly the state of mind that misses its flaws.
The value here comes from the reviewer's independence, so run it and take the findings seriously.

**This is not a repeat of Phase 4's task reviews.** Those were *task-scoped gates*: each judged
one task's diff against one task's brief, deliberately blind to the rest of the codebase. Every
one of them could pass while the assembled change is still wrong — because no task reviewer ever
saw the whole thing. This is the first pass that looks at the change **as a whole**, across the
task boundaries, which is precisely where this kind of build's characteristic failures live: a
contract two tasks agreed on that neither got quite right, a duplicated helper three tasks each
wrote their own copy of, an abstraction that made sense per task and reads as incoherent
assembled.

## The call

Dispatch **one general reviewer subagent** over the whole branch. Set `model` and `effort`
explicitly (Operating rules) — this is the last check before a human reads the PR, so it is not
the dispatch to economise on. Build its diff with `$SKILL_DIR/scripts/review-package BASE HEAD` so
the package never enters your context, and hand the reviewer:

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
- **The deferred Minors** from Phase 4, for re-triage. Ask which of them must be fixed before
  merge, now that they can be seen together. Three Minors that each looked like polish in isolation
  can be one Major when they turn out to be the same smell in three places. **A roll-up nobody
  reads is a silent discard** — this is where it gets read.

## What to ask it for

The reviewer answers two questions about the assembled branch, and reports them separately:

- **Standards** — does the change follow this repo's documented conventions, plus the ordinary
  code-smell baseline? Point it at the repo's own standards files (`AGENTS.md` / `CLAUDE.md`, a
  `CONTRIBUTING.md`, a `docs/` style guide) and tell it to read them before judging, rather than
  applying generic taste.
- **Spec** — does the branch faithfully implement what was asked: nothing missing, nothing extra,
  nothing built wrong? This is judged against the hardened plan and the acceptance criteria, not
  against what the code appears to be trying to do.

Tell it to keep the two answers apart in its report and to tag every finding as one or the other.
They are different repairs and Phase 8 routes them differently.

Give it the same evidence discipline the task reviewer works under: read the review package rather
than crawling the codebase, cite `file:line` for every finding, treat the plan's authorship as no
defence, and stay read-only on the checkout.

**A self-review is not a substitute.** If this agent cannot dispatch a subagent at all, say so
plainly in the receipt and in the Phase 9 handoff — a whole-branch review you performed on your own
work is materially weaker evidence, and a receipt that doesn't admit it is worse than a skipped
phase.

## Enumerate the findings

The two answers stay separate — don't merge them into one ranked list. End the phase with the
findings written out and **triaged by severity**:

- **critical / major** → blocking. These drive Phase 8's loop.
- **minor / nice-to-have** → non-blocking. These go to the Phase-9 handoff notes.

Don't silently drop a finding you disagree with. Verify the claim against the code first: read
what the reviewer read. Then either fix it, or say plainly why you reject it, with your reasoning
— performative agreement and quiet dismissal are the same failure wearing different clothes. A
finding you reject on inspection is a fine outcome; a finding you quietly ignore is not.

**Exit:** findings enumerated and triaged, Standards and Spec reported separately.

**Exit receipt example:**
`✅ Phase 7 (REVIEW) — whole-branch reviewer on abc1234...HEAD — Standards: 3 findings (1 major); Spec: 2 findings (1 critical: rate limit applied per key, AC says per tenant)`
