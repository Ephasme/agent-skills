# Source-health traps

A source that answers is not a source that is fresh. A WhatsApp companion device was once
unlinked and the MCP server kept answering every call for **44 hours** while ingesting nothing;
three consecutive runs across two cases wrote "no new messages" from a frozen store.

The field names below are those of a WhatsApp MCP server exposing a health tool
(`whatsapp_health`); map them to whatever your server reports.

1. **`connection: "connected"` proves nothing on its own.** It is the socket's opinion of itself,
   and a half-open socket never contradicts it.
2. **Check freshness and identity every run:** `last_message_at` and `needs_pairing`.
   `needs_pairing: true`, or `connection: "logged_out"`, means the device is unlinked. A human
   must re-pair the companion device — the procedure belongs to whoever runs the server. Retrying
   never fixes it.
3. **The decisive test: if `last_message_at` equals your own cursor, the source is dead, not
   quiet.** A live but silent account still advances it. Two runs in a row at the same value is an
   outage — freeze the cursor, say so in the entry, and do not write "no new messages".
4. **Never read the age of the last connection event as freshness — it inverts the answer.** It
   measures the last connection *state change*, so a socket that stays up grows it without bound:
   a healthy server reported 42.5 h with `last_message_at` six minutes old. Large is healthy.
5. **A recovered pairing backfills.** Re-linking triggered a history sync of ~11 000 messages and
   the whole outage window came back. Do not write a window off until you have re-scanned it after
   recovery.
6. **Chat-level `last_message_ts` and `unread_count` can be phantom.** A chat reported a fresh
   timestamp and unread messages, but listing its messages returned nothing after it under every
   filter, and the phone confirmed the conversation had ended earlier. Decide "is there something
   new" from the message list (content and per-message status) only.
