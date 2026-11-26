---
name: feature
description: >-
  Ships a feature end to end from a one-line description: plans it, hardens the plan,
  implements it on an isolated branch, opens one pull request per repository, reviews every
  pull request, fixes what the review finds, and merges them in dependency order. Use when the
  user invokes /feature followed by a description of what to build.
disable-model-invocation: true
---

# Feature

The text after `/feature` is the feature description. Take it from description to merged pull
requests without handing control back between stages; the user asked for the whole pipeline.

Empty description → ask for it, then start. Nothing else is worth a question before stage 1.

## Track the pipeline

Before any work, create a todo list with one item per stage below, and keep it current. The list is
what keeps a long run from silently dropping the review or the merge at the end.

## Isolate the work

Never work on the default branch. If the current checkout is not already a dedicated worktree on its
own feature branch, create one per repository the feature touches (`git worktree add -b <branch>
<path> <base>`, or the environment's worktree tool if it has one) and do everything there. Install
dependencies in the new worktree before running anything; a fresh worktree has none.

## Stages

1. **Plan.** Use the `write-plan` skill on the description. If the description leaves a requirement
   genuinely open (two readings that lead to different code), settle it first with the
   `brainstorm-design` skill; otherwise plan straight away. Skip `write-plan`'s closing
   execution-mode question: stage 3 decides it.
2. **Harden.** Run the `harden-plan` skill on the plan in its default fix mode, never `--no-fix`.
   The plan that comes out is the one you execute.
3. **Implement.** Run the `execute-plan` skill on the hardened plan, sub-agent per task where
   sub-agents are available, inline otherwise. When it offers merge / pull request / keep / delete at
   close-out, take neither: stage 4 owns that.
4. **Open pull requests.** One per repository touched, each from its feature branch to that repo's
   default branch. When the change spans repositories, say in each description which other pull
   requests it pairs with and which must merge first.
5. **Review.** Run the `open-code-review` skill on every pull request. Not installed → spawn an
   independent reviewer sub-agent per pull request with the diff and the plan; no sub-agents →
   review each diff yourself in a separate pass.
6. **Fix.** Address every finding: fix it, or, when a finding is wrong, record why on the pull
   request rather than silently skipping it. Re-run the project's checks after the last fix. If the
   fixes changed behaviour, review once more.
7. **Commit and push** the fixes to each pull request's branch.
8. **Merge in dependency order.** Providers before consumers: a library or schema change merges
   before the code that uses it, a backend before the frontend that calls it. Merge a pull request
   only when its checks are green and the ones it depends on are merged. Merging is the finish line:
   do not deploy or release anything.

## Stop conditions

Stop and report only on what tools cannot resolve: a credential or access you lack, a check failing
for a reason outside the feature, a merge conflict whose resolution needs a product decision. Park
that repository, finish the others as far as their dependencies allow, then report the blocker.

## Report

Per repository: pull request link, merge state, findings fixed and findings rejected with reason,
and anything left unverified.
