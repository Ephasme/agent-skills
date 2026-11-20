---
name: realm-stop
description: >-
  Stops a realm started by realm-create: one realm verb closes the own
  workspaces (tabs, for older workers) of the realm's subscribed worker panes, which ends their omp sessions,
  unsubscribes every pane of the realm's key, deletes that key's brief
  directory, pauses open subjects and retires the closed workers in realm's
  db, then reports what closed and what failed. Run by the queen. Invoked as
  `/realm-stop [KEY|NAME]`.
compatibility: >-
  Requires herdr (workspace and tab list/close) and a realm launched by realm-create.
disable-model-invocation: true
---

# Realm stop

**Explicit invocation only.** It kills every worker session of the realm; never run it on a guess.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py` and `<realm>` this realm's Agent Mail
project key or its name (`realm realms` lists both).

## 1. Stop

`realm stop --project <realm>`, from the queen's pane. It acts only on panes subscribed under that realm's key,
never on another realm sharing a workspace, never on your own tab, and never on a workspace labelled `👑`.

- Workers mid-subject (`agent_status` `working`): it stops with `needs` (exit 2) and lists them, closing nothing.
  Name them to the user; rerun with `--close-working` only once they confirm.
- Otherwise it closes each worker's own workspace (the db records it; a worker older than workspaces has its tab
  closed instead), checks with `herdr workspace list` / `herdr tab list` that each one is gone, unsubscribes every
  pane of the key (worker wakes and your mail aside), deletes its brief directory, sets open subjects to
  `paused` and retires the closed workers in the db. A close that failed or a workspace or tab still open is in
  `failed`, never retried blindly.

The launchd service stays installed (other realms may use it). Agent Mail keeps the workers registered and their
history readable. Your own tab keeps its `👑 queen` label, your workspace its `👑`.

## 2. Report

One line per entry of `closed` and `failed` (agent, its `workspace` or `tab`, closed or failed with its error).
Then the panes in `unsubscribed`, and `briefs_deleted`.
