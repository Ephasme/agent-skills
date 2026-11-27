---
name: bugfix
description: >-
  Takes a bug report to a merged fix: investigates it with the debug-systematically skill, proves
  the root cause with a reproduction that fails, fixes the cause at its source and repairs what the
  bug already broke where it can, opens one pull request per repository, reviews every pull request
  with open-code-review, fixes what the review finds, and merges them in dependency order. Use when
  the user invokes /bugfix followed by a symptom, an error, a failing test or an issue link.
compatibility: >-
  Requires git and an authenticated GitHub CLI `gh`. open-code-review needs its `ocr` CLI and a
  configured provider, with fallbacks described inside.
disable-model-invocation: true
---

# Bugfix

The text after `/bugfix` is the bug report: a symptom, an error message, a failing test, an issue
link. Take it from report to merged pull requests without handing control back between stages; the
user asked for the whole pipeline.

Empty report → ask for it, then start. Nothing else is worth a question before stage 1.

## Track the pipeline

Before any work, create this todo list, each item verbatim, and keep it current. Mark an item done
only when the outcome after its colon holds. The list is what keeps a long run from silently
dropping the review or the merge at the end.

```text
0. Isolate: worktree created per repository, dependencies installed
1. Debug: debug-systematically loaded, symptom reproduced
2. Prove: root cause shown by a test that fails
3. Fix: root cause fixed, test passing, current damage repaired or reported
4. Open pull requests: changes pushed, one opened per repository
5. Review: every pull request reviewed
6. Fix findings: every finding fixed or rejected, fixes pushed
7. Merge: pull requests merged in dependency order
```

## Isolate the work

Never work on the default branch. If the current checkout is not already a dedicated worktree on its
own fix branch, create one per repository the fix touches (`git worktree add -b <branch> <path>
<base>`, or the environment's worktree tool if it has one) and do everything there. Install
dependencies in the new worktree before running anything; a fresh worktree has none.

## Stages

1. **Debug.** Load the `debug-systematically` skill and follow it through stages 1 to 3 here: it
   governs the investigation and the fix, and this skill adds the proof and the delivery around
   them. Reproduce the symptom as reported before reading any code for a cause. Read the report's
   links (issue, logs, failing run) and recent changes to the code involved.
2. **Prove.** The root cause is established when a test written against it fails for the reason
   you state, and the reason is traced to its origin, not to where the error surfaces. Write that
   test where the project keeps its tests; without a test framework, a script that exits non-zero.
   Record the command and its failing output: they go in the pull request. A cause you cannot
   reproduce is a hypothesis, not a cause: keep investigating, never fix on it.
3. **Fix.** Fix the cause where it lives, even when that is another repository or layer than the one
   reporting the error; the symptom's site only gets a change when it also mishandled the bad input.
   Run the test from stage 2 and watch it pass, then the project's checks. Then the current problem:
   what the bug already broke (bad rows, stuck jobs, stale caches, wrong files). Repair it in the
   same change when the repository can carry the repair (a migration, a backfill script, a cache
   invalidation). A repair that would write production data or touch infrastructure is not run:
   put the exact command and its expected effect in the report for the user.
4. **Open pull requests.** Commit the test first, then the fix, so the history shows the test
   failing before the fix lands. Push, and open one pull request per repository, from its fix branch
   to that repo's default branch. The description states the symptom, the root cause and how it was
   traced, the reproduction command with its output before and after the fix, and any damage
   repaired or left for the user. When the fix spans repositories, say in each description which
   other pull requests it pairs with and which must merge first.
5. **Review.** Run the `open-code-review` skill on every pull request, passing the root cause and the
   reproduction as background so the review checks that the fix addresses the cause, not the
   symptom. No OCR provider → the `open-code-review-delegate` skill on the same pull request.
   Neither installed → an independent reviewer sub-agent per pull request with the diff and the
   root cause; no sub-agents → review each diff yourself in a separate pass.
6. **Fix findings.** Address every finding: fix it, or, when a finding is wrong, record why on the
   pull request rather than silently skipping it. Rerun the stage 2 test and the project's checks
   after the last fix, then commit and push. If the fixes changed behaviour, review once more.
7. **Merge in dependency order.** Providers before consumers: a library or schema change merges
   before the code that uses it, a backend before the frontend that calls it. Merge a pull request
   only when its checks are green and the ones it depends on are merged. Merging is the finish line:
   do not deploy or release anything.

## Stop conditions

Stop and report only on what tools cannot resolve: a credential or access you lack, a bug that does
not reproduce once `debug-systematically` has run its course, three failed fixes (that skill's
signal to question the architecture with the user), a root cause in code you cannot change (a
third-party dependency: fix nothing at the symptom, report the cause and where to report it
upstream), a check failing for a reason outside the fix, a merge conflict whose resolution needs a
product decision. Park that repository, finish the others as far as their dependencies allow, then
report the blocker.

## Report

- The root cause in a few lines, and the reproduction: command, output before, output after.
- Per repository: pull request link, merge state, findings fixed and findings rejected with reason.
- Damage repaired, and damage left for the user with the exact command to repair it.
- Anything left unverified.
