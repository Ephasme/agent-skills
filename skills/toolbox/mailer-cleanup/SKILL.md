---
name: mailer-cleanup
description: >-
  Unclutters a Gmail mailbox through the google-workspace MCP: profiles senders,
  creates labels and filters that skip the inbox, applies them to existing mail,
  sorts the long tail with a classifier, archives mail older than a year, prunes
  empty labels. Use when the user asks to clean, unclutter, declutter or triage
  their inbox or mailbox, add Gmail filters, reorganize Gmail labels, or in French
  "nettoie ma boîte mail", "range mes mails", "désencombre ma boîte". Archives
  and relabels only; never deletes mail.
---

# Mailer cleanup

Goal: an inbox that holds only mail from people that needs the user's attention. Every machine
sender goes to a label and skips the inbox. Archiving is reversible; deleting mail is out of
scope — never trash or delete a message.

Tools: `xd://mcp__google_workspace_*` (or `google_perso_*` for the personal account; ask
which mailbox only if the user didn't say "work"/"perso"). Drive them from a Python `eval` with
`await tool.write({"path": "xd://mcp__google_workspace_<tool>", "content": json.dumps(args)})`;
the result is a dict, the text is under `["text"]`.

## Gmail API traps (each one cost a wrong report before)

- **Search returns 100 results per page.** A count read from one `search_gmail_messages` page
  is never the mailbox size. For true counts use
  `manage_gmail_filter {action: "apply", criteria: {query}, filter_action: {removeLabelIds:
  ["INBOX"]}, dry_run: true}` — it reports `Matching messages: N`. Never report "N left in
  inbox" from a search page.
- **Quota: "Units per minute per user".** `include_headers: true` costs one read per result.
  Pace paged searches ~12 s apart; on `Quota exceeded` sleep 60 s and retry once.
- **Message IDs parsed from search text can carry a trailing literal `\n`.** Normalise with
  `re.match(r"[0-9a-f]{16}", id)` before `batch_modify_gmail_message_labels`, which otherwise
  fails the whole batch with `Invalid ids value`.
- **`Archive` is a reserved label name** (400 `Invalid label name`). Use `Archives`.
- **`update` on a filter recreates it with a new ID.** Store the returned `New filter ID`.
- **`list_gmail_filters` output contains each filter twice** (text + JSON). Split on the
  part before the first ```` ``` ```` before counting.
- **`apply` on thousands of messages can hit the 30 s MCP timeout yet finish server-side.**
  Re-run with a `-label:<target>` query to confirm 0 remain instead of re-applying blindly.
  Cap each run with `max_messages` (≤2000) and loop until `Applied to 0`.
- **Filters only act on new mail.** Every created filter must be followed by `apply`
  (dry-run first for the count).
- Label queries: `label:"[Notion]"` and `label:[notion]-priority-x-to-do` both work; slashes in
  nested names become `-`. A label is empty only when its sub-labels are empty too.

## Workflow

1. **Inventory.** `list_gmail_filters`, `list_gmail_labels`. Keep existing filters (forwards,
   automations) untouched.
2. **Measure the real inbox** with dry-run counts: `in:inbox`, `in:inbox is:unread`,
   `in:inbox older_than:30d`, `in:inbox from:<top sender>`, `in:inbox category:updates`.
3. **Profile senders** over the whole inbox, paging until no `page_token` (pace for quota):
   count by address, keep 2 sample subjects each. The head is usually GitHub, calendar,
   SaaS notifications, newsletters, alerts.
4. **Create labels** — one flat level per topic first, nest later: `GitHub`, `GitHub/CI`,
   `Calendar`, `Newsletters`, `Social`, `Notifications`, `Alerts`, `Security`, `Finance`,
   `Receipts`, `Apple`, `Support`, `People`, `Archives` — only those the profile justifies.
5. **Create filters** (label + `removeLabelIds: ["INBOX"]`; add `"UNREAD"` only for pure noise
   like CI runs, RSVPs, newsletters, promotions, auto-replies). Patterns that held:
   - `from:notifications@github.com` → `GitHub`, archive. Default: all of it, mentions and
     review requests included — the user wanted none in the inbox. CI separately:
     `to:ci_activity@noreply.github.com` → `GitHub/CI`, archive, read.
   - Calendar: `filename:invite.ics subject:(Accepted OR Declined OR Accepté OR Refusé OR
     Canceled OR Annulé OR "Updated invitation")`, `filename:invite.ics subject:Invitation`,
     `from:calendar-notification@google.com`.
   - `category:promotions`, `category:social` → archive, read.
   - Shared group inboxes (e.g. `support@`): match `from:X OR to:X OR list:X.domain` —
     group mail arrives from third parties, so `from:` alone misses it.
   - Monitoring: archive `RESOLVED`, keep `FIRING` in the inbox.
   - Security senders (`no-reply@accounts.google.com`, `accounts@1password.com`,
     `noreply@github.com`, Notion login notices) → `Security`, archive but leave unread.
   Then `apply` each (dry-run → real).
6. **Re-measure the inbox; repeat 3–5** on what remains until the tail is mostly humans.
7. **Sweep stale mail** the filters didn't cover: `in:inbox older_than:30d -is:starred` →
   archive under a temporary dated label so it can be undone.
8. **Sort the temporary label into topics.** Messages already carrying a topic label just
   drop the temp label. For the rest, collect `{id, from, subject}` and run `judge_batch` with
   a `choice` question over the topic labels (`People` = a real person writing; cold sales
   posing as personal = `Newsletters`). `judge_batch` returns a `JudgmentBatch`: poll
   `.status()` until `running` is false, then `.results()`. Spot-check the top senders per
   label, then `batch_modify_gmail_message_labels` in chunks of 500 (`verify: false`).
   Delete the temp label once `label:<temp>` counts 0.
9. **Archive mail older than a year:** `older_than:1y -in:sent -in:chats -in:trash -in:spam` →
   add `Archives`, remove `INBOX` and the topic labels.
10. **Prune and nest.** Delete labels whose dry-run count is 0 (check sub-labels and that no
    filter references the ID). Nest small labels under a parent (`Finance/Receipts`,
    `Notifications/Security`, `Notifications/Alerts`, `Newsletters/Social`) — filters
    reference label IDs, so renames don't break them.

## Report

Table of filters/actions with the count each changed, the before/after inbox count (from
dry-run, not search pages), the label tree with counts, and the risks the user must know:
anything important now skipping the inbox (security alerts, mentions, new invitations,
crash alerts), one-off sweeps that no filter repeats, labels no filter feeds (`People`,
`Archives`), and the undo path (Settings → Filters; select the label → Move to Inbox).
