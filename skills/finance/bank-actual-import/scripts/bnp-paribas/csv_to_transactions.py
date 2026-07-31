#!/usr/bin/env python3
"""Convert a BNP Paribas "Télécharger mes opérations" CSV export into an
Actual-ready transactions.json, with an exact opening balance computed
against a known target balance.

Usage:
  csv_to_transactions.py --csv export.csv --target-balance 19138.83 \
    --out transactions.json

Unlike BoursoBank, BNP's CSV carries NO running-balance column and the API
behind the export hard-caps history at 13 months — there is no way to
reconcile further back than that through this endpoint. The computed
"opening" transaction therefore represents the balance 13 months ago (or
wherever the export's earliest row falls), not the account's true opening
balance.

The file has no header row: line 1 is a ~22-field account-metadata line
(account label repeated, masked account number, statement date, etc.) — it
is skipped entirely, real data starts at line 2. Each data line has 5
semicolon-separated fields: date;type;subtype;label;amount.

BNP's export also has a recurring encoding bug: accented characters come
through HTML-entity-encoded, and re-encoded on top of themselves up to three
times (e.g. "è" -> "&egrave;" -> "&amp;egrave;" -> "&amp;amp;amp;egrave;").
Unescaping once is not enough; this script unescapes repeatedly until the
string stops changing.
"""
import argparse
import csv
import datetime
import html
import json
import sys


def unescape_fully(s, max_rounds=5):
    for _ in range(max_rounds):
        new = html.unescape(s)
        if new == s:
            break
        s = new
    return s


def parse_cents(amount_str):
    v = amount_str.replace(' ', '').replace('\xa0', '').replace(',', '.')
    return round(float(v) * 100)


def parse_date(d):
    # DD/MM/YYYY -> YYYY-MM-DD
    dt = datetime.datetime.strptime(d.strip(), '%d/%m/%Y')
    return dt.date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--target-balance', required=True, type=str,
                     help='Known-correct current balance in EUR, read from the '
                          'account synthesis page (this CSV has no balance column).')
    ap.add_argument('--out', required=True)
    ap.add_argument('--opening-payee', default='Starting Balance (13mo window)')
    args = ap.parse_args()

    target_cents = round(float(args.target_balance) * 100)

    with open(args.csv, encoding='utf-8', errors='replace') as f:
        reader = csv.reader(f, delimiter=';')
        rows = list(reader)

    if len(rows) < 2:
        print('ERROR: expected a metadata line plus at least one data row', file=sys.stderr)
        sys.exit(1)

    data_rows = rows[1:]  # skip the account-metadata header line

    txns = []
    for r in data_rows:
        if len(r) < 5:
            continue
        date_str, op_type, op_subtype, label, amount_str = r[0], r[1], r[2], r[3], r[4]
        label = unescape_fully(label).strip()
        op_type = unescape_fully(op_type).strip()
        txns.append({
            'date': parse_date(date_str),
            'amount': parse_cents(amount_str),
            'payee_name': label or op_type,
            'imported_payee': label,
            'notes': op_type,
            'cleared': True,
        })
    txns.sort(key=lambda t: t['date'])

    if not txns:
        print('ERROR: no data rows parsed', file=sys.stderr)
        sys.exit(1)

    total_cents = sum(t['amount'] for t in txns)
    opening_cents = target_cents - total_cents

    earliest = datetime.date.fromisoformat(txns[0]['date'])
    opening_date = (earliest - datetime.timedelta(days=1)).isoformat()

    opening_txn = {
        'date': opening_date,
        'amount': opening_cents,
        'payee_name': args.opening_payee,
        'notes': f'Balance reconciled from BNP Paribas CSV export ({args.csv}); '
                 f'BNP only exposes {13} months of history, so this is NOT the '
                 f'account\'s true opening balance.',
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
            'source': 'bnp-paribas',
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
