---
name: linear-project-sync
description: >-
  Reconcile a repo's Linear project with reality and leave it greenfield — read every
  ticket, cross-check each one's status, priority, and estimate against what the code,
  git history, and merged PRs actually show, rewrite stale descriptions down to the
  current desired state, then close done/obsolete tickets, reopen regressed ones, and
  create tickets for uncovered gaps — so the board reads as if it were freshly planned
  today and is ready to pick up cold next session. Grounds every status/close/reopen
  call in evidence and ends with a report of everything it changed. Resolves the project
  from a "Linear project" section in the repo's CLAUDE.md; if none exists, it asks for
  the project name/id + team, resolves them, and writes that section. Use whenever the
  user wants to sync, groom, tidy, clean up, triage, refresh, or update the Linear board
  or tickets for the current project, "greenfield the linear project", get the backlog in
  shape, reconcile tickets with what's actually been done, or prep the project for the
  next work session — even when they just say "update linear", "sort out the tickets",
  "get the board ready", or "make linear match where we actually are". Applies changes
  autonomously by default; pass `--dry-run` for a plan-only preview that reads the board and
  reports what it would change without any Linear writes.
---

# linear-project-sync

Take the Linear project attached to the repo you're in and make it **true and greenfield**:
every ticket's status, priority, estimate, and description reflect where the work actually
is *right now*, done and dead tickets are gone, real gaps have tickets, and the project
itself carries a clean description and a fresh snapshot — so someone (or you, next session)
can open the board and immediately know what's left, with no archaeology.

**North star:** after this runs, the board should read as if a careful lead planned exactly
the remaining work from scratch today — no done work lingering as "todo", no obsolete
acceptance criteria referencing an approach that was abandoned, no vague one-liners, no
orphan work happening in the code with no ticket. "Greenfield" here is the same idea as the
[`greenfield`](../greenfield/SKILL.md) doc skill, applied to a board: strip the history and
the cruft, keep only the current desired state.

## The one rule that outranks "autonomous"

This skill runs autonomously and applies changes without asking. That freedom rests entirely
on **one discipline: never mutate on a guess.** Every status change, every close, every
reopen must trace to concrete evidence — a merged PR, a commit, code that exists (or doesn't),
a ticket that's a literal duplicate of another. Closing a ticket you *believe* is done, when
it isn't, is the single expensive, trust-destroying mistake this skill can make, and it is
worse than doing nothing.

So the boundary is: **evidence → act; no evidence → don't act, record it.** When you can't
tell whether a ticket is done, whether two tickets are really duplicates, or whether a rewrite
would lose intent you don't understand, **leave it untouched and surface it in the final report
under "Needs a human"** rather than force a call. Autonomous means you don't ask permission for
the calls you *can* ground. It does not mean you resolve ambiguity by guessing.

Content edits (rewording, tightening, adding estimates, fixing priority) are low-stakes and
reversible — act freely. Status flips and structural changes (close/create/reopen) are the ones
that need the evidence bar above.

## Mode: `--dry-run`

`--dry-run` changes exactly one variable: **whether any Linear write happens.** In dry-run you do
everything below — resolve the project, build ground truth, read the board, evaluate every ticket,
decide every close/reopen/create — but you **call no mutating tool** (`save_issue`, `save_project`,
`save_comment`, `save_status_update`, `create_issue_label`). Reading is unchanged; only the writes
are withheld. Phase 0 is the sole exception: writing the `## Linear project` section to CLAUDE.md
is local, not a Linear mutation, so still do it — the next real run needs it.

The Phase 6 report becomes the whole deliverable: it reads as "what I *would* change" instead of
"what I changed" (`would close`, `would set`, …). Use it as the trust-building first pass on any
board you haven't run this on before, or whenever the user asks for a preview. Without the flag,
the skill applies autonomously as described everywhere else.

## Phase 0 — Resolve the project

The skill needs one Linear project to operate on: the one belonging to *this repo*. Look for a
`## Linear project` section in the repo's `CLAUDE.md` (`${CLAUDE_PROJECT_DIR}/CLAUDE.md`, or the
CLAUDE.md at the repo root):

```markdown
## Linear project

- **Project**: <Project Name> — `<project-uuid>`
- **Team**: <Team Name> (`<TEAM-KEY>`) — `<team-uuid>`
- **URL**: <linear project url>
```

