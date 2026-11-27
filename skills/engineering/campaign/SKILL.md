---
name: campaign
description: >-
  Takes a vague, one-line product request to a merged stack of pull requests: interrogates the
  user until the request is an actionable epic, writes a macro strategy and an ordered list of
  features, has one sub-agent per draft review it against the others, implements the features one
  at a time with the feature skill on a GitHub stacked-PR chain, re-plans the remaining features
  after each one lands, reviews the whole stack with open-code-review, then merges it. Use when the
  user invokes /campaign followed by a request too large for a single /feature.
compatibility: >-
  Requires git, an authenticated GitHub CLI `gh` with the `gh stack` extension (github/gh-stack),
  and a GitHub repository with stacked pull requests available. Uses the feature skill;
  open-code-review needs its `ocr` CLI and a configured provider, with fallbacks described inside.
disable-model-invocation: true
---

# Campaign

Explicit invocation only: the text after `/campaign` is the request. A campaign turns it into an
epic, the epic into a strategy and an ordered list of features, and the features into one stacked
pull request each, reviewed as a whole and merged at the end.

Empty request → ask for it, then start.

The user is consulted in stage 1 and approves the epic at its end. From then on, run every stage to
the end without handing control back, except for the escalations named below: the user asked for
the whole campaign, and a pause between features costs them a context switch for nothing.

## Track the campaign

Before any work, create this todo list, each item verbatim, and keep it current. Mark an item done
only when the outcome after its colon holds. A campaign runs for hours; the list is what stops the
global review from being dropped at the end.

```text
Define
  0. Set up: campaign worktree created, campaign files excluded
  1. Brainstorm: epic.md approved by the user
  2. Strategy: strategy.md and feature files written
  3. Review: every draft reviewed, whole-set pass done
Build
  4. Coordinate: replaced by feature items after stage 2
Finish
  5. Global review: every finding fixed or rejected, pull requests marked ready
  6. Merge: stack merged, worktrees removed
```

Where the todo tool has groups or phases, create these three, so that feature items land before
`Finish`; otherwise keep the items flat, in this order. Once stage 2 has listed the features,
replace item 4 with two items per feature, in implementation order:

```text
  4.NN <feature-slug>: pull request opened
  4.NN <feature-slug>: checkpoint done
```

## Campaign files

Everything the campaign decides lives in files, not in conversation, because the features are
implemented by fresh sub-agents that start with no memory of it. Before stage 1 writes anything,
fetch the current repository and add a worktree for the campaign, detached at the remote trunk
(`git worktree add --detach <path> origin/<trunk>`). Keep the files untracked at its root, excluded
via `$(git rev-parse --git-common-dir)/info/exclude`; untracked files survive every branch switch
the stack makes:

```
.campaign/<slug>/
├── epic.md            # stage 1
├── strategy.md        # stage 2, with a revision log appended in stage 4
└── features/
    ├── 01-<slug>.md   # one per feature, in implementation order
    └── …
```

## Stages

### 1. Brainstorm: request → epic

The request is vague by assumption. Make it actionable by asking, not by guessing.

1. **Read first.** Explore the code, docs and repo instructions (`AGENTS.md`, `CLAUDE.md`,
   `GEMINI.md`, `.cursor/rules`) the request touches. Never ask what the code can answer.
2. **Interrogate in rounds.** Ask a few questions per round, each with the options you see and the
   one you recommend; use a structured multiple-choice prompt where the agent has one. Let each
   round build on the last answers. Keep going until the exit test below passes, however many
   rounds that takes.
3. **Challenge, do not transcribe.** When the request names a solution, dig for the problem behind
   it. Ask who it is for and what they do today, what observable result proves it works, the
   smallest version still worth shipping, what is explicitly out, what existing behaviour must not
   break, and the constraints (deadline, stack, compliance, cost). Say so when something already
   does the job, or when the request is two epics.
4. **Exit test.** The epic is actionable when every success criterion is observable, scope in and
   out is explicit, and no open question remains whose two answers would produce different
   features.
