---
name: realm-stop
description: >-
  Stops a realm started by realm-create: one realm verb closes each of the
  realm's worker workspaces, which ends their omp sessions, removes every bind
  file of the realm's key, deletes that key's brief directory, pauses open
  subjects and retires the closed workers in realm's db, then reports what
  closed and what failed. Run by the queen. Invoked as `/realm-stop [KEY|NAME]`.
compatibility: >-
  Runs inside the realm container, on a realm launched by realm-create: the `realm` CLI on PATH and herdr
  (workspace list/close).
disable-model-invocation: true
---

# Realm stop

**Explicit invocation only.** It kills every worker session of the realm; never run it on a guess.

Below, `realm` is the realm CLI on the container's PATH and `<realm>` this realm's Agent Mail
project key or its name (`realm realms` lists both).

## 1. Stop

`realm stop --project <realm>`, from the queen's pane. It acts only on that realm's recorded workers, never on
another realm, never on your own pane, and never on a workspace labelled `👑`.

- Workers mid-subject (`agent_status` `working`): it stops with `needs` (exit 2) and lists them, closing nothing.
  Name them to the user; rerun with `--close-working` only once they confirm.
- Otherwise it closes each worker's own workspace, checks with `herdr workspace list` that each one is gone,
  removes every bind file of the key (workers, scout and your own, so nothing wakes on its mail any more),
  deletes its brief directory, sets open subjects to `paused` and retires the closed workers in the db. A close
  that failed or a workspace still open is in `failed`, never retried blindly.

Agent Mail keeps the workers registered and their history readable. Your own tab keeps its `👑 queen` label,
your workspace its `👑`.

## 2. Report

One line per entry of `closed` and `failed` (agent, its `workspace`, closed or failed with its error).
Then the panes in `unbound`, and `briefs_deleted`.