**If the section exists**, use the UUIDs directly — no lookup needed, no ambiguity.

**If it's missing**, ask the user two things and nothing else: the **project** (name or id/URL)
and the **team** it lives in. Then resolve them against Linear (`list_teams` to match the team,
`list_projects` filtered to that team to match the project), confirm you found the right one by
name, and **write the section into CLAUDE.md** using the format above — storing the resolved
UUIDs and the team key so the next run skips this entirely. Place it near other project-context
sections; don't disturb the rest of the file.

The **team key** (e.g. `ENG`) matters beyond identification: ticket identifiers (`ENG-142`) are
built from it, and those identifiers are how you'll link tickets to git history in Phase 1.

## Phase 1 — Establish ground truth *before* touching the board

You cannot judge a ticket's real status from the ticket. Judge it from the world the ticket
describes. Build that picture first:

- **Git history** — recent commits and merged branches. Grep commit messages and branch names
  for the team key (`git log --oneline -50`, `git branch -a`, look for `ENG-###`). A ticket
  whose id appears in a merged commit/PR is almost certainly done.
- **Merged & open PRs** — the author's convention prefixes PR titles with the ticket id, so
  merged PRs are the strongest "this is done" signal and open PRs mean "in progress". Use the
  GitHub tools (`list_pull_requests`, `search_pull_requests`) or `gh` if a remote exists.
- **The code itself** — when a ticket describes a feature/file/function, check whether it exists
  and does what the ticket asks. `TODO`/`FIXME`/`HACK` comments and obvious missing pieces are
  raw material for gap tickets in Phase 4.

Keep a running map of `ticket id → evidence` (done / in-progress / no-trace / can't-tell). This
map is what licenses every Phase 3–4 mutation. No entry, no structural change.

If the repo has no git history or no PRs to draw on, say so — you can still greenfield content
and estimates, but be far more conservative about flipping status to Done, and lean on ticket
comments and the code for evidence instead.

## Phase 2 — Read the whole board

Pull the full current state so you evaluate against real Linear config, not assumptions:

- `get_project` — description, state, health, dates, the current story.
- `list_issues` filtered to the project (include all states — you need the closed ones too, to
  catch wrongly-closed work) — then `get_issue` for detail and `list_comments` for context on
  anything non-obvious. Include sub-issues.
- `list_issue_statuses` for the team — the actual workflow states and their **types**
  (`backlog` / `unstarted` / `started` / `completed` / `canceled`). Teams rename these, so key
  off the *type*, never a hardcoded name.
- `get_team` — read the estimation settings (`issueEstimationType`: `notUsed` / `fibonacci` /
  `exponential` / `linear` / `tShirt`, plus allow-zero/extended). Only set estimates on the
  team's scale, and only if the team uses them at all.
- `list_project_labels` / `list_issue_labels`, and cycles/milestones if the project uses them,
  so labels and grouping you set already exist.

## Phase 3 — Reconcile each ticket

For every open ticket (and closed ones that Phase 1 shows are *not* actually done), evaluate:

- **Status** — move it to the workflow state that matches ground truth. Merged PR / shipped code
  → a `completed` state. Open PR or active branch → `started`. Untouched → leave in `backlog`/
  `unstarted`. Only flip status when Phase 1 has evidence; a ticket with no trace stays where it
  is. This is the highest-value correction on the board — a status that lies is worse than a
  missing estimate.
- **Priority** — Linear's scale is `1` Urgent, `2` High, `3` Medium, `4` Low, `0` None. Set/adjust
  only when the current value is clearly wrong given the project's goal (a blocker sitting at Low,
  a nice-to-have marked Urgent). Don't churn reasonable priorities — you don't have the full
  business context the user does.
- **Estimate ("difficulty")** — this maps to Linear's **estimate** field. Fill it in where it's
  missing and you can judge the size from the work, and correct estimates that are wildly off.
  Respect the team's scale from Phase 2; if the team doesn't use estimates, skip this entirely.
