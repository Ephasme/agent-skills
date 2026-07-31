#!/usr/bin/env bash
# Pure-curl fetch of every monthly "Relevé de compte" PDF for a BNP Paribas
# account, via the same "Documents & relevés" > "Relevés" feature the web
# app uses -- a completely different, much deeper history source than
# fetch_export.sh's 13-month CSV (which is a genuine, server-enforced cap on
# that specific endpoint, confirmed by testing dateDebutOperation=2015 and
# getting the same ~13-month window back unchanged).
#
# Two-step, both plain cookie-authenticated (no CSRF token, no special auth
# beyond the session cookies already used by fetch_export.sh):
#   1. POST demat-wspl/rest/rechercheCriteresDemat {"dateDebut":...,"dateFin":...}
#      -> JSON listing every document in that window, across ALL document
#      categories (statements, contracts, tax certificates...) each with an
#      opaque idDoc. This script only keeps the "Comptes chèques" /
#      typeDoc=="RELEV" entries.
#   2. GET demat-wspl/rest/consultationDocumentDemat?ibanCrypte=...&idDocument=
#      <idDoc>&... -> the actual PDF bytes (content-type: application/pdf).
#
# A wide dateDebut (e.g. 01/01/2010) does NOT return an error or an empty
# set -- the server just clamps to whatever actually exists, so the true
# earliest statement date is whatever comes back, not necessarily what you
# asked for (found empirically: this account's archive starts 2021-10/11,
# not 2010).
#
# Usage:
#   fetch_releves.sh --jar jar.txt --iban-crypte <blob> --out-dir releves/ \
#     [--from DD/MM/YYYY] [--to DD/MM/YYYY]
set -euo pipefail

JAR=""
IBAN_CRYPTE=""
OUT_DIR="releves"
FROM="01/01/2010"
TO=$(date +%d/%m/%Y)

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --iban-crypte) IBAN_CRYPTE="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$JAR" || -z "$IBAN_CRYPTE" ]]; then
  echo "Usage: $0 --jar jar.txt --iban-crypte <blob> --out-dir releves/ [--from DD/MM/YYYY] [--to DD/MM/YYYY]" >&2
  exit 1
fi

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
mkdir -p "$OUT_DIR"
LIST_JSON=$(mktemp)
trap 'rm -f "$LIST_JSON"' EXIT

STATUS=$(curl -sS -b "$JAR" -A "$UA" \
  -H "Content-Type: application/json" \
  -X POST -d "{\"dateDebut\":\"${FROM}\",\"dateFin\":\"${TO}\"}" \
  -o "$LIST_JSON" -w "%{http_code}" \
  "https://mabanque.bnpparibas/demat-wspl/rest/rechercheCriteresDemat")

if [[ "$STATUS" != "200" ]]; then
  echo "ERROR: rechercheCriteresDemat returned HTTP $STATUS (expected 200). Cookie jar likely stale." >&2
  cat "$LIST_JSON" >&2
  exit 1
fi

# Filter to actual monthly statements (typeDoc RELEV) under "Comptes chèques" --
# the same date-range search also returns other document families (tax
# certificates, contracts...) which this script has no use for.
readarray -t DOC_LINES < <(python3 -c "
import json
d = json.load(open('$LIST_JSON'))
docs = d.get('data', {}).get('rechercheCriteresDemat', {}).get('mapDocuments', {}).get('Comptes chèques', {}).get('listeDocument', [])
for doc in docs:
    if doc.get('typeDoc') == 'RELEV':
        print('\t'.join([doc['idDoc'], doc['idLocalisation'], doc['viDocDocument'], doc['dateDoc'], doc['typeCompte'], doc['famDoc']]))
")

if [[ "${#DOC_LINES[@]}" -eq 0 ]]; then
  echo "ERROR: no RELEV documents found for 'Comptes chèques' in this window -- inspect $LIST_JSON" >&2
  exit 1
fi

echo "found ${#DOC_LINES[@]} monthly relevé(s)"

OK=0
FAIL=0
for line in "${DOC_LINES[@]}"; do
  IFS=$'\t' read -r ID_DOC ID_LOC VI_DOC DATE_DOC TYPE_CPT FAM_DOC <<< "$line"
  # DD/MM/YYYY -> YYYY-MM-DD for the filename
  FNAME_DATE=$(python3 -c "d='$DATE_DOC'.split('/'); print(f'{d[2]}-{d[1]}-{d[0]}')")
  OUT_PDF="$OUT_DIR/releve_${FNAME_DATE}.pdf"

  DL_STATUS=$(curl -sS -b "$JAR" -A "$UA" \
    -o "$OUT_PDF" -w "%{http_code}" \
    --get "https://mabanque.bnpparibas/demat-wspl/rest/consultationDocumentDemat" \
    --data-urlencode "ibanCrypte=${IBAN_CRYPTE}" \
    --data-urlencode "idDocument=${ID_DOC}" \
    --data-urlencode "idLocalisation=${ID_LOC}" \
    --data-urlencode "viDocDocument=${VI_DOC}" \
    --data-urlencode "dateDocument=${DATE_DOC}" \
    --data-urlencode "typeCpt=${TYPE_CPT}" \
    --data-urlencode "typeDoc=RELEV" \
    --data-urlencode "typeFamille=R001" \
    --data-urlencode "familleDoc=${FAM_DOC}" \
    --data-urlencode "consulted=false")

  if [[ "$DL_STATUS" == "200" ]] && head -c 4 "$OUT_PDF" | grep -q '%PDF'; then
    OK=$((OK+1))
  else
    echo "WARNING: failed to fetch relevé dated $DATE_DOC (HTTP $DL_STATUS)" >&2
    FAIL=$((FAIL+1))
  fi
done

echo "fetched $OK/${#DOC_LINES[@]} relevé PDF(s) into $OUT_DIR ($FAIL failed)"
if [[ "$FAIL" -gt 0 ]]; then
  exit 1
fi
