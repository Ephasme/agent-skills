# Source-health traps

A source that answers is not a source that is fresh. On 2026-07-26 the WhatsApp companion device
was unlinked; the door kept answering every call for **44 hours** while ingesting nothing, and
three consecutive runs across two cases wrote "no new messages" from a frozen store.

1. **`connection: "connected"` proves nothing on its own.** It is the socket's opinion of itself,
   and a half-open socket never contradicts it.
2. **Check freshness and identity every run, from `whatsapp_health`:** `last_message_at` and
   `needs_pairing`. `needs_pairing: true`, or `connection: "logged_out"` (which also sets
   `ok: false`), means the device is unlinked. A human must re-pair: set `WHATSAPP_PHONE_NUMBER`,
   restart the deployment, then enter the pairing code from the pod log in WhatsApp → Appareils
   connectés. Retrying never fixes it.
3. **The decisive test: if `last_message_at` equals your own cursor, the source is dead, not
   quiet.** A live but silent chat still advances it. Two runs in a row at the same value is an
   outage — freeze the cursor, say so in the entry, and do not write "no new messages".
4. **Never read `last_event_age_sec` as freshness — it inverts the answer.** It is the age of the
   last connection *state change*, so a socket that stays up grows it without bound: a healthy
   server reported 153 221 s (42.5 h) with `last_message_at` six minutes old. Large is healthy.
5. **A recovered pairing backfills.** Re-linking triggered a history sync of 11 272 messages and
   the whole 44 h window came back. Do not write a window off until you have re-scanned it after
   recovery.
6. **`whatsapp_chats_list`'s `last_message_ts` and `unread_count` can be phantom.** Found
   2026-08-16: a chat reported a fresh timestamp and `unread_count: 2`, but
   `whatsapp_messages_list` returned nothing after it under every filter, and the real WhatsApp
   Desktop app confirmed the conversation had ended earlier. About 15 unrelated chats stayed at
   `unread_count: 2` days after being read. Decide "is there something new" from
   `whatsapp_messages_list` (content and per-message `status`) only.

## Reading an older journal entry

Entries before August 2026 quote the retired `wacli doctor`. Map its fields:

| old (`wacli doctor`) | now (`whatsapp_health`) |
|---|---|
| `store.last_sync_at` | `last_message_at` |
| `authenticated: false` | `needs_pairing: true` / `connection: "logged_out"` |
| `sync_supervisor: healthy` | `connection: "connected"` |
| `linked_jid` | `self_id` |
| `connection_state: locked_by_other_process` | no equivalent — no sidecar holds a store lock any more |
