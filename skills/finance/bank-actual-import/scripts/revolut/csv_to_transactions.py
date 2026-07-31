#!/usr/bin/env python3
"""Convert a Revolut "Statement" CSV export into an Actual-ready
transactions.json, with an exact opening balance computed against a known
target balance.

Usage:
  csv_to_transactions.py --csv export.csv --target-balance 10865.92 \
    --out transactions.json

--target-balance must be the account's current HEADLINE balance as shown in
the app, INCLUDING pending card holds — not the cleared-only ledger balance.
Revolut's own displayed balance already nets pending transactions in, and
this script keeps them as uncleared (cleared: false) transactions so the
full sum (cleared + uncleared) matches that headline number exactly.

Revolut's CSV has a real header and a running `Balance` column, like
BoursoBank's export — but only on COMPLETED rows:
- COMPLETED: kept as cleared transactions; Balance is a genuine running
  total, verified below.
- PENDING: kept as uncleared transactions (blank Balance — not yet settled).
- REVERTED: dropped entirely. This is an authorization hold that was
  cancelled/reversed and never actually affected the balance (blank
  Balance, like PENDING, but permanently resolved rather than in-flight).

Amount does NOT include Fee — the real effect on the running Balance is
Amount - Fee. Verified against the CSV's own Balance column: chaining
prev_balance + Amount - Fee == Balance holds exactly across every COMPLETED
row in a real 4060-row export; prev_balance + Amount alone does not,
whenever Fee is nonzero (e.g. currency-exchange or ATM fees).
"""
import argparse
import csv
import datetime
import json
import sys


def parse_cents(amount_str):
    return round(float(amount_str) * 100)


def txn_date(row):
    # Completed Date is blank for PENDING rows — fall back to Started Date.
    raw = row['Completed Date'] or row['Started Date']
    return raw.split(' ')[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--target-balance', required=True, type=str,
                     help='Current headline balance in account currency, e.g. 10865.92 '
                          '(the app\'s displayed balance, INCLUDING pending card holds)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--opening-payee', default='Starting Balance')
    args = ap.parse_args()

    target_cents = round(float(args.target_balance) * 100)

    with open(args.csv, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print('ERROR: no rows in CSV', file=sys.stderr)
        sys.exit(1)

    txns = []
    skipped_reverted = 0
    prev_balance_cents = None
    chain_mismatches = 0

    for r in rows:
        state = r['State']
        if state == 'REVERTED':
            skipped_reverted += 1
            continue

        amount_cents = parse_cents(r['Amount'])
        fee_cents = parse_cents(r['Fee']) if r['Fee'] else 0
        net_cents = amount_cents - fee_cents
        cleared = state == 'COMPLETED'

        if cleared and r['Balance']:
            bal_cents = parse_cents(r['Balance'])
            if prev_balance_cents is not None and prev_balance_cents + net_cents != bal_cents:
                chain_mismatches += 1
            prev_balance_cents = bal_cents

        desc = r['Description'].strip()
        notes = r['Type'] if fee_cents == 0 else f"{r['Type']} (fee {fee_cents/100:.2f})"
        txns.append({
            'date': txn_date(r),
            'amount': net_cents,
            'payee_name': desc,
            'imported_payee': desc,
            'notes': notes,
            'cleared': cleared,
        })

    if chain_mismatches:
        print(f'ERROR: {chain_mismatches} COMPLETED-row balance chain link(s) did not '
              'hold (prev_balance + Amount - Fee != Balance). Refusing to write output.',
              file=sys.stderr)
        sys.exit(3)

    txns.sort(key=lambda t: t['date'])

    total_cents = sum(t['amount'] for t in txns)
    opening_cents = target_cents - total_cents

    earliest = datetime.date.fromisoformat(txns[0]['date'])
    opening_date = (earliest - datetime.timedelta(days=1)).isoformat()

    opening_txn = {
        'date': opening_date,
        'amount': opening_cents,
        'payee_name': args.opening_payee,
        'notes': f'Opening balance reconciled from Revolut statement export ({args.csv})',
        'cleared': True,
    }

    check = opening_cents + total_cents
    if check != target_cents:
        print(f'ERROR: opening_cents({opening_cents}) + total_cents({total_cents}) = '
              f'{check}, expected {target_cents}. Refusing to write output.', file=sys.stderr)
        sys.exit(2)

    out = {
        'opening': opening_txn,
        'transactions': txns,
        'meta': {
            'count': len(txns),
            'sum_cents': total_cents,
            'opening_cents': opening_cents,
            'target_cents': target_cents,
            'earliest_date': txns[0]['date'],
            'latest_date': txns[-1]['date'],
            'skipped_reverted': skipped_reverted,
            'source': 'revolut',
        },
    }
    with open(args.out, 'w') as f:
        json.dump(out, f, indent=2)

    print(f'wrote {args.out}')
    print(f'  {len(txns)} transactions ({skipped_reverted} REVERTED rows skipped), '
          f'{txns[0]["date"]} -> {txns[-1]["date"]}')
    print(f'  sum: {total_cents/100:.2f}  opening: {opening_cents/100:.2f}  '
          f'-> final: {(opening_cents+total_cents)/100:.2f} (target: {target_cents/100:.2f})')


if __name__ == '__main__':
    main()
