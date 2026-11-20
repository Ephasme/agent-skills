---
name: realm-stop
description: >-
  Stops a realm started by realm-create: lists the worker tabs of the current
  herdr workspace (label prefix `🛠️ subject-`), closes each one, which ends
  its omp session, deletes the brief directory, and reports what closed and
  what failed. Run by the queen. Invoked as `/realm-stop`.
compatibility: >-
  Requires herdr (tab list/close, agent list) and a realm launched by
  realm-create in the current herdr workspace.
disable-model-invocation: true
---

# Realm stop

**Explicit invocation only.** It kills every worker session of the realm; never run it on a guess.

## 1. List what will close

`herdr tab list --workspace "$HERDR_WORKSPACE_ID"`. The realm's tabs are those whose `label` starts with
`🛠️ subject-`: the prefix realm-create sets. Never pick a tab by any other sign, and never your own tab
(`$HERDR_TAB_ID`): closing it kills the session running this skill.

None found: say so and stop. Otherwise show the list — label, `tab_id`, `agent_status` — before closing anything.

## 2. Close each tab

A tab whose `agent_status` is `working` is mid-subject: name it to the user and close it only once they confirm.
The others: `herdr tab close <tab_id>`. herdr has no command to stop an agent first; closing the tab ends the pane
and the omp session in it.

Then `herdr tab list` again: every listed tab must be gone. One still there or a close that errored is a failure,
reported, never retried blindly.

## 3. Clean up

- `python3 ~/.agents/skills/realm-create/scripts/realm.py unsubscribe --project <key>`, `<key>` being the realm's
  Agent Mail project: stops the mail nudges to your pane and the workers'. Leave the launchd service installed;
  other realms may use it.
- Delete `${TMPDIR:-/tmp}/swarm/`, the briefs realm-create wrote.
- Your own tab keeps its `👑 queen` label; nothing renames it.
- Agent Mail: leave the workers registered. `retire_agent` keeps message history but needs each worker's
  `registration_token`, which realm-create does not keep.

## 4. Report

One line per tab: label, closed or failed (with herdr's error). Then the panes `realm unsubscribe` dropped, and
whether `${TMPDIR:-/tmp}/swarm/` was deleted.
