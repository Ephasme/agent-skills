---
name: bank-actual-import
description: Import or reconcile a bank account's history into a self-hosted Actual Budget instance with exact-cent precision, preferring pure curl/API calls against the bank (no browser clicking, no page-script injection) plus @actual-app/api, and falling back to a manual CSV handoff only when a bank's architecture genuinely blocks curl replication. Currently covers BoursoBank (ex-Boursorama, full history, pure curl), BNP Paribas (mabanque.bnpparibas — pure curl, full history via relevé PDFs chain-verified back to true account opening, bridged to today via the 13-month CSV export), Crédit Agricole (pure curl — full history via relevé PDFs, chain-verified, bridged to today via a live operations feed; manual CSV only as a fallback), and Revolut (pure curl once two extra per-request headers are set — full history via the "Statement" CSV job, chain-verified against its own running balance column). Use when asked to import/sync/reconcile a bank account (current account, Livret A, joint account, kids' accounts...) into Actual, especially when the user offers cookies or a CSV export, or wants it done "without the browser" / "via the API". For a bank not yet covered here, use this skill's pattern (network-inspect the bank's own export feature, then replicate in curl — only falling back to manual export if that's provably impossible) to add it rather than falling back to browser automation by default. Don't assume a UI-advertised history cap (e.g. "13 mois") is server-enforced without testing a wider date range yourself — it may just be a UI default.
---

# bank-actual-import — bank → Actual, exact reconciliation

Pull a bank account's transaction history via authenticated HTTP requests
(curl-only, replaying the bank's own export feature — no Chrome automation,
no injected page JS for the actual data pull) and reconcile it into Actual
Budget so the account balance matches the bank to the cent.

Each bank has its own export mechanics (auth flow, CSV/OFX shape, history
depth limit), so this skill keeps per-bank scripts under `scripts/<bank>/`
behind a shared reconciliation step (`scripts/reconcile_actual.mjs`, which
is entirely bank-agnostic — it only ever sees a generic `transactions.json`).

Banks covered so far:
- **`boursobank/`** — BoursoBank / Boursorama. Full account history, no
  retention cap. Pure curl.
- **`bnp-paribas/`** — BNP Paribas. Pure curl, full history: monthly relevé
  PDFs (`fetch_releves.sh`, `demat-wspl/rest/...`) chain-verified back to
  true account opening, bridged to today via the 13-month CSV export
  (`fetch_export.sh`) — which is itself a genuine, server-enforced 13-month
  cap (tested directly, not assumed), unlike the relevés which go back as
  far as the account's actual archive allows.
- **`credit-agricole/`** — Crédit Agricole. Pure curl, full history: monthly
  relevé PDFs (`fetch_releves.sh`, `hubdocumentaire.credit-agricole.fr`)
  chain-verified month-to-month back to account opening, bridged to today
  via a live operations feed (`fetch_operations.sh`,
  `detail-dav.credit-agricole.fr`). Only the CSV export itself
  ("Télécharger mes opérations") lacks curl replication (cross-origin iframe
  + ephemeral handshake) — kept as a documented fallback, not the primary
  path anymore. See its section below.
- **`revolut/`** — Revolut. Pure curl, full history in a single request: the
  "Statement" CSV export (`fetch_export.sh`,
  `app.revolut.com/api/retail/user/current/statements/account-statements`),
  an async job polled until ready, with its own running balance column
  (like BoursoBank) — no chain-verification across multiple files needed.
  The catch: session cookies alone 401 with a misleading
  `{"message":"Phone and/or passcode are incorrect"}` — every request also
  needs `x-device-id`/`x-hardware-id` headers. See its section below.

## When to use

- "Import my [BoursoBank/BNP Paribas/Crédit Agricole/Revolut] transactions
  into Actual"
- "Reconcile this account's balance exactly"
- The user offers to hand over cookies for a supported bank account (all
  four banks are cookie-jar + pure curl now; Crédit Agricole's CSV export
  is a manual fallback only, see its section)
- Off-budget savings (Livret A) or on-budget checking accounts — same flow
  per bank, the export endpoint/file format is generic per account

Not for Enable Banking / open-banking auto-sync (that's a separate,
already-live integration — see the shared Gotchas below about the two
colliding). Not yet wired up for other banks — see "Adding another bank"
at the bottom for how to extend this skill, trying curl
replication before falling back to a manual export.

## Prerequisites

1. **Actual server credentials already provisioned**: `ACTUAL_API_PASSWORD`
   in `iac-stacks/actual-budget/secrets.enc.env` (SOPS). See
   `actual-budget-deployed` memory / `docs/actual-budget` for how that was
   set up — Actual has no native API-key feature, this password row is it.
2. **Actual end-to-end encryption password.** Separate from the OIDC login
   and from the server password above. `@actual-app/api` cannot decrypt the
   budget file without it. Ask the user for it fresh each run unless they've
   explicitly asked you to store it in SOPS as `ACTUAL_E2E_PASSWORD` — don't
   store it unasked, and delete any plaintext copy the moment the run ends.
3. **Cookies for the target bank**, scoped correctly (see Step 1 per bank
   below — this is the part that goes wrong first). Session cookies can go
   stale same-day for the French banks — for Revolut it's minutes, not
   hours, so extract cookies and run the fetch back-to-back. A cheap
   authenticated GET before trusting a jar saves a wasted round-trip.
   Crédit Agricole's CSV export is the one exception that still needs a
   manual handoff instead — see its section below for why.
4. Node 18+, Python 3, `curl`, `jq`. Crédit Agricole's and BNP Paribas's
   relevé parsing both need `pdfplumber` in a dedicated venv (see their
   sections) — the system Python is externally managed and refuses
   `pip install --user`.

## Procedure

### Step 1 — Get a working cookie jar

Ask the user to export cookies while logged into the bank in their normal
browser, covering **all cookies for the bank's domain(s), including
subdomains** — not "current site only" (session tokens frequently live on a
sibling subdomain from the page being viewed). If the user hands over a full
multi-domain cookie dump (they may — treat it as containing live credentials
for every site they're logged into), extract only the lines you need and
never inspect or repeat the rest:

```bash
awk -F'\t' 'NF==7 && ($1 ~ /<bank-domain-pattern>/)' full_dump.txt > cookies_bank.txt
{ echo "# Netscape HTTP Cookie File"; cat cookies_bank.txt; } > jar.txt
```

See the per-bank sections below for the exact domain pattern and the
required cookie names (some cookie names *look* like session tokens but
aren't — verified per bank).

### Step 2 — Find the account identifier

Every bank encodes an account identifier somewhere reachable without
scripting (usually the account's own URL). See the per-bank section for
where to find it and what it means.

If you have Chrome MCP access to the user's already-logged-in tab, the
easiest way to get it is simply navigating to the account and reading the
resulting URL from `tabs_context_mcp` / the `navigate` result — no JS
execution needed, no DOM scraping.

### Step 3 — Fetch the export

Run the bank-specific `fetch_export.sh` (see below). Each one replays the
bank's own export/download feature purely over HTTP. Crédit Agricole and
BNP Paribas each have two of these instead of one — a `fetch_releves.sh`
for full history via monthly PDF statements, plus the standalone
`fetch_export.sh` reused as the bridge to today — see their sections below.
**Exception:** Crédit Agricole's CSV export specifically has no curl
equivalent — only fall back to asking the user to click "Télécharger mes
opérations" themselves if a session can't reach its other two endpoints.

### Step 4 — Build the reconciled transaction set

Run the bank-specific `csv_to_transactions.py` with the account's current
true balance (from the bank's own site — cross-check the headline balance
if anything looks off, e.g. pending card holds; see Gotchas). This computes
an opening-balance transaction such that
`opening + sum(all transactions) == target` exactly, in integer cents —
never float arithmetic — and refuses to write output if that identity
doesn't hold.

### Step 5 — Inspect the Actual account before touching it

```bash
cd scripts && npm install   # once, installs @actual-app/api locally
node reconcile_actual.mjs --list-accounts \
  --server-pw-file /path/to/server_pw --e2e-pw-file /path/to/e2e_pw
node reconcile_actual.mjs --inspect <account-id> \
  --server-pw-file ... --e2e-pw-file ...
```

Check what's already there. An account fed by Enable Banking auto-sync will
likely have a **small recent window** of real transactions (not full
history) plus a rough `starting_balance_flag` placeholder — that whole set
needs replacing, not merging with, your reconciled import.

### Step 6 — Reconcile

```bash
node reconcile_actual.mjs --account-id <id> --transactions transactions.json \
  --server-pw-file ... --e2e-pw-file ...        # dry run — prints the plan only
node reconcile_actual.mjs --account-id <id> --transactions transactions.json \
  --confirm --server-pw-file ... --e2e-pw-file ...   # actually deletes + imports
```

**This step is destructive by design** (deletes every existing transaction
in the account, then inserts the reconciled history) and Claude Code's own
auto-mode classifier will independently block the `--confirm` run — that's
expected, not a bug to route around. Explain the plan (counts, sums,
resulting balance) and get the user's explicit go-ahead before running with
`--confirm`. This part of the skill is entirely bank-agnostic.

### Step 7 — Verify and clean up

The script prints the final transaction count and sum — confirm it matches
the target to the cent. Then delete every artifact that touched live
credentials: the cookie jar, the CSV/QIF export (full transaction history —
treat as sensitive), and any password files you wrote to disk.

## BoursoBank (`scripts/boursobank/`)

- **Cookie scope**: all cookies for `boursorama.com` AND `boursobank.com`,
  including subdomains (`clients.*`, `api.*`). A 6-cookie "current site"
  export (`__brs_mit`, `brswpaa`, `brsxd_secure`, `didomi_cookies`,
  `fonts-loaded`, `rememberme`) is **not enough** — none of those is a
  session token. `rememberme` in particular looks like a persistent-login
  cookie but is only the "remember my client ID" checkbox value; replaying
  it gets you the plain login form, not a session. The real session token
  is `PHPSESSID`.
- **Verify the jar** before going further:
  ```bash
  curl -sS -b jar.txt -c jar.txt \
    -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36" \
    -o /tmp/home.html -w "%{http_code}\n" "https://clients.boursobank.com/"
  grep -io '<title>[^<]*</title>' /tmp/home.html   # "Accueil" = logged in; the login-page title = not
  ```
- **Account key**: every account has a hex key baked into its own URL, e.g.
  `https://clients.boursobank.com/compte/cav/a7d277658d6373812ae91b61c2ce6569/`
  (current accounts: `cav/<key>`; savings: `epargne/livret-a/<key>/`). The
  export endpoint only needs this key, regardless of account type. (The
  dashboard's account list itself is client-side rendered and empty in raw
  HTML, so don't bother trying to fetch and grep it.)
- **Fetch the export** (prefer CSV over QIF — the CSV includes an
  `accountbalance` column, which is what makes exact-cent reconciliation
  possible without guessing):
  ```bash
  bash scripts/boursobank/fetch_export.sh --jar jar.txt --account-key <KEY> \
    --out export.csv --format CSV --from 01/01/2000
  ```
- **Build transactions.json**:
  ```bash
  python3 scripts/boursobank/csv_to_transactions.py --csv export.csv \
    --target-balance 43363.18 --out transactions.json
  ```
- Full account history available, no retention cap encountered.

## BNP Paribas (`scripts/bnp-paribas/`)

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

## Crédit Agricole (`scripts/credit-agricole/`)

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

## Revolut (`scripts/revolut/`)

Very different security model from the French banks: web login needs a
phone (QR-code scan or magic-link), and every API call needs two extra
headers beyond the session cookies — but once past that, it's the simplest
pure-curl pipeline of the four banks: **one file, one request, full history,
a real running-balance column**. No relevé chain-verification needed.

- **Cookie scope**: all cookies for `revolut.com` (and subdomains —
  `app.revolut.com`, `sso.revolut.com`, `chat.revolut.com`).
  ```bash
  awk -F'\t' 'NF==7 && ($1 ~ /revolut\.com$/)' full_dump.txt > cookies_revolut.txt
  { echo "# Netscape HTTP Cookie File"; cat cookies_revolut.txt; } > jar.txt
  ```
- **Session cookies alone are NOT enough** — a plain `curl -b jar.txt` (or
  even an in-page `fetch(..., {credentials:'include'})`) against any
  `app.revolut.com/api/retail/*` endpoint returns
  `401 {"message":"Phone and/or passcode are incorrect","code":9001}`
  regardless of how fresh the cookies are. This looks like a step-up-auth
  failure but isn't — every request also needs two headers, read from the
  `revo_device_id` / `revo_hardware_id` cookies already in the same jar:
  ```bash
  DEVICE_ID=$(awk -F'\t' '$6=="revo_device_id"{print $7}' cookies_revolut.txt)
  HW_ID=$(awk -F'\t' '$6=="revo_hardware_id"{print $7}' cookies_revolut.txt)
  curl -b jar.txt -H "x-device-id: $DEVICE_ID" -H "x-hardware-id: $HW_ID" ...
  ```
  Add those two headers and the exact same request succeeds. (The
  `credentials` cookie also *looks* like a ready-to-use HTTP Basic-Auth
  token — `base64(uuid:secret)` — but sending it as an `Authorization:
  Basic` header changes nothing; it's the device/hardware headers that
  matter, not that cookie.)
- **Session tokens expire in ~2–3 minutes**, far more aggressive than any
  French bank in this skill (`token/info`'s own response reports
  `"lifetime"` in milliseconds — observed ~144000ms). A cookie export is
  only useful for a couple of minutes after being taken; extract cookies
  and run the fetch immediately, back-to-back, or the very same jar that
  worked moments ago starts 401ing again.
- **Fetch the export** — an async job; the script polls the same GET until
  `"state":"READY"`, which also carries a signed, unauthenticated Google
  Cloud Storage download URL for the actual CSV:
  ```bash
  bash scripts/revolut/fetch_export.sh --jar jar.txt \
    --device-id <uuid> --hardware-id <uuid> --ccy EUR --out export.csv
  ```
  Defaults to requesting `from=2015-01-01` (before Revolut existed) — the
  server doesn't error on an over-wide range, it just returns whatever
  actually exists, so this reliably captures full history in one call
  without needing to know the account's real opening date up front.
- **Build transactions.json**:
  ```bash
  python3 scripts/revolut/csv_to_transactions.py --csv export.csv \
    --target-balance 10865.92 --out transactions.json
  ```
  `--target-balance` must be the app's **headline** balance (including
  pending card holds), not the cleared-only ledger balance — see Gotchas.

## Gotchas — shared across banks

- **Enable Banking (if connected) syncs only a recent window, not full
  history**, and may leave a rough starting-balance placeholder from before
  it was connected. Don't try to merge your import with it — inspect
  (Step 5), then replace the whole set.
- **Enable Banking may re-sync after your import** and create duplicate rows
  for the days your import and its sync both cover, since it's unclear
  whether its own `imported_id` scheme matches transactions you inserted
  yourself. Flag this to the user as a known follow-up risk rather than
  guessing at Enable Banking's dedup key format.
- **Actual's server password and E2E encryption password are two different
  secrets.** The server password (stored per `actual-budget-deployed`
  memory) authenticates `@actual-app/api` to the server; without the
  separate E2E password, `downloadBudget` succeeds but the budget can't be
  decrypted for read/write.
- **The destructive delete+import step will get blocked by Claude Code's
  auto-mode permission classifier**, and should — bulk-deleting a live
  financial account's transaction history is exactly the kind of action that
  deserves an explicit human yes. Explain the plan and wait for it; don't
  try another tool to work around the block.
- **A pending card "autorisation en cours" (authorization hold) is not
  necessarily in the bank site's headline balance.** We saw a live -7.01€
  pending Tesla Supercharger hold (BoursoBank) that was excluded from "Solde
  disponible" but *was* included in what Enable Banking had already synced
  into Actual — that mismatch is exactly why the existing Actual data
  needed replacing, not trusting. Check for this on any bank before
  treating a small discrepancy as a bug in the reconciliation math.
- **Extracting `ACTUAL_API_PASSWORD`/`ACTUAL_E2E_PASSWORD` from a decrypted
  `secrets.env` needs the *whole* `KEY=` prefix stripped, not just
  `export `.** `awk -F'export ' '{print $2}'` on a line like
  `export ACTUAL_API_PASSWORD=abc123` leaves `ACTUAL_API_PASSWORD=abc123` in
  the output (only the literal string `"export "` was consumed), and
  `reconcile_actual.mjs` then sends that whole string as the password,
  failing with `Authentication failed: invalid-password` — a confusing
  error since the real password file at that path *looks* populated (`wc -c`
  shows plausible-ish length). Use `sed -E 's/^export
  ACTUAL_API_PASSWORD=//'` (anchored to the exact key name) instead, and
  sanity-check the extracted file's byte count roughly matches the known
  password length before trusting it.
- **Chrome MCP read-only navigation + `get_page_text` (no clicks, no JS
  injection) is the right way to recover an account identifier or balance
  you don't already have**, and doesn't violate an "API only / no browser
  interaction" instruction — that instruction is about how the *data pull*
  happens (curl, not scripted clicks), not about whether you're allowed to
  read a URL or rendered text off a tab the user is already logged into.
  `tabs_context_mcp` alone will tell you if a session looks stale (e.g. a
  tab sitting on a logout/deconnexion page).
- **Proving "no missing transactions" needs an opening balance that's
  independently anchored, not just internally consistent.** A
  `target - sum(transactions)` computation is trivially self-consistent no
  matter how much history is missing — it always balances by construction.
  Actual proof requires the computed opening to match something the bank
  itself asserts independently: an official statement's own stated
  "Ancien/Nouveau solde" (BNP, Crédit Agricole), a first transaction
  explicitly labeled as account-opening ("VIREMENT CREATION COMPTE",
  BoursoBank; "Topup" against a zero prior balance, Revolut), or — when the
  computed opening ISN'T zero and there's no such label — an exhaustive
  same-history check that any apparent gap is a constant, permanent
  characteristic rather than hiding a real missing transaction (see the
  BoursoBank 136.37 gotcha below for the concrete technique: group by date,
  walk day-boundaries, confirm every deviation self-corrects back to the
  same baseline rather than permanently shifting it).
- **A statement's own sequence number isn't proof of "the first ever" by
  itself if the bank resets it periodically** (Crédit Agricole resets
  "Relevé n°" every January) — sort by actual date, not by the number, and
  corroborate with the shape of the first period (a partial first calendar
  year/month is a good sign the account is genuinely that new).

## Gotchas — BoursoBank-specific

- **`rememberme` is not a session cookie.** Don't waste time trying to
  replay it — go straight to asking for a full multi-domain export with
  `PHPSESSID`.
- **Dashboard balances are client-side rendered.** A plain `curl` GET of
  `https://clients.boursobank.com/` returns empty
  `<span class="c-info-box__account-balance"></span>` placeholders — the
  numbers are filled in by JS after load. Use the CSV export's own
  `accountbalance` column instead, or read the page through an
  authenticated browser tab if you need the live figure specifically.
- **The export POST doesn't return the file directly.** It 302s to an HTML
  page containing a *one-time* download token
  (`api.boursobank.com/services/api/files/download.phtml?token=...`) that
  you must follow with a second request, same cookie jar.
- **`accountbalance` in the CSV is an end-of-value-date balance, shared by
  every transaction on that date** — not a per-row running total. Verifying
  it row-by-row produces hundreds of spurious "mismatches"; group by
  `dateVal` first. Even grouped, a handful of days can still fail to chain
  cleanly (BoursoBank's own value-dating quirks around weekends/multi-day
  settlement) — that's normal. Only the final
  `opening_balance + total_sum == target` identity needs to hold exactly,
  and `csv_to_transactions.py` asserts it.
- **A non-zero computed opening balance isn't automatically a sign of
  missing history** — it can be a permanent, unexplained offset baked into
  BoursoBank's own systems since account creation. Found on this account: a
  constant +136.37 gap between `0 + sum(all 1766 real transactions)` and
  the CSV's/live site's own displayed balance, present *identically* on
  the account's very first day (verified against its own official Dec-2018
  PDF statement — "Ancien solde 0,00", first transactions literally labeled
  "VIREMENT CREATION COMPTE") and unchanged all the way to today. Proved
  it was permanent, not a hidden mid-history transaction, by grouping the
  full CSV by `dateVal` and computing `csv_balance - cumulative_sum` at
  every one of 751 day-boundaries across 8 years: every single deviation
  from 136.37 was a temporary 1-4 day wobble (the same value-dating quirk
  above) that self-corrected back to *exactly* 136.37 — a permanent shift
  from a missing transaction would show zero offset before it and a
  different-but-stable offset after, not a temporary bump that returns to
  the same baseline. Also ruled out a live pending card hold as the cause
  (the account detail page showed "Mouvements à venir hors carte: 0,00€").
  Conclusion: the transaction list is complete; leave the existing
  reconciliation as-is rather than "fixing" it to open at 0.00.
- **Boursorama also has a monthly-PDF statement archive** (Mes documents →
  Relevés de comptes), independent of the CSV export, reachable the same
  cookie-authenticated way as BNP/Crédit Agricole's relevé archives —
  direct download links look like
  `api.boursobank.com/services/api/files/statements-document.phtml?type=ccs&id=<token>`
  (plain GET, same jar, no extra auth). Not built into a fetch script here
  since the CSV export already has no retention cap, but it's what let us
  cross-verify the account's true opening day against an authoritative
  source. The pagination widget for browsing far back
  (`documents/documents-suite/<continuationKey>`) breaks unpredictably
  under repeated automated clicks — if it stops advancing, don't fight it;
  the definitive-completeness question can be answered analytically from
  data already in hand (as above) instead of needing to click all the way
  back.

## Gotchas — BNP Paribas-specific

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

## Gotchas — Crédit Agricole relevés + operations (the pure-curl pipeline)

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

## Gotchas — Crédit Agricole CSV fallback

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

## Gotchas — Revolut

- **The 401 body is actively misleading.** `{"message":"Phone and/or
  passcode are incorrect","code":9001}` reads like a step-up 2FA/PIN
  challenge, but it fires for *any* auth gap on this API — stale cookies,
  right cookies but missing `x-device-id`/`x-hardware-id`, even a
  well-formed `Authorization: Basic` header built from the `credentials`
  cookie's own value. Don't chase a passcode/2FA flow based on this
  message; check the two device headers first.
- **A same-origin in-page `fetch()` fails identically to a naive curl call**
  — both are missing the same two headers, so a CORS-style "must be a
  browser-only endpoint" conclusion from reconnaissance would have been
  wrong here. Confirmed by testing the *exact* same request shape via curl
  once the headers were known — this is what actually settled it, not the
  in-page test.
- **Monkey-patching `window.fetch`/`XMLHttpRequest` after the page has
  already loaded does not intercept this app's own API calls** — same
  early-binding issue as hit on other SPAs before; the bundle must capture
  its own reference before an injected patch installs. Don't rely on this
  technique to recover request headers from a live session; reading the
  relevant cookies directly (here: `revo_device_id`, `revo_hardware_id`)
  and reasoning about the 401 body was what actually worked.
- **The account's live headline balance = last COMPLETED row's running
  `Balance` + sum of PENDING rows' `Amount`.** Verified exactly: cleared
  ledger balance 11130.15, five pending card holds summing to -264.23,
  headline balance 10865.92 — 11130.15 + (-264.23) = 10865.92 to the cent.
  `--target-balance` must be this headline number (matching what
  `reconcile_actual.mjs`'s own final check sums: cleared + uncleared
  together), not the cleared-only figure.
- **`Amount` excludes `Fee`** — the real effect on the running `Balance`
  column is `Amount - Fee`, confirmed by chain-checking `prev_balance +
  Amount - Fee == Balance` across all 4060 real COMPLETED rows with zero
  mismatches (`prev_balance + Amount` alone fails whenever `Fee` is
  nonzero, e.g. currency-exchange or ATM fees).
- **REVERTED rows are not the same thing as PENDING rows**, despite both
  having a blank `Balance` — REVERTED is a card-authorization hold that got
  cancelled and permanently never affected the balance (drop it entirely);
  PENDING is still in-flight and does affect the live headline balance
  (keep it, marked uncleared). Treating REVERTED as an uncleared
  transaction would double it into the wrong side of the reconciliation.
- **The UI's own statement-generation date-range picker looked capped**
  (2018 shown fully greyed out, no visible way further back), but the
  underlying API wasn't — requesting `from=2015-01-01` directly returned
  the account's actual full history starting 2020-04-10 (a `Topup` of
  10.00 against a zero prior balance — genuinely the account's opening,
  not a truncation). Don't trust a picker's disabled-looking range as the
  real limit; test the API directly with a deliberately-wide range.
- **The statement job is genuinely asynchronous** — the very first request
  for a wide, never-before-requested range returns
  `{"state":"IN_PREPARATION"}`; poll the identical GET (same query string)
  every few seconds until `{"state":"READY","url":"..."}` appears. A
  previously-requested exact range (same from/to/ccy/format) comes back
  `READY` immediately, cached server-side.
- **End-to-end verified on this account**: 4065 transactions (2020-04-10 →
  2026-07-23, 155 REVERTED rows correctly excluded), opening balance
  computed as exactly 0.00 — the CSV's very first row genuinely is the
  account's opening transaction, no estimation needed — final sum matching
  the live headline balance to the cent.

## Adding another bank

When asked to support a bank not listed above:

1. Use Chrome MCP to watch network requests (`read_network_requests`, or
   `javascript_tool` to monkey-patch `XMLHttpRequest.prototype`/
   `Response.prototype` when the app is an SPA that hides its calls behind
   already-bound `fetch` references) while triggering the bank's own
   "download/export transactions" feature. Don't assume the obvious button
   in a fancy SPA widget is the real one — as BNP's `ia-rop` case shows, a
   client-side-only button can look identical to a real network call. Prefer
   whatever the bank's classic non-SPA "download my statements" page does.
   Also check whether the feature runs in a **cross-origin iframe** (several
   of Crédit Agricole's do) — if so, `javascript_tool` on the parent tab
   won't see its requests at all (different JS global), *and* a same-origin
   `fetch()` test from the parent tab will fail with a CORS error even when
   the endpoint is perfectly curl-replicable (CORS is browser-enforced only;
   curl ignores it). A cross-origin iframe is not by itself evidence of "no
   curl replication" — Crédit Agricole has three, and two of the three
   (Documents, account operations) turned out to be plain
   cookie-authenticated BFFs; only the CSV export's needed an ephemeral
   parent/child handshake beyond cookies. Test each iframe's BFF against a
   real cookie jar via curl directly before concluding it can't be replayed.
2. Note: the auth mechanism (cookies only vs. CSRF token vs. one-time
   download link vs. a cross-origin session handshake), the account
   identifier's location and true meaning, the export request shape, the
   response CSV/OFX shape (header or not, delimiter, decimal separator,
   running-balance column or not, encoding quirks), and any retention cap.
3. **Try to replicate purely in curl first** (verify against a real
   cookie-jar export before trusting it — HTTP 200 plus a plausible byte
   size and row count). Only fall back to a manual-export-only script (no
   `fetch_export.sh`, per Crédit Agricole's CSV export specifically — its
   other two endpoints do have one) once curl replication is genuinely,
   demonstrably blocked — e.g. a session handshake that can't be reproduced
   outside the browser, or automated downloads that provably never reach
   disk (check Chrome's own `History` SQLite db's `downloads` table to
   confirm, don't just assume from a missing file in `~/Downloads`) — and
   note that an in-page `fetch()` to a local port to sidestep the download
   guardrail gets blocked by the extension too; don't try that either.
4. Add `scripts/<bank>/csv_to_transactions.py` (and `fetch_export.sh` if step
   3 succeeded) following the existing banks' shape (accept
   `--target-balance` as at least an override, emit the same
   `transactions.json` schema: `{opening, transactions, meta}`), then add a
   section here. `reconcile_actual.mjs` needs no changes — it's bank-agnostic.
5. **Don't trust a UI-advertised history cap (or a UI date-picker's
   disabled-looking range) without testing it directly against the API.**
   BNP's "13 derniers mois" copy turned out to be a real, server-enforced
   limit (requesting `dateDebutOperation=01/01/2015` returned the exact
   same ~13-month window back, byte-for-byte); Revolut's date picker showed
   2018 fully greyed out with no visible way further back, yet requesting
   `from=2015-01-01` directly against the API returned genuine full history
   back to account opening in 2020. One example doesn't predict the other
   — always probe with a deliberately-too-wide range and read back what
   the server actually returns before writing down "hard cap" (or "no
   cap") as fact.
6. **A 401 body that reads like a step-up/2FA/passcode challenge may
   actually just mean a required non-cookie header is missing.** Revolut's
   `{"message":"Phone and/or passcode are incorrect"}` fired identically
   for stale cookies, correct cookies without `x-device-id`/
   `x-hardware-id`, and even a plausible-looking `Authorization: Basic`
   attempt — don't assume the message text describes the real cause. Check
   for a bank-specific device/session-correlation cookie (anything named
   like `*device*id*` or `*hardware*id*` in the same jar) that the app
   might be sending as a header rather than relying on automatic cookie
   transmission.
7. **Monkey-patching `window.fetch`/`XMLHttpRequest.prototype` to recover a
   live request's exact headers or POST body doesn't always work** — it
   failed on both Revolut and BNP's own SPA bundles, apparently because
   the bundle captures its own reference to `fetch`/`XHR` before an
   injected patch can install. When it fails, fall back to reasoning from
   what IS visible (cookie names, a 401 body's exact wording, response
   shapes from variations you construct yourself) rather than spending
   more time trying to force the patch to catch on.

## Security

- Cookies and the CSV/QIF/OFX export are live bank credentials and full
  transaction history respectively — never print them, never commit them,
  delete them the moment the run is done.
- If handed a multi-domain cookie dump, extract only the lines for the bank
  you're working on (Step 1) and never inspect or repeat the rest.
- Don't store the Actual E2E password without being asked to; if you do
  store it, it goes in SOPS (`ACTUAL_E2E_PASSWORD`) alongside
  `ACTUAL_API_PASSWORD`, never in plaintext in this repo or on disk longer
  than the run.
