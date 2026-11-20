---
name: realm-restart
description: >-
  Makes the current session the queen of a realm that is already running:
  reloads realm-create's queen instructions, then one realm verb resumes the
  old queen's Agent Mail identity by name, moves the mail aside to this pane,
  rewrites each worker's brief for delivery once it is idle, and reloads the
  subject table from realm's SQLite db; then runs the queen loop. Use after the
  queen's omp session died or when continuing a live realm from a new session.
  Invoked as `/realm-restart KEY|NAME`, e.g. `/realm-restart "secret garden"`.
compatibility: >-
  Requires a realm started by realm-create (its realm.py and launchd service),
  herdr, and an Agent Mail MCP server named agent-mail-perso exposing
  macro_start_session, list_agents and fetch_topic.
disable-model-invocation: true
---

# Realm restart

**Explicit invocation only.** It takes over a live realm's queen identity; never run it on a guess.

**ABSOLUTE RULE: only the user sends prompts into the queen's pane** (realm-create, top of file). This skill
types into nothing: brief delivery to workers is realm's launchd job, into worker panes only.

**ABSOLUTE RULE: workers never ask the user anything directly** (realm-create, top of file). The briefs this
restart rewrites carry it.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`, and "realm-create" is
`~/.agents/skills/realm-create/SKILL.md`.

Argument: `<realm>`, the realm's Agent Mail project key (starts with `/`) or its name. Missing: `realm realms`
lists each realm's key and name, `realm list` the subscribed panes per project; show them, ask which one, start
nothing.

## 1. Load the queen's instructions

Read realm-create in full now, every section from the absolute rules to "Ending the swarm". It is the current
version of everything this session must do as queen; a pointer to it is not enough.

## 2. Take over

`realm restart --project <realm> --model <your model>`, from this pane. It:

- labels this tab `👑 queen · <name>` (realm's guard then refuses to type into it), and puts `👑` in front of this
  workspace's label unless worker tabs still live in it (`queen_workspace` says which);
- picks the queen: the one the db records, else the single `Swarm queen` agent in Agent Mail;
- stops with `needs` (exit 2) when the old queen may still be running (another `👑` tab in this workspace, or
  Agent Mail activity in the last 5 min): two sessions reading one inbox lose replies. Show the user what it
  found and ask; rerun with `--force` only on their word. Several or no queen candidates: `needs` lists them;
  ask, rerun with `--queen <name>`;
- resumes the queen by name (same agent, threads and unread inbox), moves the aside subscription to this pane,
  and records this pane in the db;
- adopts worker panes realm already wakes that the db does not know yet (a realm older than the db): a pane in a
  `🛠️` workspace of its own is recorded with that workspace, any other with its tab;
- rewrites every worker's brief from the current template (a worker recorded with a tab relabels that tab, never
  the workspace it shares with you). omp workers get it delivered by realm's launchd job
  once their pane is idle (`brief_pending` until then); a pane with no agent gets `omp @<brief>` started now; a
  gone pane is listed in `pane_gone`;
- syncs from mail and returns the table.

Keep `queen`: that is `QUEEN`. Show `table`, with `brief_pending` names beside it and `inbox` (unread mail) after
it. Each `pane_gone` worker: report it; relaunch (`realm spawn`) or retire it (`realm retire`) only on the
user's word.

When `realm worker list --project <realm> --all` is empty after the restart (no subscribed worker panes, no db
rows), the realm has no workers left: say so; `realm spawn` adds them on the user's word.

## 3. Be the queen

Act as realm-create "Be the queen" and every section after it, which you read in step 1, with this `QUEEN`, this
pane and the db. `realm status --project <realm>` shows which briefs are still pending delivery.
