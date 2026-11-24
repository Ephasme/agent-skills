---
name: realm-restart
description: >-
  Makes the current session the queen of a realm that is already running:
  reloads realm-create's queen instructions, then one realm verb resumes the
  old queen's raven identity by name, binds this pane to it, re-mails
  each worker its rewritten brief, and reloads the subject table from realm's
  SQLite db; then runs the queen loop. Use after the queen's omp session died
  or when continuing a live realm from a new session.
  Invoked as `/realm-restart KEY|NAME`, e.g. `/realm-restart "secret garden"`.
compatibility: >-
  Runs inside the realm container, on a realm started by realm-create: the `realm` CLI on PATH, herdr, and
  raven reachable from realm (`RAVEN_URL` and its admin token in realm's secret store).
disable-model-invocation: true
---

# Realm restart

**Explicit invocation only.** It takes over a live realm's queen identity; never run it on a guess.

**ABSOLUTE RULE: nothing types into any pane, the queen's above all** (realm-create, top of file). This skill
types into nothing, and it wakes nobody: a changed brief waits as a notice the next dispatch or wake carries.

**ABSOLUTE RULE: workers never ask the user anything directly** (realm-create, top of file). The briefs this
restart rewrites carry it.

**ABSOLUTE RULE: the queen never does real work herself** (realm-create, top of file). Real work goes to a
worker; the boundary is that file's two lists. Never an edit in any worktree, never a suite or a formatter
inside a worker's worktree, never finishing, rebasing or resolving a conflict on a worker's branch. A stalled
worker is rebriefed smaller, reassigned or replaced (realm-create, "A worker that stalls"), never done by this
session.

Below, `realm` is the realm CLI on the container's PATH, and "realm-create" is
`~/.agents/skills/realm-create/SKILL.md`.

Argument: `<realm>`, the realm's project key (starts with `/`) or its name. Missing: `realm realms`
lists each realm's key and name, `realm status --project <key>` its panes; show them, ask which one, start
nothing.

## 1. Load the queen's instructions

Read realm-create in full now, every section from the absolute rules to "Ending the swarm". It is the current
version of everything this session must do as queen; a pointer to it is not enough.

## 2. Take over

`realm restart --project <realm> --model <your model>`, from this pane (any directory: it refuses, before
anything else, unless the realm repository `spare-cycles/realm` is at `~/code/perso/realm` or `$REALM_REPO`,
and records it as the directory every worker starts in). It:

- labels this tab `👑 queen · <name>` and puts `👑` in front of this workspace's label;
- picks the queen: the one the db records, else the single `Swarm queen` agent in raven;
- stops with `needs` (exit 2) when the old queen may still be running (another `👑` tab in this workspace): two
  sessions reading one inbox lose replies. Show the user what it found and ask; rerun with `--force` only on
  their word. Several or no queen candidates: `needs` lists them;
  ask, rerun with `--queen <name>`;
- resumes the queen by name (same agent, threads and unread inbox), binds this pane to her, and records this
  pane in the db;
- rewrites every agent's brief from the current template and wakes nobody for it: a changed brief waits as a
  notice that a worker's next dispatch, or the foreman's next `[pass]`, opens with (`pending` lists them). A pane
  with no agent gets `omp @<brief>` started now (`started`); an agent whose pane is gone is listed in `pane_gone`;
- syncs from mail and returns the table.

Keep `queen`: that is `QUEEN`. Show `table`, with `pending` and `started` names beside it and `inbox` (unread
mail) after it. Each `pane_gone` worker: report it; relaunch (`realm spawn`) or retire it (`realm retire`) only
on the user's word.

When `realm worker list --project <realm> --all` is empty after the restart (no live worker, no db rows), the
realm has no workers left: say so; `realm spawn` adds them on the user's word.

## 3. Be the queen

Act as realm-create "Be the queen" and every section after it, which you read in step 1, with this `QUEEN`, this
pane and the db. `realm status --project <realm>` shows each pane and whether it is bound.
