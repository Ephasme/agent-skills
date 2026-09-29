---
name: sync-case
description: Syncs a tracked case in a case-archive repository — a repo with one folder per case under `cases/`, whose README front-matter carries a `tracking:` block and whose `journal.md` holds per-source cursors — from its live message sources (WhatsApp, iMessage, email, calendar, reached through MCP servers) into the case's README digest, append-only journal and the task tracker the repository declares, then commits and pushes. Use whenever the user asks to sync, refresh, update or catch up a case, "mettre à jour / synchroniser / faire un run", asks what is new in a tracked matter, or says a case is N days behind. Nothing schedules runs; this skill is how a tracked case gets fresh.
compatibility: >-
  Needs a git repository laid out as described in the skill (a case README with a tracking:
  front-matter block, a journal.md with cursors), an MCP server for each
  source the case names, and the task-tracker MCP server the repository's instructions declare.
---

# Sync a tracked case

A run reads every source since its cursor, turns what matters into **facts in the case** and
**work in the task tracker**, then commits once. It is the whole contract: there is no scheduler,
no CLI, no reconciliation tool — a run happens because the user asked, and they are watching.

Input: a case slug. The case is `cases/<slug>/`. This file is English; write the case's curated
content (README digest, journal entry) in the case's declared `language:` (default `en`).

## The repository contract

The skill assumes this layout and reads everything else from the repository itself.

**`cases/<slug>/README.md`** front-matter:

```yaml
case: <slug>
status: active            # anything else: the case is history, do not sync
language: en              # language of the curated content
persistent: false         # true = a standing matter that is never archived
tracking:
  sources: [<source-key>, ...]   # one key per message source
  notify: <channel>              # optional; where a real action or deadline is announced
```

Its body holds two machine-managed blocks, `<!-- BEGIN:summary -->…<!-- END:summary -->` and
`<!-- BEGIN:upcoming -->…<!-- END:upcoming -->`, and a hand-edited `## Notes` section.

**`cases/<slug>/journal.md`**: append-only, newest entry first, directly below a front-matter
that holds the cursors:

```yaml
last_synced: <ISO-8601 timestamp or null>
sources:
  - source: <source-key>
    last_processed: <ISO-8601 timestamp or null>
```

**The repository's agent instructions** (`AGENTS.md`, `CLAUDE.md`, `GEMINI.md`,
`.cursor/rules` — read whichever exist, and a nested `cases/<slug>/AGENTS.md`, which wins)
declare what this skill cannot know:

- which MCP server answers each source key, when the key is not the server's own name;
- the task tracker (database, view, fields) that holds the case's work;
- how to notify, and where its credential lives;
- any index or derived file that must stay current in the same commit.

What the instructions do not declare, ask once and suggest the user write it down there.

## Before starting

- Read the repository instructions, then `cases/<slug>/README.md` — per-case rules win.
- Read `references/source-traps.md` now if a source is WhatsApp: the door can answer every call
  while ingesting nothing, and the only honest freshness check is described there.
- Open the case's view in the task tracker; a missing tracker door is a blocker (see below).

## Sources

Each key in `tracking.sources` names one MCP server. Typical doors:

| source | read |
|---|---|
| WhatsApp | all chats since the cursor, by listing messages — never by trusting chat-level counters |
| iMessage | full-text search; on empty or timeout, fall back to listing chats plus per-chat history. One empty search proves nothing |
| email + calendar | threads since the cursor, plus calendar events for the *Upcoming* digest |

A source key is written into committed cursors, so it never changes once used — even when the
server behind it is replaced, map the old key to the new server in the repository instructions.
A `null` cursor bootstraps with a 7-day lookback.

## The run, in order

1. **Pull, then read cursors.** `git pull --rebase` first — other machines push too. Then read the
   journal front-matter.
2. **Gate on status.** If README `status:` is not `active`, stop and change nothing.
3. **Fetch the delta per source.** Re-scan each source strictly after its `last_processed` with a
   small overlap window, all threads rather than a pinned subset.
4. **Health gate.** A source that will not read, or fails its freshness test
   (`references/source-traps.md`): freeze its cursor, log the outage, continue with the others.
   Never write "no new messages" from one empty or failed read.
5. **Classify** each message not yet consolidated: relevant → consolidate; irrelevant → drop,
   logged with a reason; uncertain → flag, never guess. Tag the run `RAS` (nothing to report) /
   `CHANGE` / `ACTION` / `URGENT` — or the repository's own tag set, if it declares one.
6. **Dedup by message id**, across runs and across sources. A re-seen message is a no-op, which is
   what makes a retried run safe.
7. **Act as custodian.** Leave the whole case correct, consistent and clear — you may reorganise
   anything to that end, not only the digest. Keep the `summary` and `upcoming` blocks current.
   Create a calendar event only when time **and** place are certain, keyed by source message id so
   a retry cannot duplicate it.
8. **Append one journal entry**, newest first, directly below the front-matter, carrying the
   run's tag.
9. **Advance cursors last.** Only after the README and journal writes are persisted: each scanned
   source's `last_processed` to its max consumed timestamp, `last_synced` to now. If any
   consolidation write failed, leave the cursors — the overlap re-reads next run.
10. **Put the work in the task tracker.** Every action, deadline or follow-up surfaced becomes an
    item in the case's view — created, updated with what you learned, or closed. The repository
    gets only the facts that back it.
11. **Keep derived files current**, as the repository instructions require (an index, a profile
    of the owner, a payments ledger).
12. **Commit and push.** README, journal, cursors and any touched file in one commit, then push.
    On a non-fast-forward rejection, `git pull --rebase` and push again; if it still fails, keep
    the commit local and say so in the journal entry — the next run's pull replays it.
13. **Notify only on a real action or deadline**, through the channel the case's `notify:` names
    and the repository instructions describe. A `RAS` run sends nothing. Nothing alerts when a run
    fails, so report failures in the chat.

## Facts in the repository, work in the tracker

A run never writes a task into the repository: no checkbox, no `☐`, no numbered *Next steps*, no
digest or prose copy of the tracker's items. A mirror of the work inside the repository becomes a
second truth that drifts. The repository states what happened, what was said, what a document
contains, what money is owed; the tracker holds the work.

- A fact that implies work: write the fact in the case **and** create the item in the tracker,
  same run.
- Tracker tools missing: that is a broken door — get it reconnected, say so in the journal, and
  never fall back to a list in the repository.

## What a run may not touch

- README front-matter `case`, `status`, `tracking` — structural, owned by the user.
- Past journal entries and their cursors — you only append one entry and advance cursors.
- The `## Notes` section — hand-edited by the user.
- Untracked or git-ignored files: delete only what `git ls-files --error-unmatch <path>` accepts,
  because anything else is unrecoverable.

A `RAS` run leaves cursors untouched and does not churn the README.

## References

| Read when | File |
|---|---|
| A source is WhatsApp — before trusting any "no new messages" | `references/source-traps.md` |
| A search returns nothing, an attachment or image is involved, or you must send an email attachment | `references/query-traps.md` |
