# Revolut

Everything specific to Revolut: how its export is replayed in curl, and the traps that cost time. The shared seven-step procedure, the shared gotchas, and the reconciliation step live in [`../SKILL.md`](../SKILL.md).

## Contents

- [Export mechanics](#export-mechanics)
- [Gotchas](#gotchas)

## Export mechanics

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

## Gotchas

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