5. **Write `epic.md`:** problem, users, goal, success criteria, in scope, out of scope,
   constraints, risks, and the decisions taken with the user. Show it to the user and get their
   approval. This is the campaign's only gate.

### 2. Strategy: epic → features

Write `strategy.md`:

- **Approach.** The architectural direction, the repositories touched, the trunk branch each stack
  targets, and the riskiest unknown with where it gets resolved.
- **Sequencing principle.** The first feature is the thinnest end-to-end path through the system;
  each later one widens it. Attack the riskiest unknown early, while changing course is cheap.
- **Feature table.** Order, slug, one-line outcome, depends on, epic success criteria it serves.
  Every success criterion is served by at least one feature; no feature serves none.

Then one `features/NN-<slug>.md` per feature, written for a reader who has seen nothing else:

- **Description.** The paragraph handed to `/feature` as its argument. Self-sufficient.
- **Acceptance criteria.** Observable, each traceable to an epic criterion.
- **Consumes / provides.** The interfaces, schemas and names it relies on from earlier features and
  exposes to later ones. These contracts are what keep the stack coherent.
- **Out of scope.** What a later feature covers, so this one does not drift into it.
- **Status.** `pending`, then `in progress`, then `done` with its pull request.

Each feature is a vertical slice that leaves its layer of the stack working and its checks green on
its own: a stack merges bottom-up, and any layer may end up merged alone. Size each one as a pull
request a reviewer can read in one sitting. A list that keeps growing usually means the epic
carries scope the user ruled out; cut back to the epic rather than ship a long tail.

### 3. Review: one sub-agent per draft

Spawn one reviewer per draft, in parallel: one owns `strategy.md` (and checks it against
`epic.md`), one owns each feature file. Every reviewer reads all campaign files and edits only the
one it owns, so no two agents write the same file.

- **Feature reviewers** check that the description is enough for an implementer who has seen
  nothing else, that acceptance criteria are observable, that the feature is a vertical slice
  depending only on earlier features, that its contracts match what its neighbours consume and
  provide, that it overlaps no other feature, and that every claim about existing code is true.
- **The strategy reviewer** checks that the features together cover every epic success criterion
  and nothing out of scope, that the order respects every dependency, and that the riskiest unknown
  is resolved early.
- **Across drafts.** A problem that lives in another draft goes to its owner as a message with the
  concrete change. The owner applies it or answers why not. A disagreement two reviewers cannot
  settle comes to you, and you decide on the merits. Without agent-to-agent messaging, each
  reviewer lists its cross-draft changes in its result, and you route them to the owners in a
  second round.

When every reviewer has finished, read all files once more as a whole and fix what still clashes.
If a contract changed during that pass, have the affected reviewers check their drafts again.

No sub-agents → review the drafts one at a time yourself, strategy first, writing each review's
findings to a file before the next, then do the whole-set pass.

### 4. Coordinate: one feature at a time

In the campaign worktree, create the first feature's branch off the trunk and make it the bottom of
the stack:

```sh
git switch -c campaign/<slug>/01-<feature-slug> origin/<trunk>
gh stack init --base <trunk> campaign/<slug>/01-<feature-slug>
```

Install the dependencies there before anything runs. Every other repository the strategy touches
gets its own campaign worktree and stack the same way.

Then, in order and for each feature, until none is pending:

1. **Branch.** From the top of the stack, `gh stack add campaign/<slug>/NN-<feature-slug>`, except
   for the first, already in place. Set the feature's status to `in progress`.
