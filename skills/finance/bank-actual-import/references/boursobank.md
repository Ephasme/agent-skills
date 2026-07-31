# BoursoBank

Everything specific to BoursoBank / Boursorama: how its export is replayed in curl, and the traps that cost time. The shared seven-step procedure, the shared gotchas, and the reconciliation step live in [`../SKILL.md`](../SKILL.md).

## Contents

- [Export mechanics](#export-mechanics)
- [Gotchas](#gotchas)

## Export mechanics

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

## Gotchas

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
