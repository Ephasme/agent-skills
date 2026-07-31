#!/usr/bin/env python3
"""Convert a Crédit Agricole "Télécharger mes opérations" CSV export into an
Actual-ready transactions.json.

Usage:
  csv_to_transactions.py --csv export.csv --out transactions.json

Unlike BoursoBank and BNP Paribas, this export has NO pure-curl equivalent:
the download page runs inside a cross-origin iframe (espace-client hosts
telechargement-operations.credit-agricole.fr) that requires a contextId
minted via a parent/child handshake, and the Chrome extension's automation
deliberately does not persist files downloaded via scripted clicks to disk.
The user must click "Télécharger mes opérations" themselves in the browser
and hand over the resulting CSV directly.

Format quirks specific to this export:
- Encoded as Windows-1252 (cp1252), not UTF-8/entity-escaped like BNP.
- A real header row IS present ("Date;Libellé;Débit euros;Crédit euros;"),
  preceded by ~10 lines of boilerplate (download date, account holder,
  account number, and usefully "Solde au DD/MM/YYYY <amount> €" - the exact
  closing balance as of the export, which this script parses directly
  instead of requiring a --target-balance argument like the BNP script does.
- Each transaction's Libellé field is a MULTI-LINE quoted CSV value: line 1
  is the operation type (e.g. "Prélèvement", "Virement en votre faveur"),
  line 2 is the description, followed by several blank padding lines. This
  is valid (if unusual) CSV - Python's csv module parses embedded newlines
  inside a quoted field correctly as long as the whole file is fed to it at
  once rather than line-by-line.
- Amount is split across two columns (Débit euros / Crédit euros) rather
  than a single signed amount column; exactly one is populated per row.
- Rows are in descending chronological order (most recent first).
- At least one instant-transfer row has a stray hex transaction ID appended
  as an extra line inside the Libellé field, just before the closing quote -
  harmless, folded into the description like any other extra line.
"""
import argparse
import csv
import datetime
import io
import json
import re
import sys


def parse_amount_cents(s):
    s = s.strip()
    if not s:
        return 0
    s = s.replace('\xa0', '').replace(' ', '').replace(',', '.')
    return round(float(s) * 100)


def parse_date(d):
    dt = datetime.datetime.strptime(d.strip(), '%d/%m/%Y')
    return dt.date().isoformat()


def clean_label(raw):
    lines = [l.strip() for l in raw.split('\n')]
    lines = [l for l in lines if l]
    op_type = lines[0] if lines else ''
    description = ' '.join(lines[1:]) if len(lines) > 1 else ''
    return op_type, description


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--target-balance', type=str, default=None,
                     help="Override the closing balance instead of parsing it "
                          "from the export's own 'Solde au ...' line.")
    ap.add_argument('--opening-payee', default='Starting Balance')
    args = ap.parse_args()

    with open(args.csv, encoding='cp1252', errors='replace') as f:
        raw = f.read()

    balance_match = re.search(r'Solde au \d{2}/\d{2}/\d{4}\s+([\d\s]+,\d{2})\s*', raw)
    if args.target_balance is not None:
        target_cents = round(float(args.target_balance) * 100)
    elif balance_match:
        target_cents = parse_amount_cents(balance_match.group(1))
    else:
        print('ERROR: could not find "Solde au ..." balance line in the export, '
              'and no --target-balance override was given.', file=sys.stderr)
        sys.exit(1)

    header_idx = raw.find('Date;Libell')
    if header_idx < 0:
        print('ERROR: could not find the "Date;Libellé;..." header row.', file=sys.stderr)
        sys.exit(1)

    body = raw[header_idx:]
    reader = csv.reader(io.StringIO(body), delimiter=';')
    rows = list(reader)
    data_rows = rows[1:]  # skip the header row itself

    txns = []
    for r in data_rows:
        if len(r) < 4 or not r[0].strip():
            continue
        date_str, label_raw, debit_str, credit_str = r[0], r[1], r[2], r[3]
        op_type, description = clean_label(label_raw)
        debit_cents = parse_amount_cents(debit_str)
        credit_cents = parse_amount_cents(credit_str)
        amount = credit_cents - debit_cents
        txns.append({
            'date': parse_date(date_str),
            'amount': amount,
            'payee_name': description or op_type,
            'imported_payee': description,
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
        'notes': f'Balance reconciled from Crédit Agricole CSV export ({args.csv}).',
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
            'source': 'credit-agricole',
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
