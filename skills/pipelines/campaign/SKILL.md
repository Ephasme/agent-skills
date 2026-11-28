---
name: campaign
description: >-
  Takes a product-scale request to a merged stack of pull requests: interrogates the
  user until the request is an actionable epic, writes a macro strategy and a list of features,
  schedules them as a dependency graph with conflict-aware priorities, has one sub-agent per draft
  review it against the others, implements independent features in parallel with the feature
  skill and lands each on a GitHub stacked-PR chain as it finishes, re-plans the remaining
  features after each one lands, reviews the whole stack with open-code-review, then merges it.
  Use when the user invokes /campaign followed by a vast endeavour: a whole application or
  product, thousands of lines across many features and often several repositories, such as
  "build me an app that manages my invoices". A moderately large change within one repository is
  a /feature, not a campaign.
compatibility: >-
  Requires git, an authenticated GitHub CLI `gh` with the `gh stack` extension (github/gh-stack),
  and a GitHub repository with stacked pull requests available. Uses the feature skill;
  open-code-review needs its `ocr` CLI and a configured provider, with fallbacks described inside.
disable-model-invocation: true
---

# Campaign

Explicit invocation only: the text after `/campaign` is the request. A campaign turns it into an
epic, the epic into a strategy and a list of features, the features into a dependency graph and a
schedule, and the schedule into one stacked pull request per feature: independent features are
implemented in parallel, every pull request lands on one stack, and the stack is reviewed as a
whole and merged at the end.

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
  0. Set up: campaign worktree created, campaign files excluded, rerere enabled
  1. Brainstorm: epic.md approved by the user
  2. Strategy: strategy.md and feature files written
  3. Schedule: schedule.md written with graph, conflicts, ranks and k
  4. Review: every draft reviewed, whole-set pass done
Build
  5. Coordinate: replaced by feature items after stage 4
Finish
  6. Global review: every finding fixed or rejected, pull requests marked ready
  7. Merge: stack merged, worktrees removed
```

Where the todo tool has groups or phases, create these three, so that feature items land before
`Finish`; otherwise keep the items flat, in this order. Once stage 4 has settled the features,
replace item 5 with two items per feature, in rank order:

```text
  5.NN <feature-slug>: integrated, pull request opened
  5.NN <feature-slug>: checkpoint done
```

Features run in parallel and finish in any order: tick each pair when its feature lands, not top
to bottom.

## Campaign files

Everything the campaign decides lives in files, not in conversation, because the features are
implemented by fresh sub-agents that start with no memory of it. Before stage 1 writes anything,
fetch the current repository and add a worktree for the campaign, detached at the remote trunk
(`git worktree add --detach <path> origin/<trunk>`). Keep the files untracked at its root, excluded
via `$(git rev-parse --git-common-dir)/info/exclude`; untracked files survive every branch switch
the stack makes. Enable rerere for the clone (`git config rerere.enabled true`): every feature
lands by rebase, and `gh stack` turns rerere on only when it can prompt.

```
.campaign/<slug>/
├── epic.md            # stage 1
├── strategy.md        # stage 2, with a revision log appended in stage 5
├── schedule.md        # stage 3, updated at every checkpoint
└── features/
    ├── 01-<slug>.md   # one per feature; NN is a stable ID, not a position
    └── …
