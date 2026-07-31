#!/usr/bin/env bash
# Pure-curl fetch of every monthly "Relevé de compte" PDF from Crédit
# Agricole's Hub Documentaire (hubdocumentaire.credit-agricole.fr) — no
# browser automation, no JS injection. Unlike the CSV "Télécharger mes
# opérations" export (cross-origin iframe + contextId handshake, see
# csv_to_transactions.py's docstring and SKILL.md), the Hub Documentaire is a
# plain top-level SPA whose BFF authenticates purely via session cookies.
# The document list and each document's download both are simple
# cookie-authenticated GETs.
#
# Usage:
#   fetch_releves.sh --jar jar.txt --out-dir releves/
#
# The jar must carry cookies for hubdocumentaire.credit-agricole.fr (the BFF
# session cookie set during the OAuth-code handshake espace-client performs
# when you click Documents > "Accéder à mes documents"). Cookies for
# espace-client.credit-agricole.fr alone are not enough — the two are
# separate origins with separate sessions.
#
# Only real monthly statements are fetched (libelle starting "Relevé n°",
# libelleTypeDocument "Relevés") — the annual "Relevés de Facturation"
# summaries that share the same category are skipped; they're fee summaries,
# not account statements, and would break the opening/closing balance chain
# in csv_to_transactions.py's monthly-statement parser.
set -euo pipefail

JAR=""
OUT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --jar) JAR="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

if [[ -z "$JAR" || -z "$OUT_DIR" ]]; then
  echo "Usage: $0 --jar jar.txt --out-dir releves/" >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
BASE="https://hubdocumentaire.credit-agricole.fr/ca-centrefrance/bff/api/hub"
WORKTMP=$(mktemp -d)
# Only cleaned up on success (see bottom) so a failed run's raw responses
# stay inspectable at $WORKTMP.

# 1. Fetch the document list (all types), verify it looks authenticated.
STATUS=$(curl -sS -b "$JAR" -c "$JAR" -A "$UA" \
  -H "Referer: https://hubdocumentaire.credit-agricole.fr/ca-centrefrance/fe/" \
  -o "$WORKTMP/documents.json" -w "%{http_code}" \
  --get "$BASE/documents" \
  --data-urlencode "texte=" \
  --data-urlencode "date_debut=" \
  --data-urlencode "date_fin=")

if [[ "$STATUS" != "200" ]]; then
  echo "ERROR: document list request returned HTTP $STATUS (expected 200). Cookie jar likely stale or missing hubdocumentaire.credit-agricole.fr cookies." >&2
  exit 1
fi

if ! jq -e '.listeDocument | type == "array"' "$WORKTMP/documents.json" >/dev/null 2>&1; then
  echo "ERROR: response doesn't look like the expected {listeDocument: [...]} shape — inspect $WORKTMP/documents.json (kept on disk since this run failed), the jar is probably not authenticated." >&2
  exit 2
fi

# 2. Filter to real monthly statements only, TSV: id, key, libelle.
jq -r '.listeDocument[]
  | select(.libelleTypeDocument == "Relevés" and (.libelle | startswith("Relevé n°")))
  | [.id, .key, .libelle] | @tsv' "$WORKTMP/documents.json" > "$WORKTMP/releves.tsv"

COUNT=$(wc -l < "$WORKTMP/releves.tsv" | tr -d ' ')
if [[ "$COUNT" -eq 0 ]]; then
  echo "ERROR: no monthly relevés found in the document list — check $WORKTMP/documents.json (kept on disk since this run failed)." >&2
  exit 3
fi
echo "found $COUNT monthly relevés"

# 3. Download each one.
OK=0
FAIL=0
while IFS=$'\t' read -r ID KEY LIBELLE; do
  # Sanitize for filesystem: "/" (from "n°007 du 02/07/2026") -> "-".
  FNAME=$(echo "$LIBELLE" | tr '/' '-')
  DEST="$OUT_DIR/$FNAME.pdf"

  DSTATUS=$(curl -sS -b "$JAR" -c "$JAR" -A "$UA" \
    -H "Referer: https://hubdocumentaire.credit-agricole.fr/ca-centrefrance/fe/" \
    -o "$DEST" -w "%{http_code}" \
    --get "$BASE/download_document/document.pdf" \
    --data-urlencode "document_id=${ID}" \
    --data-urlencode "key_id=${KEY}" \
    --data-urlencode "origine=EDOC" \
    --data-urlencode "format=application/pdf" \
    --data-urlencode "categorie_id=00008")

  if [[ "$DSTATUS" == "200" ]] && head -c 4 "$DEST" | grep -q '%PDF'; then
    OK=$((OK+1))
  else
    echo "  FAILED ($DSTATUS): $LIBELLE" >&2
    rm -f "$DEST"
    FAIL=$((FAIL+1))
  fi
done < "$WORKTMP/releves.tsv"

echo "wrote $OK PDFs to $OUT_DIR ($FAIL failed)"
if [[ "$FAIL" -gt 0 ]]; then
  echo "one or more downloads failed — $WORKTMP kept on disk for inspection." >&2
  exit 4
fi
rm -rf "$WORKTMP"
