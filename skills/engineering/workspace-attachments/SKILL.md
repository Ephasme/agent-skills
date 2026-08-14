---
name: workspace-attachments
description: >-
  Moves real file bytes in and out of the self-hosted Google Workspace MCP servers
  (Gmail, Drive, Chat), which do all their file I/O on the server rather than on
  the machine the agent runs on, so the obvious call silently produces an unusable
  result. Use whenever a task treats an email attachment or a Drive file as bytes
  rather than metadata: "download the invoice from that email", "save the PDF
  attached to X", "send this file to Y", "attach the report", "upload this to
  Drive", "forward that attachment", or in French "télécharge la pièce jointe",
  "envoie ce fichier", "mets ça sur Drive". Also when a download "succeeded" but
  the returned path or URL cannot be opened, an upload failed with a path error
  naming a file that does exist locally, or a file is big enough that inlining it
  would blow the context window — it routes by size and says which attachments
  must never be inlined. Not needed for listing, searching or reading bodies.
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

**Read the size first.** The message listing already reports every attachment's
size, and the size picks the route — so decide before downloading, not after.

| situation | do this |
|---|---|
| **default, any size** | run the download tool, then fetch the URL it returns with the Access service token (below) |
| no Access token available, **and under ~100 KB** | Gmail only: `get_gmail_attachment_content` with `return_base64: true` |
| no token and over that | stop and say the token is required — there is no third route |

The URL route is the default because it puts the bytes **on disk**, which is where
every subsequent step needs them, and it is indifferent to size.

🔴 **`return_base64` routes the whole file through the context window, so it is a
small-file fallback and nothing more.** Base64 inflates by 4/3, and Gmail permits
attachments up to 25 MB — about 33 MB of text, order 8M tokens, which no context
holds. The ceiling bites far earlier than that: a **51 KB** PDF produced ~70 KB of
base64, which the harness elided and spilled to an artifact rather than showing,
so the bytes never reached the model anyway. Treat ~100 KB as a hard stop, prefer
the URL well below it, and never reach for this flag merely because it needs no
credentials. It is absent from the tool's one-line description but present in the
schema. Decode with `base64 -d`, writing the payload to a file first — shell-
quoting it inline will corrupt it.

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

Each destination takes a **different key**, and they are not interchangeable:
`content` (base64) and `path` (a server-side path) on the mail tools' `attachments`
entries, `url` on those same entries but only for a URL the server itself minted,
and `fileUrl` on `create_drive_file`. There is no `fileUrl` on the mail tools and
no `path` on `create_drive_file`.

| goal | do this |
|---|---|
| attach your own bytes to mail, **under ~100 KB** | `attachments: [{"filename": …, "content": "<base64>", "mime_type": …}]` — binary-safe |
| attach your own bytes to mail, **larger** | copy onto the server (below), then `attachments: [{"path": "/root/.workspace-mcp/attachments/<name>"}]` |
| re-attach something just downloaded | `attachments: [{"url": "<that download URL>"}]` |
| any local file → Drive | copy onto the server (below), then `create_drive_file` with `fileUrl: "file:///root/.workspace-mcp/attachments/<name>"` |
| Gmail attachment → Drive | already on the server: same as above, with the **`Saved filename`** the download reported |

`{"path": …}` is the route for a file you put on the server yourself, and it is
the only one that is: a manually copied file has no `/attachments/<uuid>` URL,
because that uuid index is created solely by the server's own download tools.
Verified with the 2 MB binary below — Gmail confirmed 2048.0 KB on the draft.

`{"url": …}` is therefore for one case only: re-attaching something a download
tool produced in this same task. The server recognises its own attachment URL,
reads the file off disk and makes no HTTP request, so it needs no Access token and
is not subject to the 1-hour expiry the way an outside fetch is.

Both server-side forms read only inside the attachment directory. For a file a
download left behind, the name is the **`Saved filename`** it reported, not the
original attachment name — it carries an added uuid suffix. Do not try to widen
the allowlist, and do not expect any other server path to be readable.

🔴 **The same ~100 KB ceiling applies to base64 going in.** A `content` payload is
a tool argument, so the whole file passes through the context window on the way
out just as it does on the way in. Do not base64 a multi-megabyte local file.

**`create_drive_file`'s `content` parameter cannot carry binary at all** — it is
encoded as UTF-8, so a PDF or image uploads "successfully" and only fails when
someone opens it. Never use `content` for anything that is not text; use a
`fileUrl` instead.

**Getting a local file onto the server** is therefore the route for anything
binary or large. The attachment directory is writable, so copy into it and then
reference that path — `{"path": …}` for mail, `fileUrl: "file://…"` for Drive.
Verified with a 2 MB binary: md5 survived the copy, the Drive upload and a
download back out, and Gmail confirmed the full 2048.0 KB on a draft.

```bash
POD=$(kubectl -n mcp-servers get pod -l app=workspace-perso-mcp \
        -o jsonpath='{.items[0].metadata.name}')
kubectl -n mcp-servers cp ./report.pdf \
        "$POD:/root/.workspace-mcp/attachments/report.pdf"
```

⚠️ That `cp` **exits non-zero** with `tar: Cannot change ownership … Operation not
permitted` while writing the file correctly anyway. Do not treat the failure as
real or retry it — confirm with `md5sum` inside the pod instead:

```bash
kubectl -n mcp-servers exec "$POD" -- \
        md5sum /root/.workspace-mcp/attachments/report.pdf
```

Use the work Deployment's own label for the work identity. Clean up after
yourself: files left there are served for an hour by anyone holding the door
token, and the directory is not swept for names the server did not create itself.

## Two smaller traps

1. `to`, `cc` and `bcc` reject a JSON array — Gmail answers `Invalid To header`.
   Pass one comma-separated string.
2. Attachment ids are per-fetch. Take them from the most recent message read; a
   stale id fails even though the message and the file are both fine.
