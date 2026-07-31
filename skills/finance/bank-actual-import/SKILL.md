---
name: bank-actual-import
description: >-
  Imports or reconciles a bank account's history into a self-hosted Actual Budget
  instance with exact-cent precision, preferring pure curl calls against the bank (no
  browser clicking, no page-script injection) plus @actual-app/api, and falling back to a
  manual CSV handoff only when a bank's architecture genuinely blocks curl replication.
  Covers BoursoBank (ex-Boursorama), BNP Paribas, Crédit Agricole, and Revolut — each
  with full history back to account opening, and per-bank detail in its own reference
  file. Use when asked to import, sync, or reconcile a bank account (current account,
  Livret A, joint account, kids' accounts) into Actual, especially when the user offers
  cookies or a CSV export, or wants it done "without the browser" or "via the API". For a
  bank not yet covered, follow this skill's pattern — network-inspect the bank's own
  export feature, then replicate it in curl — rather than defaulting to browser
  automation.
compatibility: Requires Node 18+, Python 3, curl, jq, an Actual Budget server with its API and end-to-end encryption passwords, and network access to the bank.
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
  path anymore. See [`references/credit-agricole.md`](references/credit-agricole.md).
- **`revolut/`** — Revolut. Pure curl, full history in a single request: the
  "Statement" CSV export (`fetch_export.sh`,
  `app.revolut.com/api/retail/user/current/statements/account-statements`),
  an async job polled until ready, with its own running balance column
  (like BoursoBank) — no chain-verification across multiple files needed.
  The catch: session cookies alone 401 with a misleading
  `{"message":"Phone and/or passcode are incorrect"}` — every request also
  needs `x-device-id`/`x-hardware-id` headers. See [`references/revolut.md`](references/revolut.md).

## When to use

- "Import my [BoursoBank/BNP Paribas/Crédit Agricole/Revolut] transactions
  into Actual"
- "Reconcile this account's balance exactly"
- The user offers to hand over cookies for a supported bank account (all
  four banks are cookie-jar + pure curl now; Crédit Agricole's CSV export
  is a manual fallback only, see its reference file)
- Off-budget savings (Livret A) or on-budget checking accounts — same flow
  per bank, the export endpoint/file format is generic per account

Not for Enable Banking / open-banking auto-sync (that's a separate,
already-live integration — see the shared Gotchas below about the two
colliding). Not yet wired up for other banks — see "Adding another bank"
at the bottom for how to extend this skill, trying curl replication before
falling back to a manual export.

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
   manual handoff instead — see its reference file for why.
4. Node 18+, Python 3, `curl`, `jq`. Crédit Agricole's and BNP Paribas's
   relevé parsing both need `pdfplumber` in a dedicated venv (see their
   reference files) — the system Python is externally managed and refuses
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

See the bank's reference file (Per-bank detail, below) for the exact domain
pattern and the required cookie names — some cookie names *look* like session
tokens but aren't, verified per bank.

### Step 2 — Find the account identifier

Every bank encodes an account identifier somewhere reachable without
scripting (usually the account's own URL). See the bank's reference file for
where to find it and what it means.

If you can drive the user's already-logged-in browser tab, the easiest way to
get it is navigating to the account and reading the resulting URL — no JS
execution needed, no DOM scraping. Otherwise ask the user to copy the URL.

### Step 3 — Fetch the export

Run the bank-specific `fetch_export.sh`. Each one replays the bank's own
export/download feature purely over HTTP. Crédit Agricole and BNP Paribas
each have two of these instead of one — a `fetch_releves.sh` for full history
via monthly PDF statements, plus the standalone `fetch_export.sh` reused as
the bridge to today — see their reference files.
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
in the account, then inserts the reconciled history). If your agent has a
command-approval layer, expect it to block the `--confirm` run independently —
that's expected, not a bug to route around. Explain the plan (counts, sums,
resulting balance) and get the user's explicit go-ahead before running with
`--confirm`. This part of the skill is entirely bank-agnostic.

### Step 7 — Verify and clean up

The script prints the final transaction count and sum — confirm it matches
the target to the cent. Then delete every artifact that touched live
credentials: the cookie jar, the CSV/QIF export (full transaction history —
treat as sensitive), and any password files you wrote to disk.


## Per-bank detail

The seven steps above are the same for every bank. What differs — cookie
scope, the endpoints, the history depth, and the traps that cost real time —
lives in one file per bank. **Read the one for the bank you are importing,
and only that one.**

| Bank | Detail | Path to full history |
|---|---|---|
| BoursoBank / Boursorama | [`references/boursobank.md`](references/boursobank.md) | One export, no retention cap, own running-balance column |
| BNP Paribas | [`references/bnp-paribas.md`](references/bnp-paribas.md) | Relevé PDFs chain-verified to account opening + the 13-month CSV as the bridge to today |
| Crédit Agricole | [`references/credit-agricole.md`](references/credit-agricole.md) | Relevé PDFs chain-verified + a live operations feed as the bridge; CSV export is a manual fallback |
| Revolut | [`references/revolut.md`](references/revolut.md) | One async "Statement" CSV job, own running-balance column; needs two extra headers |

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
- **Expect a command-approval layer to block the destructive delete+import
  step**, and it should — bulk-deleting a live
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
- **Read-only browser navigation (no clicks, no JS injection) is the right
  way to recover an account identifier or balance you don't already have**,
  and doesn't violate an "API only / no browser interaction" instruction —
  that instruction is about how the *data pull* happens (curl, not scripted
  clicks), not about whether you're allowed to read a URL or rendered text
  off a tab the user is already logged into. Just listing the open tabs
  will tell you if a session looks stale (e.g. a
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

## Adding another bank

When asked to support a bank with no reference file yet:

1. Watch network requests with whatever browser-automation tooling you have —
   a browser MCP server, the devtools protocol, or the browser's own network
   panel with the user reading it out. When the app is an SPA that hides its
   calls behind already-bound `fetch` references, monkey-patching
   `XMLHttpRequest.prototype` / `Response.prototype` from the page console
   surfaces them. Do this while triggering the bank's own
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
