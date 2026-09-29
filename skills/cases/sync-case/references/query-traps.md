# Query traps

## Multi-term full-text search returns nothing

`whatsapp_messages_search` with `frigo OR série OR parachut` returned zero over a window that
provably contained "J'envoie le mail à Parachut"; the single term `parachut` found it at once.
Search **one term at a time**, and corroborate with a plain `whatsapp_messages_list` over the
window. Treat any past "search returned nothing" as weak evidence.

## Images arrive as text in omp

`whatsapp_download_media` succeeds and returns a valid MCP image block, but omp flattens every
MCP result to text, so the model sees only `[Image: image/jpeg]`. No setting changes it. Full
diagnosis: `_dev/reports/2026-08-05-omp-mcp-image-blocks-dropped.md`.

Recover the bytes locally first — they survive inline in the session log:

```bash
mcp-image-fetch from-session --match <message-id> \
    -o cases/<case>/documents/<name>     # writes <name>.jpg
```

If the attachment was never fetched in any session, or the tool reports `status: "truncated"`,
re-fetch it live:

```bash
mcp-image-fetch call --server whatsapp \
    --tool whatsapp_download_media \
    --args '{"chat":"<jid>","message_id":"<id>"}' -o <path>
```

Then `read` the written file to actually see it. Do not log "media locked", do not ask a human to
open the image.

## Gmail attachments cannot come from a local path

`send_gmail_message`'s `attachments.path` resolves inside the cluster where the workspace MCP
runs, so a local path fails with "Path does not exist". Call the MCP door over HTTP with the file
base64-inlined from disk (`jq --rawfile`), which also keeps the payload out of the transcript.
