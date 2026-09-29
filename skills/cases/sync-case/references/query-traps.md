# Query traps

## Multi-term full-text search returns nothing

A WhatsApp message search for `a OR b OR c` returned zero over a window that provably contained a
message with `c`; the single term `c` found it at once. Search **one term at a time**, and
corroborate with a plain message listing over the window. Treat any past "search returned nothing"
as weak evidence.

## An image arrives as a placeholder

Some agent harnesses flatten MCP results to text, so a media-download tool that returns a valid
image block reaches the model as `[Image: image/jpeg]`. When that happens:

1. Get the bytes onto disk — from the harness's session log if the result is stored there inline,
   or by calling the MCP server's download tool directly (outside the model's context) and writing
   the decoded result to a file under `cases/<slug>/documents/`.
2. Open the written file with the harness's file-reading tool, which renders images.

Do not log "media unavailable" and do not ask a human to open the image.

## Email attachments may not come from a local path

When the email MCP server runs remotely, a send tool's attachment `path` resolves on the server,
so a local path fails with "Path does not exist". Call the server's send tool with the file
base64-inlined from disk (for example `jq --rawfile`), which also keeps the payload out of the
transcript.
