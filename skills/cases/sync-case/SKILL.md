---
name: sync-case
description: Syncs a tracked case of the `me` repo from its live message sources (WhatsApp, iMessage, Gmail/Calendar) into its README digest, append-only journal and Notion rows, then commits and pushes. Use whenever Loup asks to sync, refresh, update, catch up or "mettre à jour / synchroniser / faire un run" a case — `coparenting` today, or any case whose README front-matter carries a `tracking:` block — including "what's new with Carole/the kids", "run the RUNBOOK", or "the case is N days behind". Nothing schedules runs; this skill is the only way a case gets fresh.
compatibility: >-
  Runs only inside the `me` repository (cases/, index.db, AGENTS.md, secrets.sops.yaml),
  with the whatsapp, imessage, google-perso and Notion MCP servers mounted.
---

# Sync a tracked case

A run reads every source since its cursor, turns what matters into **facts in the case** and
**work in Notion**, then commits once. It is the whole contract: there is no scheduler, no CLI,
no reconciliation tool — a run happens only because Loup asked, and he is watching.

Input: a case slug (e.g. `coparenting`). The case is `cases/<slug>/`.
Language: this file is English; write the case's curated content (README digest, journal entry)
in the case's declared `language:` (`coparenting` is `fr`).

## Before starting

- Read `cases/<slug>/README.md` and, if present, `cases/<slug>/AGENTS.md` — per-case rules win.
- Read `references/source-traps.md` now if the case uses `wacli` (WhatsApp): the door can
  answer every call while ingesting nothing, and the only honest freshness check is described there.
- The case's Notion view is linked at the top of its README; the databases are in `AGENTS.md`.

## Sources and cursors

`tracking.sources` in the README names one MCP server per door:

| source key | MCP server | read |
|---|---|---|
| `wacli` | `whatsapp` (`whatsapp_*` tools) | all chats since the cursor, via `whatsapp_messages_list`. The key stays `wacli` because renaming it would orphan committed cursors |
| `imessage` | `imessage` | `imessage_search`; on empty or timeout, fall back to `imessage_list_chats` + `imessage_history`. One empty search proves nothing |
| `workspace-perso` | `workspace-perso` | Gmail threads since the cursor, plus Calendar events for the *Upcoming* digest |

Cursors live in `cases/<slug>/journal.md` front-matter: one `last_synced`, and a `sources:` list
keyed by the exact source key, each with `last_processed`. A `null` cursor bootstraps with a
7-day lookback.

## The run, in order

1. **Pull, then read cursors.** `git pull --rebase` first — Loup's Mac pushes too. Then read the
   journal front-matter.
2. **Gate on status.** If the README front-matter `status:` is not `active`, stop and change
   nothing (archived cases are history).
3. **Fetch the delta per source.** Re-scan each source strictly after its `last_processed` with a
   small overlap window, all threads rather than a pinned subset.
4. **Health gate.** A source that will not read, or fails the freshness test in
   `references/source-traps.md`: freeze its cursor, log the outage, continue with the others.
   Never write "no new messages" from one empty or failed read.
5. **Classify** each message not yet consolidated: relevant → consolidate; irrelevant → drop,
   logged with a reason; uncertain → flag, never guess. Tag the run `RAS` / `CHANGEMENT` /
   `ACTION` / `URGENT`.
6. **Dedup by message id**, across runs and across sources. A re-seen message is a no-op, which is
   what makes a retried run safe.
7. **Act as custodian.** Leave the whole case correct, consistent and clear — you may reorganise
   anything to that end, not only the digest. Keep the `BEGIN/END` `summary` and `upcoming`
   blocks current. Create a calendar event only when time **and** place are certain, keyed by
   source message id so a retry cannot duplicate it.
8. **Append one journal entry**, newest first, directly below the front-matter, carrying the
   run's tag.
9. **Advance cursors last.** Only after the README and journal writes are persisted: each scanned
   source's `last_processed` to its max consumed timestamp, `last_synced` to now. If any
   consolidation write failed, leave the cursors — the overlap re-reads next run.
10. **Put the work in Notion.** Every action, deadline or follow-up surfaced becomes a row in the
    case's Notion view — created, updated with what you learned, or closed. The repo gets only the
    facts that back it.
11. **Keep the index current**, per `AGENTS.md` › *Keep current in the same commit*: `status`,
    `scan`, `merge` the new summaries of the touched files, `check`. Update `USER.md` if the run
    changed a fact it states.
12. **Commit and push.** README, journal, cursors and any touched file in one commit (then
    `index.db` in its own, per `AGENTS.md`), then push. On a non-fast-forward rejection,
    `git pull --rebase` and push again; if it still fails, keep the commit local and say so in the
    journal entry — the next run's pull replays it.
13. **Notify only on a real action or deadline**, by hand — see *Notify* below. A `RAS` run sends
    nothing.

## Facts in the repo, work in Notion

A run never writes a task into the repo: no checkbox, no `☐`, no numbered *Next steps* / *À faire*,
no digest or prose copy of the Notion rows. That mirror existed until 2026-08-14 and was removed
because it became a second truth that drifted. The repo states what happened, what was said, what
a document contains, what money is owed, what the custody calendar is; Notion holds the work.

- A fact that implies work: write the fact in the case **and** create the row in Notion, same run.
- Notion tools missing: that is a broken door — fix it per `AGENTS.md`, say so in the journal,
  and never fall back to a list in the repo.

## What a run may not touch

- README front-matter `case`, `status`, `tracking` — structural, owned by Loup.
- Past journal entries and their cursors — you only append one entry and advance cursors.
- The `## Notes` section — hand-edited by Loup.
- Untracked or git-ignored files: delete only what `git ls-files --error-unmatch <path>` accepts,
  because anything else is unrecoverable.

A `RAS` run (nothing actionable) leaves cursors untouched and does not churn the README.

## Notify

Only for a real action or deadline: `POST` a one-line message to
`https://ntfy.loup-peluso.com/trackers` with `Authorization: Bearer $NTFY_TOKEN`. The topic is
`trackers` for every case — the server is deny-all and the token is scoped to that one topic, so a
per-case topic returns 403. The token is in `secrets.sops.yaml` (`sops -d secrets.sops.yaml`).
Nothing alerts when a run fails, so report failures in the chat.

## References

| Read when | File |
|---|---|
| The case reads WhatsApp — before trusting any "no new messages" | `references/source-traps.md` |
| A search returns nothing, an attachment or image is involved, or you must send a Gmail attachment | `references/query-traps.md` |
