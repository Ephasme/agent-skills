---
name: realm-restart
description: >-
  Makes the current session the queen of a realm that is already running:
  reloads realm-create's queen instructions, resumes the old queen's Agent
  Mail identity by name, re-subscribes this pane to realm in aside mode,
  re-injects the current brief into each worker once it is idle, rebuilds the
  subject table from mail, then runs the queen loop. Use after the queen's omp
  session died or when continuing a live realm from a new session. Invoked as
  `/realm-restart KEY`, e.g. `/realm-restart /laptop/general`.
compatibility: >-
  Requires a realm started by realm-create (its realm.py and launchd service),
  herdr, and an Agent Mail MCP server named agent-mail-perso exposing
  macro_start_session, list_agents, search_messages and fetch_topic.
disable-model-invocation: true
---

# Realm restart

**Explicit invocation only.** It takes over a live realm's queen identity; never run it on a guess.

**ABSOLUTE RULE: only the user sends prompts into the queen's pane** (realm-create, top of file). The one place this
skill types into a pane is step 6, into worker panes only.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`, and "realm-create" is
`~/.agents/skills/realm-create/SKILL.md`.

Argument: `<key>`, the realm's Agent Mail project key. Missing: run `realm list`, show the distinct projects it
lists with their panes, ask which one, start nothing.

## 1. Mark this tab

First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "👑 queen"`. realm's guard refuses to type into a
pane whose tab label holds `👑`; step 5 subscribes this pane, so the label must be there before it.

## 2. Load the queen's instructions

Read realm-create in full now, every section from the absolute rule to "Ending the swarm", including the brief
template. It is the current version of everything this session must do as queen; a pointer to it is not enough.

## 3. Resume the old queen

`list_agents` on `<key>`: the queen is the agent whose `task_description` is `Swarm queen`. None, or several: show
the candidates (name, `last_active_ts`) and ask.

`macro_start_session` with `human_key: <key>`, `agent_name: <QUEEN>`, `program: "omp"`, your model,
`task_description: "Swarm queen"`. Reconnecting by name is safe: it returns the same agent, its threads and its
unread inbox; a new name would orphan them. Keep the returned inbox for step 7.

If the old queen's session may still be alive (recent `last_active_ts`, a `👑` tab other than yours in
`herdr tab list`), say so and ask before resuming: two sessions reading one inbox lose replies.

## 4. Rebuild the worker map

- `realm list`: the rows for `<key>` give pane → agent, mode and last wake.
- `herdr tab list --workspace "$HERDR_WORKSPACE_ID"` and `herdr pane get <pane>`: each `🛠️ subject-*` tab, its
  pane, `agent` and `agent_status`.

## 5. Re-subscribe this pane

The old queen's row in `realm list` has a pane id. If it differs from `$HERDR_PANE_ID`:
`realm unsubscribe <old pane>`. Then `realm subscribe "$HERDR_PANE_ID" --agent <QUEEN> --project <key> --aside`,
and check `realm list` shows it in `aside` mode.

## 6. Re-inject each worker's brief

Workers launched under an older realm-create run an older brief. For each worker `W` (`w` its kebab-case form):

1. Write `${TMPDIR:-/tmp}/swarm/<w>.md` from the brief template you read in step 2, placeholders filled, replacing
   any old file. The brief reconnects by the same name, so the worker keeps its inbox and its subjects.
2. Deliver it according to the pane:
   - `agent` is `omp`, `agent_status` `idle` or `done`: `herdr pane send-text <pane> "Re-read @<path>: it replaces
     your previous brief. Follow it from now on, keep your current subject."`, then `herdr pane send-keys <pane>
     enter`. omp expands `@<path>` in an interactive prompt and reads the file.
   - `working` or `blocked`: send nothing now; mark it `brief pending`. On each later turn, `herdr pane get` it again
     and inject once it is `idle` or `done`. Interrupting would cut its current subject.
   - no agent in the pane (plain shell): `herdr pane run <pane> "omp @<path>"`, as realm-create "Launch one tab per
     worker".
   - pane gone: report it; relaunch per realm-create "Launch one tab per worker" under the same name, or drop it
     (`realm unsubscribe <pane>`), only on the user's word.
3. Confirm each re-injected worker answered: `herdr pane read <pane>` shows it read the file.

## 7. Rebuild the subject table

1. The queen's subjects: `search_messages` on `<key>` with `sender: <QUEEN>`, `limit: 1000`, and a query of common
   words such as `a OR the OR to` (a bare `*` matches nothing). Keep messages with a `topic` and a `[<slug>]`
   subject; `topic` is the slug, the first recipient is the worker.
2. Per slug, `fetch_topic` (`include_bodies: true`) and sort by `created_ts`. The last message sets the state:
   - from the queen, body starting `queued:` → `queued`; any other queen message → `assigned`;
   - from the worker → `done`, or `blocked` when it asks a question or names a blocker.
3. A `queued` subject whose worker's pane is `working` after the previous subject's reply is `assigned`, per the
   subject-table rule in realm-create "Be the queen".

Show the table: slug, worker, pane, state, time of the last message, and `brief pending` where step 6 deferred.
Unread mail from step 3's inbox goes beside it.

## 8. Be the queen

Act as realm-create "Be the queen" and every section after it, which you read in step 2, with this `QUEEN`, this
pane and the table above. Each turn, first re-inject any `brief pending` worker that has gone idle.
