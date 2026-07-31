---
name: track-case
description: Enable tracking on a case (new or existing) in a data repo — interview + scaffold/edit the `tracking:` block and `journal.md`, then bootstrap the first digest.
---

# Track a case

Tracking is an opt-in feature of a **case** (`cases/<slug>/`), not a separate
category: a `tracking:` block in the case's README front-matter plus a
`journal.md` drive twice-daily headless syncs per `cases/RUNBOOK.md`. This
skill turns tracking on for a case — either scaffolding a brand-new case or
adding tracking to one that already exists — and seeds its first state. The
deterministic scaffold (new-case path) is `trackers new`; the reasoning
(interview + bootstrap) is yours.

## Steps

1. **Confirm the data repo and the CLI.** The repo is `repo_path` from
   `~/.claude-trackers/settings.yaml`. The CLI is `trackers`, and it does **not**
   ship with this skill — it is machine infrastructure that the twice-daily cron
   syncs also invoke, so it lives once, in the yadm dotfiles, at
   `~/.agents/plugins/trackers/scripts/trackers`. It is usually **not on PATH**:
   check with `command -v trackers` and otherwise invoke it by full path,
   `python3 ~/.agents/plugins/trackers/scripts/trackers`, for every step below.
   If neither resolves, stop — the trackers plugin isn't installed on this
   machine and nothing below will work.

2. **Decide new case vs existing case.** Ask (or infer from context) whether
   this is a brand-new matter or an already-existing case that should start
   being tracked.

3. **Interview, one question at a time:**
   - Purpose in one line, and the slug (kebab-case, English) — for an
     existing case this is just its current folder name.
   - The people/entities glossary (names, roles, handles).
   - Sources — **these are exact MCP-server names**, not friendly channel
     labels: `wacli` (WhatsApp), `imessage`, `workspace-perso` (Gmail +
     Calendar); see `cases/RUNBOOK.md` for the full source table.
   - Language (`en` default, `fr` if the whole case is French).
   - Schedule (cron; default `0 9,21 * * *`).
   - Notify topic — **default `trackers`**, and prefer it unless there's a
     real reason not to: the ntfy server is deny-all, and the publish token
     the CLI holds only has write access to the `trackers` topic. A per-slug
     or otherwise different topic silently 403s at notify time — using it
     requires first granting that topic to the token.

4. **New case:** run
   `trackers new <slug> --lang <lang> --sources <a,b> --schedule "<cron>" --notify trackers`.
   This scaffolds `cases/<slug>/README.md` (front-matter with `case:` +
   `tracking:` + empty `Summary`/`Upcoming`/`Tasks` BEGIN/END blocks + a
   `Notes` section) and `cases/<slug>/journal.md` (`last_synced: null` + a
   `sources:` cursor list, one entry per source).

5. **Existing case:** hand-edit instead of scaffolding —
   - Add a `tracking:` block (`sources`, `schedule`, `notify`) to the case's
     README front-matter, alongside its existing `case:`/`status:` keys.
   - Set (or confirm) the top-level `language:` key to the interview answer.
     Most existing cases have **no** `language:` key, which the CLI silently
     defaults to `en` — so a French case needs `language: fr` added explicitly,
     or its digests/bootstrap will be authored in English.
   - Create `cases/<slug>/journal.md` with `last_synced: null` and a
     `sources:` cursor list (one entry per source, `scope: all`,
     `last_processed: null`).
   - Make sure the README carries the `Summary`/`Upcoming`/`Tasks`/`Notes`
     BEGIN/END blocks (localized headings per the case's `language:`); add
     any that are missing without disturbing existing hand-written content.

6. **Bootstrap the first state (a 7-day scan):** following
   `cases/RUNBOOK.md`, scan each source for the last 7 days, write the
   initial `Summary`/`Upcoming`/`Tasks` digest and a first journal entry, set
   each source's `last_processed` to its last consumed message timestamp and
   the top-level `last_synced` to now. Hand-seed any still-load-bearing older
   fact (a standing arrangement, an unpaid debt) into the README once. Author
   curated content in the case's `language:`.

7. **Commit** the case (README + journal, and any other touched files) in
   the data repo.

## Guardrails

- Folder and file NAMES stay English regardless of `language:`.
- Do not invent people or facts; surface uncertainties instead.
- Money owed stays in the case's Tasks, not the repo's `payments.md`.
