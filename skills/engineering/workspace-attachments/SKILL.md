---
name: workspace-attachments
description: >-
  Moves real file bytes in and out of the self-hosted Google Workspace MCP servers
  (Gmail, Drive, Chat) — which do all their file I/O on the server, not on the
  machine the agent runs on, so the obvious call silently produces an unusable
  result. Use whenever a task involves an email attachment or a Drive file as
  *bytes* rather than as metadata: "download the invoice from that email", "save
  the PDF attached to X", "send this file to Y", "attach the report", "upload this
  to Drive", "forward that attachment", "read the attached spreadsheet", "get the
  receipt out of my inbox", or in French "télécharge la pièce jointe", "envoie ce
  fichier", "mets ça sur Drive", "récupère la facture en pièce jointe". Also when
  a download "succeeded" but the returned path or URL cannot be opened, or an
  upload failed with a path error naming a file that does exist locally. Not
  needed for listing, searching, or reading message bodies.
compatibility: >-
  Requires the self-hosted workspace-mcp (1.21.1) instances reached over HTTP
  behind Cloudflare Access, one per Google identity (personal and work). Paths,
  env var names and the base64 escape hatch are specific to that deployment;
  a local stdio workspace-mcp returns real local paths instead and needs none of
  this. Verified end-to-end 2026-08-14.
---

# Google Workspace attachments

**The one fact that explains every failure here: these tools' "local disk" is the
server's disk, not yours.** Every download writes into the server's own filesystem
and hands back a path or URL that is meaningless to you; every upload that takes a
path or `file://` URL resolves it on the server, so a real file on your machine
reports "Path does not exist". Nothing about this is visible in the tool
descriptions, which just say "saves it to local disk".

So never pass a local path, and never treat a returned path as openable. Pick a
route from the two tables below instead.

## Getting bytes out

| source | do this |
|---|---|
| Gmail attachment | `get_gmail_attachment_content` with **`return_base64: true`** |
| Drive file, Chat attachment | fetch the returned URL with the Access service token (below) |

`return_base64` is the first choice whenever it exists: no network, no
credentials, no expiry. It is absent from the tool's one-line description but
present in the schema, and it appends the bytes as standard base64 alongside the
usual metadata. Decode with `base64 -d` (write the payload to a file first — it is
large, and shell-quoting it inline will corrupt it).

`get_drive_file_download_url` has **no such flag**, so for Drive the URL is the
only way out. The URL points at the instance's public door and the bytes are
correct, but the door is behind Cloudflare Access: **an unauthenticated fetch is a
bare `401`**, which reads like a dead link and is the single most common reason a
Drive download looks broken. Send the service token for the matching instance —
`GOOGLE_PERSO_CF_ACCESS_CLIENT_ID`/`_SECRET` for the personal Google identity,
`GOOGLE_WORK_CF_ACCESS_CLIENT_ID`/`_SECRET` for the work one:

```bash
curl -H "CF-Access-Client-Id: $GOOGLE_PERSO_CF_ACCESS_CLIENT_ID" \
     -H "CF-Access-Client-Secret: $GOOGLE_PERSO_CF_ACCESS_CLIENT_SECRET" \
     -o invoice.pdf "<the download URL from the tool>"
```

Verify what you got (`file`, or a byte count against the size the tool reported)
before using it. A `401` body written to a `.pdf` is still a file, and a
downstream step will fail somewhere less obvious.

The URL expires after **1 hour**, and the index that resolves it lives in memory,
so a server restart invalidates it early. Re-run the download tool to get a fresh
one; do not retry a stale URL.

## Putting bytes in

| goal | do this |
|---|---|
| attach your own bytes to mail | `attachments: [{"filename": …, "content": "<base64>", "mime_type": …}]` — binary-safe |
| re-attach something just downloaded | `attachments: [{"url": "<that download URL>"}]` |
| Gmail attachment → Drive | `create_drive_file` with `fileUrl: "file:///root/.workspace-mcp/attachments/<saved filename>"` |
| **your own binary file → Drive** | no direct route — see below |

The `url` form is better than re-uploading base64 when the file came from a
download in the same task: the server recognises its own attachment URL, reads the
file straight off its disk, and never makes an HTTP request — so it needs no
Access token and is not affected by the 1-hour expiry the way an outside fetch is.

The `file://` form works only because the file is *already on the server*, put
there by an earlier download. `<saved filename>` is the **`Saved filename`** the
download reported, not the original attachment name — it carries an added uuid
suffix. Reads are confined to that attachment directory; do not try to widen the
allowlist to reach something else, and do not expect any other server path to be
readable.

**Binary uploads to Drive have no direct path.** `create_drive_file`'s `content`
parameter is encoded as UTF-8, so it can carry text but will corrupt any binary.
Either make the bytes reachable at an `https` URL the server can fetch, or route
them through Gmail (attach as base64, then use the `file://` row). Say so plainly
rather than sending a corrupted file — a UTF-8-mangled PDF uploads "successfully"
and only fails when someone opens it.

## Two smaller traps

1. `to`, `cc` and `bcc` reject a JSON array — Gmail answers `Invalid To header`.
   Pass one comma-separated string.
2. Attachment ids are per-fetch. Take them from the most recent message read; a
   stale id fails even though the message and the file are both fine.