```

Each feature is implemented in a worktree of its own, `<campaign-worktree>-NN`, next to the
campaign worktree. The campaign files exist only in the campaign worktree: hand sub-agents their
absolute paths.

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
  later ones widen it. Attack the riskiest unknown early, while changing course is cheap. Stage 3
  decides what runs in parallel; this principle decides what comes first.
- **Feature table.** ID, slug, one-line outcome, depends on, epic success criteria it serves.
  Every success criterion is served by at least one feature; no feature serves none.

Then one `features/NN-<slug>.md` per feature, written for a reader who has seen nothing else:

- **Description.** The paragraph handed to `/feature` as its argument. Self-sufficient.
- **Acceptance criteria.** Observable, each traceable to an epic criterion.
- **Consumes / provides.** The interfaces, schemas and names it relies on from other features and
  exposes to them. These contracts are what keep the stack coherent.
- **Touches.** The files it expects to create or edit, and the functions, classes, routes or
  registries in them it changes. Stage 3 builds its conflict map from this list: name paths, not
  areas.
- **Out of scope.** What another feature covers, so this one does not drift into it.
- **Status.** `pending`; then `in progress` with its dispatch base and worktree; then `done` with
  its pull request.

Each feature is a vertical slice that leaves its layer of the stack working and its checks green on
its own: a stack merges bottom-up, and any layer may end up merged alone. Size each one as a pull
request a reviewer can read in one sitting. A list that keeps growing usually means the epic
carries scope the user ruled out; cut back to the epic rather than ship a long tail.

### 3. Schedule: features → graph and ranks

Find what can run at the same time, so stage 5 keeps several sub-agents busy without two of them
editing the same code. An optimal schedule is NP-hard to find and the durations are guesses anyway:
build the graph with care, then let a greedy rule run it.

1. **Depends-on edges.** Start from the feature table's "depends on" and check each edge against
   the contracts: B depends on A when B consumes something A provides. Renames and removals are
   ordered in step 2. Add an edge the contracts call for and the table lacks; remove one that no
   contract and no stated reason supports, since every false edge costs parallelism. From here on
   `schedule.md` holds the edges: replace the table's "depends on" column with a pointer to it.
2. **Conflicts.** Two features conflict when their Touches lists share a source file, function,
   class or registry (routes, dependency-injection bindings, migration index, changelog).
   - Before comparing, widen each list with the files that change alongside its files: for each
     file, list the commits that touched it (`git log -n 50 --format=%H -- <file>`) and add the
     files that appear in at least three of them and in at least a third of them
     (`git show --name-only --format= <sha>`). Coupling the code does not show lives there. Never
     widen with a file most of the repository's commits touch (changelog, manifest, version file)
     unless the feature's own list names it.
   - Skip generated files that are regenerated rather than merged.
   - A conflict is not an order: either feature may go first, never both at once. A feature that
     renames or removes a symbol others use is an order, not a conflict: add the depends-on edge
     that puts it after them, or have them consume the new name.
3. **Break edges.** Each remaining edge serialises work; remove the ones you can.
   - Shared interfaces, schemas and registry entries that several features need go into the
     earliest feature serving a success criterion, usually 01, as working code, and the consumers'
     "Consumes" point at it. Never add a feature that only holds stubs: it serves no criterion,
     and its layer may merge alone.
   - A file or registry most features must edit gets one owner feature; the others consume what it
     exposes, and it leaves their lists, widened ones included.
   - A feature whose small part causes an edge is split, the part moving to the feature it depends
     on or to a new feature.
   Update the feature files and the `schedule.md` table with each change, and record it with its
   reason in `schedule.md`.
4. **Validate.** Remove features with no remaining parent, repeatedly; features left over form a
   cycle: split or merge them until none remains. In the drawn graph, drop edges implied by others
   (A → B → C makes A → C redundant).
5. **Size and bound.**
   - Size each feature S, M or L, weighing 1, 2 and 4.
   - W is the sum of the weights. L is the heaviest path through the graph. W/L is the most
     speedup any number of agents can give.
   - Set the concurrency `k = min(4, max(1, ⌊W/L⌋))`, and k = 1 without sub-agents. Past four
     parallel agents, integration and conflict costs outgrow the gain.
6. **Rank.** A feature's bottom level is its weight plus the largest bottom level among the
   features that depend on it; compute it from the last features backwards. Rank by bottom level,
   highest first: the heaviest remaining chain sets the finish time. Break ties by more direct
   dependents, then smaller size, then lower ID.

`schedule.md` holds:
- the graph, as a Mermaid flowchart of depends-on edges;
- a table with ID, slug, size, depends on, conflicts with, bottom level and rank;
- W, L, W/L and k;
- the edges broken, with their reasons.

Later changes to it are logged in the revision log of `strategy.md`, with the feature changes that
cause them.

It ranks; it is not a timetable. Stage 5 starts features in rank order as agents free up, and
re-ranks at each checkpoint.

### 4. Review: one sub-agent per draft

Spawn one reviewer per draft, in parallel:
- one owns `strategy.md` and checks it against `epic.md`;
- one owns `schedule.md`;
- one owns each feature file.

Every reviewer reads all campaign files and edits only the one it owns, so no two agents write the
same file.

- **Feature reviewers** check:
  - the description is enough for an implementer who has seen nothing else;
  - acceptance criteria are observable;
  - the feature is a vertical slice depending only on the parents `schedule.md` gives it;
  - its contracts match what the others consume and provide;
  - its Touches list names every file the description implies;
  - it overlaps no other feature;
  - every claim about existing code is true.
- **The strategy reviewer** checks that the features together cover every epic success criterion
  and nothing out of scope, and that the riskiest unknown is resolved early.
- **The schedule reviewer** checks:
  - every depends-on edge rests on a contract or a stated reason, and none is missing;
  - every pair of features whose Touches lists overlap is marked as conflicting;
  - the graph has no cycle;
  - sizes, W, L, k and ranks follow stage 3.
- **Across drafts.** A problem that lives in another draft goes to its owner as a message with the
  concrete change. The owner applies it or answers why not. A disagreement two reviewers cannot
  settle comes to you, and you decide on the merits. Without agent-to-agent messaging, each
  reviewer lists its cross-draft changes in its result, and you route them to the owners in a
  second round.

When every reviewer has finished, read all files once more as a whole and fix what still clashes.
If a contract or a Touches list changed during that pass, update the graph and ranks, and have the
affected reviewers check their drafts again.

No sub-agents → review the drafts one at a time yourself, strategy first and schedule second,
writing each review's findings to a file before the next, then do the whole-set pass.

### 5. Coordinate: features in parallel, landed in completion order

Run up to k features at once, each in a fresh sub-agent and its own worktree, and land each on top
of the one stack as it finishes; without sub-agents, k is 1 and you implement each feature inline.
Only you run `gh stack`, push, or open pull requests: gh-stack serialises its mutations across the
clone, and one owner keeps the stack consistent. Every other repository the strategy touches gets
a campaign worktree of its own, made like the first (detached at its remote trunk, rerere
enabled), without the campaign files.

Repeat until no feature is pending or in progress:

1. **Dispatch.** A feature is ready when every parent in `schedule.md` has landed (status `done`).
   While fewer than k features are in progress, start the ready feature of highest rank that
   conflicts with none in progress. When none qualifies, wait for a report.
2. **Integrate** each feature as it reports, one at a time.
3. **Checkpoint** after each integration, before dispatching again.

#### Dispatch a feature

1. **Base.** The dispatch base is the top of the stack: its top branch, or `origin/<trunk>` before
   the first feature lands. Record its commit (`git rev-parse <top>`) and the worktree path in the
   feature's status, set to `in progress`.
2. **Worktree.** `git worktree add -b campaign/<slug>/NN-<feature-slug> <campaign-worktree>-NN
   <dispatch base>`, then install the dependencies there before anything runs.
3. **Implement.** Run the `feature` skill with the feature file's description, in a fresh
   sub-agent, or inline without sub-agents. Hand it the absolute paths of `epic.md`,
   `strategy.md`, `schedule.md` and its feature file, and these overrides of the feature skill:
   - It is already on its own branch in a dedicated worktree, one per repository it touches. It
     works there, creates no other branch or worktree, and does not edit the campaign files.
   - It skips its stage 0 (isolate) and stage 4 (open pull requests).
   - Its stage 5 reviews the branch's own commits instead of a pull request: `open-code-review` in
     branch comparison mode from the dispatch base to `HEAD` in each worktree, with the same
     fallbacks.
   - Its stage 6 records rejected findings in its report instead of on a pull request.
   - Its stage 7 commits without pushing.
   - It skips its stage 8: the stack merges whole, once, after the global review.
   - It runs no `gh stack` and no `git push`.
   - Report: what shipped against the feature file, deviations, contracts actually created (names,
     paths, signatures), files changed outside its Touches list, review findings rejected and why,
     anything unverified, and any sign that another feature is now wrong.
   - Inline only (no sub-agents, so k is 1): create no todo list, since replacing the campaign's
     would drop stages 6 and 7. Insert the feature skill's items 1, 2, 3 and 6 instead, its item 5
     as `Review: branch commits reviewed` and its item 7 as `Commit: fixes committed`, since there
     is no pull request and nothing is pushed. Put them right before
     `5.NN <feature-slug>: integrated, pull request opened`, each numbered `5.NN.K` with K its
     number there (`5.01.1 Plan: plan written`). Remove them once the feature reports.

#### Integrate a feature

1. **Rebase.** In the feature's worktree, unless its commits already sit on the current top
   (`git merge-base --is-ancestor <top> HEAD` succeeds), move them there:
   `git rebase --onto <top> <dispatch base>`. The recorded base replays only the feature's commits,
   even when a lower layer was rewritten after dispatch. Then record `<top>`'s commit as the
   feature's dispatch base, whoever finished the rebase: a retry replays only the feature's commits.
2. **Check.** Rerun the feature's checks there, reinstalling the dependencies first if the rebase
   changed a lockfile or manifest.
3. **Failures go back.** On a rebase conflict, run `git rebase --abort` first. Then hand the
   conflict or the red check to the feature's sub-agent, or to a fresh one given the feature file,
   the dispatch base, the top and the failure; inline, you handle it. The author reruns the same
   rebase, resolves it, commits any fix, and integration resumes from step 1. Other reports wait
   their turn meanwhile, so the top does not move under the fix.
4. **Free the branch.** `git worktree remove <campaign-worktree>-NN`; the branch stays. If it
   refuses over untracked files, confirm none belongs to the feature, then add `--force`.
5. **Stack it.** In the campaign worktree:
   - The first feature: `git switch campaign/<slug>/NN-<feature-slug>`, then
     `gh stack init --base <trunk> campaign/<slug>/NN-<feature-slug>`, then install the
     dependencies.
   - Every later feature: `gh stack top`, then `gh stack add campaign/<slug>/NN-<feature-slug>`,
     which adopts the branch and checks it out.
   - Whenever the campaign worktree moves to a commit whose lockfile or manifest differs, reinstall
     the dependencies before running checks there.
6. **Open its pull request** with `gh stack submit --auto`: a draft whose base is the layer below.
   Then set its title and description with `gh pr edit`. The description states:
   - the epic in one line;
   - the feature's position (`N of M`, M being the current number of features);
   - what it builds on;
   - the review findings it rejected, and why.
7. **Done.** Set the feature's status to `done` with its pull request.

#### Checkpoint

Before the next dispatch, check that the campaign still makes sense:

- Read the pull request diff (`gh pr diff`), not only the report. Reports drift from code.
- Compare the files it changed with its Touches list. A file outside the list that another pending
  or in-progress feature touches is a conflict the map missed: add it to `schedule.md`. A feature
  in progress meets it at its own rebase.
- If the trunk moved, `gh stack sync`.
- For each pending feature, decide: keep, amend, split, merge with another, drop, or add a new
  feature that the work revealed.
  - Update the feature files, the graph and the ranks.
  - Append each change, with its reason, to the revision log in `strategy.md`.
  - Only pending features change. An in-progress feature that a change invalidates is stopped:
    stop its sub-agent, remove its worktree (`git worktree remove --force`) and branch
    (`git branch -D`), reset it to `pending`, and dispatch it again later.
- Keep the todo list matching the feature files: a dropped feature loses its two items, and a new
  or split feature gets two.
- A defect in a layer already built is fixed in that layer:
  - In the campaign worktree, check out its branch and commit the fix.
  - Run `gh stack rebase --upstack` and `gh stack push`, then rerun that layer's checks.
  - Features in progress need nothing: their recorded dispatch base keeps their rebase correct.
  - New scope goes on as a feature.
- Escalate to the user only when a change would alter the epic: dropping or adding a success
  criterion, or moving its scope. Decide everything else yourself.

A feature that touches several repositories gets a worktree and a dispatch base in each, lands in
the stack of each the same way, and its pull requests say which other ones they pair with.

### 6. Global review: the whole stack

Each feature was reviewed alone by the feature skill. This pass looks for what no single layer
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

### 7. Merge

1. `gh stack sync` so the stack sits on the current trunk, then wait for every pull request's
   checks to finish (`gh pr checks <pr> --watch`). Each must be green.
2. Merge the whole stack with `gh stack merge --yes` and the merge method the repository uses
   (`--squash`, `--rebase` or `--merge`; `gh repo view --json` lists the allowed ones). The merge is
   atomic: either every layer lands or none does. With several repositories, merge their stacks
   providers first: a library or schema before its consumers, a backend before its frontend.
3. A merge the repository refuses (required approvals, branch protection, a merge queue rejection)
   is reported, never bypassed. Merging is the finish line: deploy and release nothing.
4. Remove the campaign worktrees and any feature worktree left.

## Stop conditions

Stop and report only on what tools cannot resolve: an access or credential you lack, a check
failing for a reason outside the campaign, an epic-level change awaiting the user, a conflict whose
resolution needs a product decision. Finish everything that does not depend on the blocker first.

## Report

- The epic in one line and the stack (`gh stack view` output, plus its URL).
- The schedule: W/L, k, and the most features that ran at once.
- Per layer: pull request link, feature, and merge state.
- Revisions made between features, each with its reason.
- Global review findings fixed, and rejected with the reason.
- Anything left unverified.
