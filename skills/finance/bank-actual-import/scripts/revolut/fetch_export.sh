#!/usr/bin/env bash
# Pure-curl export of a Revolut account's full transaction history via the
# same async job the web app's "Statement" (Excel/CSV) feature uses.
#
# Unlike the French banks, Revolut's session is NOT purely cookie-based:
# every API call also needs x-device-id/x-hardware-id headers (read from the
# revo_device_id/revo_hardware_id cookies on .revolut.com in the same cookie
# export) or the backend returns a generic
# {"message":"Phone and/or passcode are incorrect","code":9001} 401 no
# matter how fresh/valid the cookies otherwise are — this looks like a
# step-up-auth failure but is actually just two missing headers.
#
# The statement itself is an async job: the first GET kicks it off
# ("state":"IN_PREPARATION"), and the SAME GET (identical query string) is
# polled until "state":"READY", at which point the response also carries a
# signed, unauthenticated download URL (Google Cloud Storage) for the actual
# CSV — a second plain curl fetches that.
#
# Usage:
#   fetch_export.sh --jar jar.txt --device-id <uuid> --hardware-id <uuid> \
#     --out export.csv [--ccy EUR] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
#
# --device-id/--hardware-id: the revo_device_id / revo_hardware_id cookie
#   values for .revolut.com — not secrets on their own, but required on
#   every API call alongside the session cookies.
# --ccy: the account's currency (EUR, GBP, USD...) — Revolut is
#   multi-currency and statements are generated per pocket/currency.
# --from: defaults to 2015-01-01 (before Revolut existed) so the export
#   covers full account history regardless of when the account was opened —
#   the server just returns whatever it actually has, no error on an
#   over-wide range.
set -euo pipefail

JAR=""
DEVICE_ID=""
HARDWARE_ID=""
CCY="EUR"
OUT="export.csv"
FROM="2015-01-01"
TO=$(date +%Y-%m-%d)
MAX_ATTEMPTS=20

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --device-id) DEVICE_ID="$2"; shift 2 ;;
    --hardware-id) HARDWARE_ID="$2"; shift 2 ;;
    --ccy) CCY="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$JAR" || -z "$DEVICE_ID" || -z "$HARDWARE_ID" ]]; then
  echo "Usage: $0 --jar jar.txt --device-id <uuid> --hardware-id <uuid> --out export.csv [--ccy EUR] [--from YYYY-MM-DD] [--to YYYY-MM-DD]" >&2
  exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
JOB_JSON=$(mktemp)
trap 'rm -f "$JOB_JSON"' EXIT

for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  STATUS=$(curl -sS -b "$JAR" -A "$UA" \
    -H "x-device-id: ${DEVICE_ID}" -H "x-hardware-id: ${HARDWARE_ID}" \
    -o "$JOB_JSON" -w "%{http_code}" \
    --get "https://app.revolut.com/api/retail/user/current/statements/account-statements" \
    --data-urlencode "from=${FROM}" --data-urlencode "to=${TO}" \
    --data-urlencode "ccy=${CCY}" --data-urlencode "format=CSV" --data-urlencode "type=OFFICIAL")

  if [[ "$STATUS" != "200" ]]; then
    echo "ERROR: statement request returned HTTP $STATUS (expected 200). Cookie jar stale, or device-id/hardware-id wrong — see $JOB_JSON:" >&2
    cat "$JOB_JSON" >&2
    exit 1
  fi

  STATE=$(python3 -c "import json; print(json.load(open('$JOB_JSON')).get('state',''))")

  if [[ "$STATE" == "READY" ]]; then
    URL=$(python3 -c "import json; print(json.load(open('$JOB_JSON'))['url'])")
    DL_STATUS=$(curl -sS -o "$OUT" -w "%{http_code}" "$URL")
    if [[ "$DL_STATUS" != "200" ]]; then
      echo "ERROR: signed-URL download returned HTTP $DL_STATUS" >&2
      exit 1
    fi
    if ! head -1 "$OUT" | grep -q '^Type,Product,'; then
      echo "WARNING: $OUT doesn't start with the expected CSV header — inspect it before trusting the export." >&2
    fi
    echo "wrote $OUT (job reached READY after $attempt poll(s))"
    exit 0
  fi

  sleep 3
done

echo "ERROR: statement job never reached READY after $MAX_ATTEMPTS polls (last state: $STATE)" >&2
exit 1
