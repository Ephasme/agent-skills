---
name: realm-restart
description: >-
  Makes the current session the queen of a realm that is already running:
  resumes the old queen's Agent Mail identity by name, re-subscribes this pane
  to realm in aside mode, rebuilds the worker map from realm and herdr and the
  subject table from mail, then runs realm-create's queen loop. Use after the
  queen's omp session died or when continuing a live realm from a new session.
  Invoked as `/realm-restart KEY`, e.g. `/realm-restart /laptop/general`.
compatibility: >-
  Requires a realm started by realm-create (its realm.py and launchd service),
  herdr, and an Agent Mail MCP server named agent-mail-perso exposing
  macro_start_session, list_agents, search_messages and fetch_topic.
disable-model-invocation: true
---

# Realm restart

**Explicit invocation only.** It takes over a live realm's queen identity; never run it on a guess.

**ABSOLUTE RULE: only the user sends prompts into the queen's pane** (realm-create, top of file). Never type into
any pane while restarting: herdr is used here only to read, and to rename your own tab.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`, and "realm-create" is
`~/.agents/skills/realm-create/SKILL.md`.

Argument: `<key>`, the realm's Agent Mail project key. Missing: run `realm list`, show the distinct projects it
lists with their panes, ask which one, start nothing.

## 1. Mark this tab

First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "👑 queen"`. realm's guard refuses to type into a
pane whose tab label holds `👑`; step 4 subscribes this pane, so the label must be there before it.

## 2. Resume the old queen

`list_agents` on `<key>`: the queen is the agent whose `task_description` is `Swarm queen`. None, or several: show
the candidates (name, `last_active_ts`) and ask.

`macro_start_session` with `human_key: <key>`, `agent_name: <QUEEN>`, `program: "omp"`, your model,
`task_description: "Swarm queen"`. Reusing the name keeps the subject threads and the inbox; a new name would orphan
them. Keep the returned inbox for step 5.

If the old queen's session may still be alive (recent `last_active_ts`, a `👑` tab other than yours in
`herdr tab list`), say so and ask before resuming: two sessions reading one inbox lose replies.

## 3. Rebuild the worker map

- `realm list`: the rows for `<key>` give pane → agent, mode and last wake.
- `herdr tab list --workspace "$HERDR_WORKSPACE_ID"` and `herdr pane get <pane>`: each `🛠️ subject-*` tab, its
  pane and `agent_status`.

A worker whose pane is gone, or whose pane runs no agent: report it with its name, and offer to drop it
(`realm unsubscribe <pane>`) or relaunch it with realm-create step 3 under the same name. Do either only on the
user's word.

## 4. Re-subscribe this pane

The old queen's row in `realm list` has a pane id. If it differs from `$HERDR_PANE_ID`:
`realm unsubscribe <old pane>`. Then `realm subscribe "$HERDR_PANE_ID" --agent <QUEEN> --project <key> --aside`,
and check `realm list` shows it in `aside` mode.

## 5. Rebuild the subject table

1. The queen's subjects: `search_messages` on `<key>` with `sender: <QUEEN>`, `limit: 1000`, and a query of common
   words such as `a OR the OR to` (a bare `*` matches nothing). Keep messages with a `topic` and a `[<slug>]`
   subject; `topic` is the slug, the first recipient is the worker.
2. Per slug, `fetch_topic` (`include_bodies: true`) and sort by `created_ts`. The last message sets the state:
   - from the queen, body starting `queued:` → `queued`; any other queen message → `assigned`;
   - from the worker → `done`, or `blocked` when it asks a question or names a blocker.
3. A `queued` subject whose worker's pane is `working` after the previous subject's reply is `assigned`, as in
   realm-create step 4.5.

Show the table: slug, worker, pane, state, time of the last message. Unread mail from step 2's inbox goes beside it.

## 6. Be the queen

Follow realm-create from "4. Be the queen" on, including "Scaling the realm" and "Ending the swarm", with this
`QUEEN`, this pane and the table above.
