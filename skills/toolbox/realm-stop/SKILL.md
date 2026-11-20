---
name: realm-stop
description: >-
  Stops a realm started by realm-create: one realm verb closes the tabs of the
  realm's own subscribed worker panes, which ends their omp sessions,
  unsubscribes every pane of the realm's key, deletes that key's brief
  directory, pauses open subjects and retires the closed workers in realm's
  db, then reports what closed and what failed. Run by the queen. Invoked as
  `/realm-stop`.
compatibility: >-
  Requires herdr (tab list/close) and a realm launched by realm-create.
disable-model-invocation: true
---

# Realm stop

**Explicit invocation only.** It kills every worker session of the realm; never run it on a guess.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py` and `<key>` the realm's Agent Mail
project key.

## 1. Stop

`realm stop --project <key>`, from the queen's pane. It acts only on panes subscribed under `<key>`, never on
another realm sharing the workspace, and never on your own tab.

- Workers mid-subject (`agent_status` `working`): it stops with `needs` (exit 2) and lists them, closing nothing.
  Name them to the user; rerun with `--close-working` only once they confirm.
- Otherwise it closes each worker tab, checks with `herdr tab list` that each one is gone, unsubscribes every
  pane of `<key>` (worker wakes and your mail aside), deletes `<key>`'s brief directory, sets open subjects to
  `paused` and retires the closed workers in the db. A close that failed or a tab still open is in `failed`,
  never retried blindly.

The launchd service stays installed (other realms may use it). Agent Mail keeps the workers registered and their
history readable. Your own tab keeps its `👑 queen` label.

## 2. Report

One line per tab from `closed` and `failed` (label, closed or failed with its error). Then the panes in
`unsubscribed`, and `briefs_deleted`.