- **Description — the greenfield pass** — rewrite so it describes the *current desired state* and
  nothing else. Cut references to abandoned approaches, obsolete acceptance criteria, resolved
  open questions, and "we used to…" narration. Make vague one-liners actionable: what's the
  outcome, how do you know it's done. **Be conservative** — tighten and correct, don't rewrite a
  clear, correct description just to restyle it. If a description encodes intent you don't fully
  understand, keep it and note it for the report rather than flatten it.
- **Labels / assignee / cycle** — align obvious mismatches (a bug with no `bug` label, a done
  ticket still assigned as if active). Low stakes; fix what's clearly off, leave the rest.

## Phase 4 — Structural changes (the evidence-gated ones)

- **Close** tickets that Phase 1 proves are done (→ a `completed` state) or that are obsolete —
  superseded, duplicated, or describing work that will never happen. Leave a one-line comment
  saying *why* and pointing at the evidence (the PR, the superseding ticket) before closing, so
  the close is auditable and reversible in meaning, not just a silent disappearance.
- **Reopen** tickets that were closed but Phase 1 shows the work isn't actually there — a reverted
  change, a feature that regressed, an "acceptance criterion" that was never met. Move back to an
  appropriate active/backlog state and comment why.
- **Create** tickets for real work that has no ticket: `TODO`/`FIXME` clusters, obvious follow-ups
  from merged PRs, missing pieces the code makes plain. Write them to the same greenfield bar you
  hold existing tickets to — clear outcome, right priority, an estimate if the team uses them,
  labels that exist. **Before creating, check you're not duplicating an existing ticket** (search
  the board you already loaded in Phase 2). A gap ticket that duplicates a real one is noise, and
  noise is the opposite of the goal.

Duplicates, obsolete tickets, and genuine gaps you're *unsure* about → don't force it. Flag them
in the report.

## Phase 5 — Greenfield the project itself

The tickets are the trees; the project is the forest. Finish by making the project readable at a
glance:

- **Description** (`save_project`) — greenfield it the same way as ticket descriptions: a clean
  statement of what this project *is* and what "done" looks like, no accumulated history. If it's
  already good, leave it.
- **State** — set the project's own state (`backlog`/`planned`/`started`/`paused`/`completed`/
  `canceled`) to match where it actually is. A project with all tickets done should not still read
  as `started`.
- **Status update** (`save_status_update`) — post one short health snapshot (`onTrack` /`atRisk`/
  `offTrack` + a few sentences): what got reconciled, what's left, what's blocked, what the next
  session should pick up first. This is the single thing a person reads to reload context cold —
  make it the honest one-paragraph state of the project.

## Phase 6 — Report

Close with a compact, skimmable report of everything you changed and everything you deliberately
didn't. Group it so the user can audit fast:

```
Linear sync — <Project Name>

Status corrected (N)
  ENG-41  Backlog → Done        merged in #218
  ENG-58  Done → In Progress    feature reverted in a1b2c3d

Content / fields (N)
  ENG-53  priority Low → High    · estimate — → 3 · description tightened
  ...

Closed (N)         ENG-60 (dup of ENG-41), ENG-72 (obsolete — approach dropped)
Reopened (N)       ENG-58 (regressed)
Created (N)        "Wire up webhook retry" (P2, est 3) — from TODO in webhook.ts:88

Project            state Started → Completed · description refreshed · status update posted

Needs a human (N)  ENG-64 — can't tell if the migration shipped; no PR references it
                   ENG-70 — looks like a dup of ENG-31 but scopes differ, left both
```

The **"Needs a human"** section is not filler — it's the honest edge of what evidence could
decide, and it's what keeps the autonomous mutations trustworthy. If it's empty, great; if it's
not, that's the skill correctly refusing to guess.

## Tools

Uses the **Linear MCP tools** — `list_teams`, `get_team`, `list_projects`, `get_project`,
`save_project`, `list_issues`, `get_issue`, `save_issue`, `list_issue_statuses`, `list_comments`,
`save_comment`, `save_status_update`, `list_project_labels`, `list_issue_labels`,
`create_issue_label`, `list_cycles`, `list_milestones` — plus git (`git log`, `git branch`) and,
where a GitHub remote exists, the GitHub tools or `gh` for PR evidence. `save_issue` both updates
existing issues and creates new ones (omit the id to create). Tool names may carry a plugin prefix
in your install (e.g. `mcp__…__save_issue`) — match by the bare method name.
