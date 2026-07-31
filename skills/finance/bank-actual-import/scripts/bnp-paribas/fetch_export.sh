#!/usr/bin/env bash
# Pure-curl export of a BNP Paribas (mabanque.bnpparibas) account's transaction
# history via the same GET endpoint the "Télécharger mes opérations" page
# calls. Unlike BoursoBank, this is a single unauthenticated-looking GET with
# no CSRF token and no one-time download link — session cookies are the only
# auth. BNP caps history at 13 months regardless of date range requested.
#
# Usage:
#   fetch_export.sh --jar jar.txt --iban-crypte <blob> --out export.csv \
#     [--from DD/MM/YYYY] [--to DD/MM/YYYY]
#
# --iban-crypte: the obfuscated account identifier from the account's own URL
#   on mabanque.bnpparibas, e.g. .../releve-d-operations/connected/current-balance
#   ?id=...&iban=<THIS>  — despite the name it is not a real IBAN, just an
#   opaque per-account token BNP happens to call "iban" in the URL.
set -euo pipefail

JAR=""
IBAN_CRYPTE=""
OUT="export.csv"
FROM=""
TO=$(date +%d/%m/%Y)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --iban-crypte) IBAN_CRYPTE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$JAR" || -z "$IBAN_CRYPTE" ]]; then
  echo "Usage: $0 --jar jar.txt --iban-crypte <blob> --out export.csv [--from DD/MM/YYYY] [--to DD/MM/YYYY]" >&2
  exit 1
fi

if [[ -z "$FROM" ]]; then
  # Default to the maximum 13-month window BNP allows.
  FROM=$(date -v-13m +%d/%m/%Y 2>/dev/null || date -d "-13 months" +%d/%m/%Y)
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"

STATUS=$(curl -sS -b "$JAR" -A "$UA" \
  -o "$OUT" -w "%{http_code}" \
  --get "https://mabanque.bnpparibas/pfm-telechargerop-wspl/rest/rechercheSoldeMvt" \
  --data-urlencode "ibanCrypte=${IBAN_CRYPTE}" \
  --data-urlencode "dateDebutOperation=${FROM}" \
  --data-urlencode "dateFinOperation=${TO}" \
  --data-urlencode "formatDate=dd/MM/yyyy" \
  --data-urlencode "formatSeparateur=," \
  --data-urlencode "nomFichier=export.csv" \
  --data-urlencode "extension=csv")

if [[ "$STATUS" != "200" ]]; then
  echo "ERROR: export request returned HTTP $STATUS (expected 200). Cookie jar likely stale or ibanCrypte wrong." >&2
  exit 1
fi

if ! head -c 1 "$OUT" | grep -q '"'; then
  echo "WARNING: $OUT doesn't look like the expected quoted-CSV metadata line — inspect it before trusting the export." >&2
fi

echo "wrote $OUT"
