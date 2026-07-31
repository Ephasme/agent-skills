#!/usr/bin/env bash
# Pure-curl fetch of the current account's recent transaction feed from
# Crédit Agricole's "detail compte DAV" BFF (detail-dav.credit-agricole.fr) —
# no browser automation, no JS injection. This is the same feed backing the
# "Détail compte DAV" page's "Liste des opérations", and structurally a much
# better source than the CSV export or the PDF relevés: it's a single JSON
# GET returning a signed `montant` per operation (no debit/credit column
# guessing, no cp1252/HTML-entity encoding quirks).
#
# Like the Hub Documentaire, this is a separate-origin micro-app embedded in
# an iframe on espace-client.credit-agricole.fr, authenticated purely via a
# session cookie scoped to detail-dav.credit-agricole.fr (confirmed via a
# real cookie-jar replay) — unlike the "Télécharger mes opérations" CSV
# export's iframe, which needs an ephemeral contextId handshake and has no
# curl equivalent (see csv_to_transactions.py's docstring).
#
# Observed cap: ~90 operations / ~12 months, hasNext:false with no further
# pagination found — same rolling window as the CSV export. Not a full
# history source; use fetch_releves.sh + releves_to_transactions.py for
# anything older than what this returns, and use this only to bridge the gap
# between the latest relevé's closing date and today.
#
# Usage:
#   fetch_operations.sh --jar jar.txt --out operations.json
set -euo pipefail

JAR=""
OUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$JAR" || -z "$OUT" ]]; then
  echo "Usage: $0 --jar jar.txt --out operations.json" >&2
  exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

STATUS=$(curl -sS -b "$JAR" -A "$UA" \
  -H "Referer: https://espace-client.credit-agricole.fr/" \
  -o "$OUT" -w "%{http_code}" \
  "https://detail-dav.credit-agricole.fr/ca-centrefrance/bff/operations/imputees")

if [[ "$STATUS" != "200" ]]; then
  echo "ERROR: operations request returned HTTP $STATUS (expected 200). Cookie jar likely stale or missing detail-dav.credit-agricole.fr cookies." >&2
  exit 1
fi

if ! python3 -c "import json,sys; d=json.load(open('$OUT')); sys.exit(0 if 'operationBlocs' in d else 1)" 2>/dev/null; then
  echo "ERROR: response doesn't look like the expected {operationBlocs: [...]} shape — inspect $OUT, the jar is probably not authenticated." >&2
  exit 2
fi

COUNT=$(python3 -c "import json; d=json.load(open('$OUT')); print(sum(len(b['operationDetails']) for b in d['operationBlocs']))")
echo "wrote $OUT ($COUNT operations, hasNext=$(python3 -c "import json; print(json.load(open('$OUT'))['hasNext'])"))"
