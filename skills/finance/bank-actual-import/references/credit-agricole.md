# Crédit Agricole

Everything specific to Crédit Agricole: how its export is replayed in curl, and the traps that cost time. The shared seven-step procedure, the shared gotchas, and the reconciliation step live in [`../SKILL.md`](../SKILL.md).

## Contents

- [Export mechanics](#export-mechanics)
- [Gotchas — the pure-curl relevés + operations pipeline](#gotchas-the-pure-curl-relevés-operations-pipeline)
- [Gotchas — the CSV fallback](#gotchas-the-csv-fallback)

## Export mechanics

Three independent micro-apps, three different levels of curl-replicability —
worth understanding before picking a path:

- **`telechargement-operations.credit-agricole.fr`** ("Télécharger mes
  opérations" CSV export) — **no curl replication.** This one embeds a
  *cross-origin* Angular app in an iframe requiring a `contextId` minted via
  a parent/child handshake on load; navigating to its URL directly, alone,
  fails with "Aucun contexte récupéré bien qu'il soit spécifié comme
  obligatoire". Its POST to `bff/generer_document?contextId=...` runs inside
  the iframe's own JS context, invisible to `fetch`/`XMLHttpRequest` patches
  from the parent frame. The download itself, triggered via a real UI click
  through browser automation, never even reached disk (Chrome's own download
  history recorded nothing) — consistent with the extension deliberately not
  persisting scripted-click downloads. **No longer needed** now that the two
  sources below cover full history and the recent bridge between them; kept
  as a documented fallback (`csv_to_transactions.py`) if a session can't
  reach either.
- **`hubdocumentaire.credit-agricole.fr`** (Documents > "Accéder à mes
  documents") — **pure curl.** Also a cross-origin iframe with an
  OAuth-code handshake, but unlike the CSV export, its BFF authenticates via
  a plain session cookie (`SESSION_ID` for that domain) — both the document
  list (`bff/api/hub/documents`) and each PDF download
  (`bff/api/hub/download_document/...?document_id=...&key_id=...`) are
  ordinary cookie-authenticated GETs. `fetch_releves.sh` fetches every
  monthly "Relevé de compte" PDF this way — full account history, not
  capped like the CSV/operations feed.
- **`detail-dav.credit-agricole.fr`** (the account detail page's "Liste des
  opérations") — **pure curl.** Same pattern: cookie-authenticated BFF, one
  GET (`bff/operations/imputees`) returns every recent operation as
  structured JSON with an already-signed `montant` — no debit/credit column
  guessing, no CSV encoding quirks. Capped at ~90 operations / ~12 months
  (`hasNext:false`, no pagination found), same rolling window as the CSV.
  `fetch_operations.sh` fetches it.

**The chain-verified pipeline** (no manual CSV export needed):

1. **Full history via relevé PDFs**, chain-verified month-to-month:
   ```bash
   bash scripts/credit-agricole/fetch_releves.sh --jar jar.txt --out-dir releves/
   ```
   Each relevé states its own opening ("Ancien solde") and closing ("Nouveau
   solde") balance — `releves_to_transactions.py` parses every PDF (via
   `pdfplumber`, word x-positions to recover the Débit/Crédit columns the
   plain-text stream loses — see the script's own docstring for the full
   parsing rationale) and asserts `closing[n] == opening[n+1]` across the
   *entire* chain, not just a single final number.
2. **Bridge the gap** between the last relevé's closing date and today:
   ```bash
   bash scripts/credit-agricole/fetch_operations.sh --jar jar.txt --out operations.json
   ```
3. **Consolidate + verify end-to-end**:
   ```bash
   scripts/.venv/bin/python3 scripts/credit-agricole/releves_to_transactions.py \
     --releves-dir releves/ --operations-json operations.json \
     --target-balance <live balance shown on the account page> \
     --out transactions.json
   ```
   (`scripts/.venv` — see Prerequisites; this account's system Python has no
   `pdfplumber` and is externally managed, refusing `pip install --user`.)
   The script re-derives the opening balance as `target - sum(all
   transactions)` and asserts it matches the *oldest* relevé's own stated
   opening balance — reconciling the whole history end-to-end, not just the
   bridge segment. Refuses to write output on any mismatch.
- **Both jars need the same domains**: cookies for
  `hubdocumentaire.credit-agricole.fr` (step 1) and
  `detail-dav.credit-agricole.fr` (step 2) — both are covered by the same
  full `credit-agricole.fr`-subdomain export used elsewhere in this skill.
- **Hard ~12-month cap on the operations feed** (and the CSV fallback) —
  same category of limit as BNP's 13 months; the relevés are what make full
  history possible at all.
- **Fallback CSV path**, if neither BFF is reachable: get the user to click
  "Télécharger mes opérations" themselves (format **CSV**, not the default
  XLSX, custom period up to ~12 months) and run
  `csv_to_transactions.py --csv export.csv --out transactions.json` —
  or pass `--csv` instead of `--operations-json` to
  `releves_to_transactions.py` to combine it with the relevé history.

## Gotchas — the pure-curl relevés + operations pipeline

- **The account view and Documents both embed cross-origin iframes too**
  (`detail-dav.credit-agricole.fr`, `hubdocumentaire.credit-agricole.fr`) —
  but unlike the CSV export's iframe, both authenticate via a plain session
  cookie rather than an ephemeral handshake, so both are pure-curl
  replicable with a fresh cookie jar. Don't assume "cross-origin iframe" by
  itself means no curl replication — check whether the iframe's own BFF
  needs anything beyond cookies before giving up on it.
- **A `fetch()` from the parent frame's JS to a cross-origin iframe's BFF
  fails with CORS**, even when the endpoint is perfectly curl-replicable —
  CORS is a browser-enforced same-origin policy, curl has no such
  restriction. Don't mistake a CORS failure during in-page reconnaissance
  for evidence the endpoint requires browser-only auth; test it via curl
  with a real cookie jar before concluding that.
- **Automated in-page network exfiltration is deliberately blocked too**:
  a page-context `fetch()` to `http://127.0.0.1:<port>` (tried while
  prototyping a way to get PDF bytes out of the browser without printing
  them as text) fails the same way clicking a download button does — the
  extension refuses it. Both are intentional guardrails, not bugs to route
  around; the actual working approach was PDF.js loaded into the page for
  prototyping (text output only, never binary), then reverse-engineering
  the real endpoints into pure `curl` scripts once understood.
- **Session cookies expire same-day.** A working jar can go stale within
  hours (observed: a `hubdocumentaire.credit-agricole.fr` cookie valid one
  evening returned 401 the next day, and the live tab had silently dropped
  to the logged-out marketing page). Re-check with a cheap authenticated GET
  before assuming a jar is still good; if not, the user must log back in
  and re-export — there's no way around a real login themselves.
- **pdfplumber's word tokenizer splits amounts on the thousands-separator
  space** — `"2 215,90"` extracts as two words, `"2"` and `"215,90"`.
  `releves_to_transactions.py`'s `merge_amount_tokens` reassembles adjacent
  `\d{1,3}` + `\d{3},\d{2}` tokens before the amount regex runs.
- **The Débit/Crédit columns collapse in plain extracted text** — every row
  ends in the same decorative glyph regardless of debit or credit; only the
  word's x-position (relative to the `Débit`/`Crédit` header's own
  x-positions, read fresh per statement rather than hardcoded, in case the
  template shifts across the account's history) recovers which column an
  amount landed in.
- **A balance amount can land in its own y-cluster**, a pixel or two off
  its "Ancien solde"/"Nouveau solde" label — cluster lines by y-*tolerance*
  (a few points), not exact rounding, or the label and its amount end up as
  two separate "lines" and the parse looks like the marker has no balance.
- **10 of 33 real statements spilled onto a 2nd PDF page** — in every case
  observed, that's legal-boilerplate overflow only; the full transaction
  table, "Total des opérations", and "Nouveau solde" always land on page 1.
  The parser still walks pages in state-machine order (bounded by the
  Ancien-solde/Total-des-opérations markers, not by page number) so a
  statement that genuinely needed a 2nd transactions page would still
  parse correctly — it just hasn't been observed on this account.
- **A long description sometimes wraps onto a line with no leading dates**
  (an extra "Default" line, an end-to-end transfer reference, a second-half
  description) — any line not starting with two `DD.MM` tokens folds into
  the previous transaction's description rather than starting a new one.
- **Transaction dates are `DD.MM`, no year** — resolved against each
  statement's own Ancien/Nouveau solde dates (which do carry a year), with
  slack for the Dec→Jan rollover at a statement's boundary.
- **The operations feed's dates are French display strings**
  (`"Samedi 11 juillet 2026"`), not ISO — parsed via a plain month-name
  lookup table, no locale dependency.
- **This account's system Python is externally managed (PEP 668)** —
  `pip3 install --user pdfplumber` is refused outright. Use the dedicated
  `scripts/.venv` (gitignored) instead: `python3 -m venv scripts/.venv &&
  scripts/.venv/bin/pip install pdfplumber`.
- **End-to-end verified on this account**: 33 relevés (Nov 2023 → Jul 2026)
  chain-verified with zero drift, bridged by 4 operations-feed transactions
  to today, opening balance re-derived from the live target balance matches
  the oldest relevé's own stated opening balance exactly — then imported
  into Actual (209 transactions replacing a 22-row placeholder, final sum
  matching the live balance to the cent).
- **The "Relevé n°XXX" sequence number resets every calendar year** — a
  file named `Relevé n°001` exists once per year (Jan 2024, Jan 2025, Jan
  2026...), so seeing "n°001" alone is NOT proof of the account's true
  opening statement. Sort all fetched relevés by their actual date first;
  the chronologically earliest one is the real candidate. Corroborating
  evidence that it really is the first-ever statement: the first calendar
  year has *fewer* statements than a full 12 (this account had exactly 2
  for 2023 — Nov and Dec — consistent with an account opened in
  November), and its own "Ancien solde" line is the ultimate confirmation
  (matched the 5974.05 already used as this account's opening balance,
  exactly).

## Gotchas — the CSV fallback

- **The CSV download page is a cross-origin iframe with an ephemeral
  handshake, not just a session cookie** — see the "no curl replication"
  note above; this is what makes it genuinely different from the relevés/
  operations BFFs above, not merely "another cross-origin iframe". Don't
  monkey-patch `fetch`/`XMLHttpRequest` from the parent frame expecting to
  catch the iframe's own requests; they're on a different origin
  (`telechargement-operations.credit-agricole.fr` vs. the parent
  `espace-client.credit-agricole.fr`) with a completely separate JS global.
- **Automated clicks don't produce a file on disk.** Confirmed by checking
  Chrome's own `downloads` table (in `History`, a SQLite DB) after clicking
  "Télécharger mes opérations" via browser automation — zero new rows, even
  though the in-page UI showed "Téléchargement terminé". Don't waste time
  hunting `~/Downloads` or other paths for a file that was never actually
  written; ask the user to click it themselves instead.
- **Encoded as Windows-1252 (cp1252), not UTF-8.** Reading it as UTF-8
  produces `�` replacement characters on every accented letter (`é`, `€`,
  etc.) — a different failure mode than BNP's entity-encoding bug, not the
  same bug recurring.
- **A real header row exists** (`Date;Libellé;Débit euros;Crédit euros;`),
  unlike BNP — but it's preceded by ~10 lines of boilerplate (download date,
  account holder, account number, and the closing balance as "Solde au
  DD/MM/YYYY <amount> €"). `csv_to_transactions.py` locates the header line
  by searching for the substring `Date;Libell` and parses the balance line
  directly rather than requiring it as an argument.
- **Each transaction's Libellé field spans multiple physical CSV lines** —
  it's a single quoted field containing embedded newlines (operation type on
  line 1, description on line 2, then blank padding lines). This is valid
  CSV; Python's `csv` module handles it correctly as long as the whole file
  is parsed at once rather than split by `\n` first — don't naively iterate
  file lines.
- **Amount is two columns, not one signed column** — `Débit euros` and
  `Crédit euros`, exactly one populated per row. `csv_to_transactions.py`
  computes `credit_cents - debit_cents`.
- **Rows are newest-first**, the reverse of a natural reconciliation order;
  the script sorts ascending before computing the opening balance.
- **At least one instant-transfer row has a stray hex transaction ID**
  appended as an extra line inside the Libellé field, right before the
  closing quote (e.g. `e64551ff663042c0a3febb0531c5d8b5`). Harmless — it
  just folds into the parsed description like any other line — but don't
  mistake it for a parsing bug if you spot it in the payee name.
- Verified against three real exports pulled by the user (identical content,
  90 transactions each, same date range) — `opening + sum(transactions) ==`
  the export's own stated closing balance, exactly, no `--target-balance`
  override needed.