2. **Implement.** Run the `feature` skill with the feature file's description, in a fresh
   sub-agent where available so each feature starts with a clean context, inline otherwise. Hand
   it `epic.md`, `strategy.md` and its feature file to read, and these overrides of the feature
   skill:
   - It is already on its own branch in a dedicated worktree: work there, create no other branch
     or worktree, and do not edit the campaign files.
   - Inline only: create no todo list, since replacing the campaign's would drop stages 5 and 6.
     Insert the feature skill's items 1 to 7 instead, right before
     `4.NN <feature-slug>: pull request opened`, each numbered `4.NN.K` with K its number there
     (`4.01.1 Plan: plan written`); its items 0 and 8 do not apply here. Remove them once the
     feature reports.
   - Open the pull request with `gh stack submit --auto` (a draft whose base is the layer below),
     then set its title and description with `gh pr edit`. The description states the epic in one
     line, the feature's position (`N of M`) and what it builds on.
   - Do not merge. The stack merges whole, once, after the global review.
   - Report: pull request link, what shipped against the feature file, deviations, contracts
     actually created (names, paths, signatures), review findings rejected and why, anything
     unverified, and any sign that a later feature is now wrong.
3. **Checkpoint.** Before the next feature, check that the campaign still makes sense:
   - Read the pull request diff (`gh pr diff`), not only the report. Reports drift from code.
   - If the trunk moved, `gh stack sync`.
   - For each pending feature, decide: keep, amend, split, merge with another, drop, or add a new
     feature that the work revealed. Update the files and append each change with its reason to the
     revision log in `strategy.md`.
   - Keep the todo list matching the feature files: a dropped feature loses its two items, and a
     new or split feature gets two in its place in the order.
   - A defect in a layer already built is fixed in that layer: check out its branch, commit the
     fix, `gh stack rebase --upstack`, `gh stack push`, and rerun that layer's checks. New scope
     goes on top as a feature.
   - Escalate to the user only when a change would alter the epic: dropping or adding a success
     criterion, or moving its scope. Decide everything else yourself.

A feature that touches several repositories adds a layer to the stack of each repository it
touches, and its pull requests say which other ones they pair with.

### 5. Global review: the whole stack

Each pull request was reviewed alone by the feature skill. This pass looks for what no single layer
shows: features that integrate badly, logic duplicated across layers, code a later layer made dead,
names and patterns that drifted between features, leftovers of changed plans.

1. Run the `open-code-review` skill on the range from the trunk to the top of the stack, in branch
   comparison mode with behaviour analysis, passing the epic and the strategy's approach as
   background. Its PR mode reviews one pull request at a time; this target covers the stack whole.
   No OCR provider → the `open-code-review-delegate` skill on the same range. Neither installed →
   an independent reviewer sub-agent with the range diff, `epic.md` and `strategy.md`; no
   sub-agents → review the range yourself in a separate pass.
2. Fix each finding in the lowest layer whose diff introduced it, then `gh stack rebase --upstack`
   and `gh stack push`. A finding you reject gets a comment on its pull request saying why.
3. Rerun the checks on every layer that changed: each must stay green on its own.
4. If the fixes changed behaviour, run the global review once more.
5. Mark every pull request of the stack ready for review (`gh pr ready`).

### 6. Merge

1. `gh stack sync` so the stack sits on the current trunk, then wait for every pull request's
   checks to finish (`gh pr checks <pr> --watch`). Each must be green.
2. Merge the whole stack with `gh stack merge --yes` and the merge method the repository uses
   (`--squash`, `--rebase` or `--merge`; `gh repo view --json` lists the allowed ones). The merge is
   atomic: either every layer lands or none does. With several repositories, merge their stacks
   providers first: a library or schema before its consumers, a backend before its frontend.
3. A merge the repository refuses (required approvals, branch protection, a merge queue rejection)
   is reported, never bypassed. Merging is the finish line: deploy and release nothing.
4. Remove the campaign worktrees.

## Stop conditions

Stop and report only on what tools cannot resolve: an access or credential you lack, a check
failing for a reason outside the campaign, an epic-level change awaiting the user, a conflict whose
resolution needs a product decision. Finish everything that does not depend on the blocker first.

## Report

- The epic in one line and the stack (`gh stack view` output, plus its URL).
- Per layer: pull request link, feature, and merge state.
- Revisions made between features, each with its reason.
- Global review findings fixed, and rejected with the reason.
- Anything left unverified.
