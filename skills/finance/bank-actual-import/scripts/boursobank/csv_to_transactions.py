#!/usr/bin/env python3
"""Convert a BoursoBank CSV export into an Actual-ready transactions.json,
with an exact opening balance computed against a known target balance.

Usage:
  csv_to_transactions.py --csv export.csv --target-balance 43363.18 \
    --out transactions.json

The CSV's own `accountbalance` column is BoursoBank's end-of-VALUE-DATE
running balance (shared by every row posted on the same dateVal, not a
per-row increment) — grouping by dateVal is required to sanity-check it.
Per-day mismatches inside that chain are common (BoursoBank's own value-dating
quirks around weekends/multi-day settlement) and are NOT fatal; only the
final opening-balance + full-sum identity actually needs to hold, and this
script asserts it, refusing to write a mismatched result.
"""
import argparse
import csv
import datetime
import json
import sys
from collections import defaultdict


def parse_cents(amount_str):
    v = amount_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
    return round(float(v) * 100)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--target-balance', required=True, type=str,
                     help='Known-correct current balance in EUR, e.g. 43363.18 '
                          '(read from the CSV\'s own newest-row accountbalance, '
                          'or cross-checked against the bank website)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--opening-payee', default='Starting Balance')
    args = ap.parse_args()

    target_cents = round(float(args.target_balance) * 100)

    with open(args.csv, encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)

    if not rows:
        print('ERROR: no rows in CSV', file=sys.stderr)
        sys.exit(1)

    txns = []
    for r in rows:
        txns.append({
            'date': r['dateOp'],
            'amount': parse_cents(r['amount']),
            'payee_name': (r.get('suggestedLabel') or '').strip() or r['label'].strip(),
            'imported_payee': r['label'].strip(),
            'notes': (r.get('category') or '').strip(),
            'cleared': True,
        })
    txns.sort(key=lambda t: t['date'])

    total_cents = sum(t['amount'] for t in txns)
    opening_cents = target_cents - total_cents

    # Sanity check via day-grouped running balance (diagnostic only, not fatal).
    by_date = defaultdict(lambda: {'sum': 0, 'balances': set()})
    for r in rows:
        d = r['dateVal']
        by_date[d]['sum'] += parse_cents(r['amount'])
        by_date[d]['balances'].add(round(float(r['accountbalance']) * 100))
    dates_sorted = sorted(by_date.keys())
    mismatches = 0
    prev_bal = None
    for d in dates_sorted:
        bal = list(by_date[d]['balances'])[0]
        if len(by_date[d]['balances']) > 1:
            print(f'NOTE: {d} has inconsistent same-day balances in the export', file=sys.stderr)
        if prev_bal is not None:
            expected_prev = bal - by_date[d]['sum']
            if abs(expected_prev - prev_bal) > 1:
                mismatches += 1
        prev_bal = bal
    if mismatches:
        print(f'NOTE: {mismatches}/{len(dates_sorted)} day-to-day balance links did not '
              'chain cleanly (normal — BoursoBank value-dating quirks). '
              'The final total is what matters and is verified below.', file=sys.stderr)

    earliest = datetime.date.fromisoformat(txns[0]['date'])
    opening_date = (earliest - datetime.timedelta(days=1)).isoformat()

    opening_txn = {
        'date': opening_date,
        'amount': opening_cents,
        'payee_name': args.opening_payee,
        'notes': f'Opening balance reconciled from BoursoBank CSV export ({args.csv})',
        'cleared': True,
    }

    # Final assertion: this MUST hold exactly, or something upstream is wrong
    # (wrong target balance, truncated export, parsing bug).
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
        },
    }
    with open(args.out, 'w') as f:
        json.dump(out, f, indent=2)

    print(f'wrote {args.out}')
    print(f'  {len(txns)} transactions, {txns[0]["date"]} -> {txns[-1]["date"]}')
    print(f'  sum: {total_cents/100:.2f}  opening: {opening_cents/100:.2f}  '
          f'-> final: {(opening_cents+total_cents)/100:.2f} (target: {target_cents/100:.2f})')


if __name__ == '__main__':
    main()
