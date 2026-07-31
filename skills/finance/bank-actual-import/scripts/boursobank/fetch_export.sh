#!/usr/bin/env bash
# Pull a full transactions export from BoursoBank for one account, via pure
# curl (no browser automation, no JS injection) — using an authenticated
# cookie jar. See ../SKILL.md for how to obtain the jar and the account key.
#
# Usage:
#   fetch_export.sh --jar jar.txt --account-key <KEY> --out export.csv \
#     [--from 01/01/2000] [--to DD/MM/YYYY] [--format CSV|QIF|OFX|XLSX]
#
# <KEY> is the hex string in the account's own URL, e.g. for
#   https://clients.boursobank.com/compte/cav/a7d277658d6373812ae91b61c2ce6569/
# the key is a7d277658d6373812ae91b61c2ce6569. Works for any account type
# (cav, epargne/livret-a, ...) — the export endpoint only cares about the key.
set -euo pipefail

JAR=""
ACCOUNT_KEY=""
OUT=""
FROM="01/01/2000"
TO=""
FORMAT="CSV"

while [ $# -gt 0 ]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --account-key) ACCOUNT_KEY="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --format) FORMAT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 1 ;;
  esac
done

[ -z "$TO" ] && TO=$(date +%d/%m/%Y)

if [ -z "$JAR" ] || [ -z "$ACCOUNT_KEY" ] || [ -z "$OUT" ]; then
  echo "usage: fetch_export.sh --jar jar.txt --account-key KEY --out export.csv [--from DD/MM/YYYY] [--to DD/MM/YYYY] [--format CSV]" >&2
  exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
WORKTMP=$(mktemp -d)
trap 'rm -rf "$WORKTMP"' EXIT

# 1. Fresh page load: the export form embeds a single-use CSRF token that
#    must be scraped immediately before the POST below.
curl -sS -b "$JAR" -c "$JAR" -A "$UA" \
  -H "Accept-Language: fr-FR,fr;q=0.9" \
  -H "Referer: https://clients.boursobank.com/" \
  -o "$WORKTMP/form.html" \
  "https://clients.boursobank.com/operations/generate/$ACCOUNT_KEY"

TOKEN=$(grep -o 'name="movementSearch\[_token\]"[^>]*value="[^"]*"' "$WORKTMP/form.html" | sed -E 's/.*value="([^"]*)".*/\1/')
if [ -z "$TOKEN" ]; then
  echo "ERROR: could not scrape CSRF token — cookie jar is probably not authenticated (check for a login-page title in $WORKTMP/form.html before it's deleted, or rerun with a fresh cookie export)." >&2
  exit 2
fi

# 2. POST the export request. This 302s to a same-origin HTML redirect page
#    containing a ONE-TIME download token on api.boursobank.com — it is not
#    the file itself.
curl -sS -b "$JAR" -c "$JAR" -A "$UA" \
  -H "Accept: */*" -H "Accept-Language: fr-FR,fr;q=0.9" \
  -H "Referer: https://clients.boursobank.com/operations/generate/$ACCOUNT_KEY" \
  -H "Origin: https://clients.boursobank.com" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "movementSearch[fromDate]=$FROM" \
  --data-urlencode "movementSearch[toDate]=$TO" \
  --data-urlencode "movementSearch[format]=$FORMAT" \
  --data-urlencode "movementSearch[_token]=$TOKEN" \
  --data-urlencode "movementSearch[submit]=" \
  -o "$WORKTMP/redirect.html" \
  "https://clients.boursobank.com/budget/exporter-mouvements/$ACCOUNT_KEY"

DL_URL=$(grep -o "https://api\.boursobank\.com/services/api/files/download\.phtml?token=[a-f0-9]*" "$WORKTMP/redirect.html" | head -1)
if [ -z "$DL_URL" ]; then
  echo "ERROR: no download token found in the export response. The account key may be wrong, the session may have expired, or BoursoBank changed this flow." >&2
  exit 3
fi

# 3. Follow the one-time token to get the real file.
curl -sS -b "$JAR" -c "$JAR" -A "$UA" \
  -H "Referer: https://clients.boursobank.com/" \
  -o "$OUT" -D "$WORKTMP/final.hdr" \
  -w "downloaded: code=%{http_code} size=%{size_download} bytes\n" \
  "$DL_URL"

if ! grep -qi '^content-disposition: attachment' "$WORKTMP/final.hdr"; then
  echo "WARNING: response didn't look like a file attachment — check $OUT manually, it may be an HTML error page." >&2
fi

echo "wrote $OUT"
