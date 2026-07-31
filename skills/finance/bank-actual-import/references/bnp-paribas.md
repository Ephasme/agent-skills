# BNP Paribas

Everything specific to BNP Paribas (mabanque.bnpparibas): how its export is replayed in curl, and the traps that cost time. The shared seven-step procedure, the shared gotchas, and the reconciliation step live in [`../SKILL.md`](../SKILL.md).

## Contents

- [Export mechanics](#export-mechanics)
- [Gotchas](#gotchas)

## Export mechanics

- **Cookie scope**: all cookies for `mabanque.bnpparibas` (and its
  subdomains, e.g. `connexion-mabanque.bnpparibas`, `bddf.bnpparibas`). No
  CSRF token and no special header is needed beyond the session cookies —
  every endpoint below (CSV export, relevé listing, relevé download) is a
  plain authenticated GET/POST off the same jar.
  ```bash
  awk -F'\t' 'NF==7 && ($1 ~ /bnpparibas$/)' full_dump.txt > cookies_bnp.txt
  { echo "# Netscape HTTP Cookie File"; cat cookies_bnp.txt; } > jar.txt
  ```
- **Account identifier (`ibanCrypte`)**: an opaque per-account token in the
  account's own URL, e.g.
  `.../releve-d-operations/connected/current-balance?id=...&iban=<THIS>` —
  despite the query param being named `iban` it is *not* a real IBAN, just
  BNP's obfuscated per-account id. It's also present in the URL of
  `virements-services/telechargement-des-operations?iban=<THIS>`, the
  human-facing "Télécharger mes opérations" page this flow replicates.

**The full-history pipeline** (no manual PDF download needed):

1. **Full history via monthly relevé PDFs**, chain-verified month-to-month
   back to the account's true opening date:
   ```bash
   bash scripts/bnp-paribas/fetch_releves.sh --jar jar.txt \
     --iban-crypte <blob> --out-dir releves/
   ```
   This is a genuinely different, much deeper history source than the CSV
   export below — confirmed by testing `dateDebutOperation=01/01/2015`
   against the CSV endpoint and getting the *same* ~13-month window back
   unchanged (a real server-side cap, not a UI default), while the same
   test against the relevé-listing endpoint (`dateDebut` 2010 vs 2016 vs
   2023) genuinely narrowed the returned set until it stopped at this
   account's actual opening month — see the Gotchas below for exactly how
   that was verified.
2. **Bridge to today** via the same 13-month CSV export used standalone
   below — pass it straight through:
   ```bash
   bash scripts/bnp-paribas/fetch_export.sh --jar jar.txt \
     --iban-crypte <blob> --out export.csv
   python3 scripts/bnp-paribas/releves_to_transactions.py \
     --releves-dir releves/ --csv export.csv \
     --target-balance 19138.83 --out transactions.json
   ```
   Only rows dated after the last relevé's closing date are taken from the
   CSV, so the two sources never double-count.
- **Standalone 13-month export** (used alone only if the relevé pipeline
  can't run, or as the bridge source above):
  ```bash
  bash scripts/bnp-paribas/fetch_export.sh --jar jar.txt \
    --iban-crypte <blob> --out export.csv \
    --from 23/06/2025 --to 23/07/2026   # DD/MM/YYYY, max 13 months apart
  python3 scripts/bnp-paribas/csv_to_transactions.py --csv export.csv \
    --target-balance 19138.83 --out transactions.json
  ```
- **This endpoint's 13-month cap is real and server-enforced** — verified by
  requesting `dateDebutOperation=01/01/2015` and getting back the exact same
  byte length / start date as the default request. Don't assume a bank's
  stated UI limit ("13 derniers mois") always means the backend clamps to
  it too; test before documenting a cap as real (Revolut's UI-suggested cap
  turned out to be fake — see its section).

## Gotchas

- **The Angular "Relevé d'Opérations" widget (`ia-rop`) is a red herring for
  scripting.** Its own "Télécharger au format excel" button and the account
  search/pagination all run **entirely client-side** off data already
  fetched once — clicking them fires zero new network requests, so there is
  nothing to replicate there. The real, curl-replicable export lives on a
  *different* page: "Virements et services" → "Télécharger mes opérations"
  (`/fr/secure/virements-services/telechargement-des-operations`), a classic
  multi-step HTML form, not part of the SPA.
- **That download form itself is capped at 13 months** ("dans la limite des
  13 derniers mois") — this is a real product limit, not a bug in this
  skill's request. There is no unlimited-history export like BoursoBank's;
  full account history beyond 13 months only exists as monthly PDF
  statements.
- **The CSV has no header row.** Line 1 is a ~22-field account-metadata line
  (account label repeated, masked account number, statement date, etc.),
  not column names. Real data starts at line 2, 5 fields:
  `date;type;subtype;label;amount`. `csv_to_transactions.py` skips line 1
  unconditionally.
- **No running-balance column at all**, unlike BoursoBank — reconciliation
  can only ever cover the 13-month window actually exported, not the
  account's true history. The computed "opening" transaction is a 13-months-
  ago balance, not an account-opening balance; it's labeled accordingly.
- **Triple HTML-entity-encoding bug on accented characters.** "è" comes
  through as `&amp;amp;amp;egrave;` (encoded three times over one another).
  A single `html.unescape()` pass leaves the string still full of entities;
  `csv_to_transactions.py` unescapes repeatedly until the string stops
  changing.
- Verified end-to-end with a pure-curl GET (no CSRF token, no custom
  headers) against `mabanque.bnpparibas/pfm-telechargerop-wspl/rest/rechercheSoldeMvt`
  using only session cookies — confirmed via a real cookie-jar replay
  (HTTP 200, correct `Content-Disposition: attachment`, matching byte size).
- **Extract the cookie jar with a domain-suffix match, same pattern as the
  other banks**:
  ```bash
  awk -F'\t' 'NF==7 && ($1 ~ /bnpparibas$/)' full_dump.txt > cookies_bnp.txt
  { echo "# Netscape HTTP Cookie File"; cat cookies_bnp.txt; } > jar.txt
  ```
  Real BNP cookie-file domains have no TLD (`.mabanque.bnpparibas`,
  `.connexion-mabanque.bnpparibas`, `.bddf.bnpparibas`, `.api-nav.bddf.bnpparibas`,
  `.psd2-retail.bddf.bnpparibas`, `.content.connexion-mabanque.bnpparibas`) —
  `bnpparibas$` catches all of them in one shot.
- **The known-good authenticated URL for reading balances without guessing**
  is `https://mabanque.bnpparibas/fr/secure/comptes-et-contrats` — it lists
  every account (checking, loans, savings) with its own current balance in
  one page, e.g. `COMPTE DE CHÈQUES N° ****0994 ... Solde créditeur
  19 138,83 €`. It's client-side rendered: the **first** `get_page_text`
  call right after `navigate` can come back with only nav labels (`MES
  COMPTES / MES ASSURANCES / PILOTER MON ÉPARGNE`) before the SPA finishes
  fetching balances — call `get_page_text` again (no re-navigation needed)
  if the first read looks suspiciously empty.
- **Don't guess other `mabanque.bnpparibas` paths** — e.g.
  `/fr/espace-client` or a hand-built
  `/fr/secure/mabanque/releve-d-operations/connected/current-balance?iban=...`
  both 404 with "IMPOSSIBLE D'AFFICHER LA PAGE QUE VOUS RECHERCHEZ...". Only
  navigate to paths actually seen in a tab's real URL (`tabs_context_mcp`)
  or reached via `back`/`forward`.
- **Navigating to the bare root `https://mabanque.bnpparibas/` renders the
  logged-out public marketing site even in an authenticated tab** — this
  looks like the session died but isn't; going `back` from there lands you
  right back on the authenticated page you came from. Don't treat it as a
  signal to ask the user to log in again.
- **Cross-check the account number in the export's own metadata line before
  trusting an `ibanCrypte` grabbed from a URL.** The "Télécharger mes
  opérations" page can serve multiple accounts (checking *and* a personal
  loan, in our case), and the `iban` query param reflects whatever account
  context was last active, not necessarily the one you intend. The CSV's
  line-1 metadata (`"Compte de chèques";"Compte de chèques";****0994;...`)
  states the masked account number — confirm it matches the account you
  meant to fetch (and the balance you read off `comptes-et-contrats`) before
  running `csv_to_transactions.py`.
- **The 13-month cap on the CSV export is real and server-side, not a UI
  default** — proven by re-requesting the exact same endpoint with
  `dateDebutOperation=01/01/2015` and getting back byte-for-byte the same
  ~13-month window as the default request. Contrast with Revolut, where a
  UI-suggested cap turned out to be fake once tested the same way. Always
  test a wider range before writing down "hard cap" as a fact.
- **BNP has a completely separate "Documents et relevés" → "Relevés"
  section with monthly PDF statements going back years further than the
  CSV export** — reached via `demat-wspl/rest/rechercheCriteresDemat` (POST
  `{"dateDebut":"DD/MM/YYYY","dateFin":"DD/MM/YYYY"}`, lists every document
  in that window) and `demat-wspl/rest/consultationDocumentDemat` (GET,
  returns the actual PDF bytes) — both plain cookie-authenticated, same jar
  as the CSV endpoint, no extra auth. Found by clicking through the "Mes
  documents" nav link and capturing the resulting network requests; the
  simple `listerDocuments` GET (no body) only returns a fixed recent window
  (`nbMoisRecuperation` in the response, observed as `"6"`) — the full-range
  POST is a different endpoint entirely.
- **A wide `dateDebut` doesn't error or return empty — it clamps to
  whatever actually exists.** Requesting `dateDebut=01/01/2010` and
  `dateDebut=01/01/2016` both returned the exact same 58 documents starting
  2021-10/11; requesting `dateDebut=01/01/2023` correctly narrowed to just
  that account's statements from Jan 2023 onward. This is how the account's
  *true* opening date (2021-09-22, confirmed by the oldest relevé's own
  "SOLDE CREDITEUR AU 22.09.2021 0,00" opening line) was discovered, rather
  than assumed — always test a deliberately-too-wide range and read back
  what actually comes out, don't trust a UI calendar's leftmost visible
  year as the true boundary (same lesson as Revolut's date picker).
- **Older (2021–2022) relevé PDFs mis-encode "é" as "Ø" in this font** —
  `Débit`/`Crédit` column headers literally extract as `DØbit`/`CrØdit`.
  Column-boundary detection that matches the literal accented string works
  on recent statements and silently returns `None` (no debit/credit split
  at all — every transaction gets treated as a credit) on older ones. Match
  on the encoding-stable tail instead (`endswith('bit')` /
  `endswith('dit')`), which survives regardless of how the accented
  character itself got mangled.
- **This PDF template renders words with ~zero inter-word gap at
  pdfplumber's default word tolerance** — worse than Crédit Agricole's:
  not just thousands-separators, but entire multi-word descriptions come
  back as one jammed token (`"PRLVSEPASYNDICAT35RUECHAMPFLEURY"`). Lowering
  `x_tolerance` to ~2.0 recovers real word boundaries, but then *also*
  over-splits multi-digit numbers on tiny extra digit-to-digit kerning
  (`"35"` → `"3"`,`"5"`; `"18936,01"` → `"18"`,`"936,01"`) — fixed by
  merging adjacent purely-numeric word fragments back together.
- **That digit-fragment merge must happen *within* each already-clustered
  line, not across the whole page's word list in reading order.** Merging
  first (by list order) before clustering into lines glued a real
  transaction amount to an unrelated number from the next line's
  continuation text (`520,88` + `23199,71` → a bogus `520,8823199,71`),
  because the two numbers were close together in the raw word list despite
  belonging to different visual rows. Cluster into lines by `top` first,
  then merge digit fragments only within each line's own word list.
- **No French weekday/month names anywhere in this template** (unlike
  Crédit Agricole) — dates are plain `DD.MM` (transaction rows) or
  `DD.MM.YYYY` (solde markers), no locale parsing needed at all.
- **A single statement can span up to 17 PDF pages** (a busy month, not a
  bug) — the parser scans every page in document order rather than
  assuming the transaction table, `TOTAL DES OPERATIONS`, and closing
  `SOLDE` line all land on page 1; the `Débit`/`Crédit` header only repeats
  on each statement's own first page, so continuation pages reuse the last
  page's known column boundary rather than requiring their own.
- **Never observed a `SOLDE DEBITEUR` (negative balance) across 58 real
  statements** — the parser supports the pattern (it's the same marker with
  the sign flipped) but it's untested against a real one; if a future
  account genuinely goes overdrawn, double-check the sign logic against an
  actual `DEBITEUR` statement rather than trusting it blind.
- **End-to-end verified on this account**: 58 relevés (2021-09-22 →
  2026-07-09) chain-verified with zero drift, bridged by 3 transactions
  from the 13-month CSV export to today, computed opening balance came out
  to exactly 0.00 — genuinely the account's true opening, not an estimated
  placeholder — matching the oldest relevé's own stated opening balance.
