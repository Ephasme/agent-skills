#!/usr/bin/env python3
"""Parse a directory of Crédit Agricole "Relevé de compte" PDFs (fetched via
fetch_releves.sh) into a single, chain-verified Actual-ready transactions.json
covering the account's full history — then bridge the gap between the last
relevé's closing date and today using the account's live operations feed
(fetch_operations.sh), or a manually-exported CSV as a fallback (see
csv_to_transactions.py).

Requires pdfplumber: ../.venv/bin/python3 releves_to_transactions.py ...
(../.venv is a dedicated venv — this account's system Python is externally
managed (PEP 668) and has no pdfplumber; `pip3 install --user` is refused.)

Usage:
  releves_to_transactions.py --releves-dir releves/ \
      --operations-json operations.json --out transactions.json
  # or, without a live session:
  releves_to_transactions.py --releves-dir releves/ --csv export.csv \
      --out transactions.json

The operations feed (fetch_operations.sh, detail-dav.credit-agricole.fr) is
preferred over the CSV: same ~12-month rolling window, but pure curl (no
manual browser export) and already-signed amounts (no debit/credit column
guessing, no cp1252/HTML-entity quirks). It does not itself state a "solde
au ..." closing balance the way the CSV does, so with --operations-json the
target balance must come from --target-balance (e.g. the live balance shown
on the account page) rather than being parsed out of the feed.

Why PDFs at all, and why parse them this way:
- The CSV export ("Télécharger mes opérations") caps history at ~12 months.
  Relevés go back to account opening (in this account's case, to Nov 2023),
  and each one carries its own opening ("Ancien solde") and closing
  ("Nouveau solde") balance — letting every single month be chain-verified
  (closing[n] == opening[n+1]) instead of trusting one final number.
- The PDF's plain extracted text collapses the Débit/Crédit table into one
  stream with no column information — every row ends in the same decorative
  glyph regardless of debit or credit. Only the x-position of each word
  (via pdfplumber's extract_words, upright words only — the page also has a
  vertical barcode-like column of digits down the left margin at a fixed x0
  that must be excluded) recovers which column an amount fell in. The
  Débit/Crédit header's own x-positions set the column boundary per
  statement rather than hardcoding a pixel value, in case the template
  shifts across the account's ~2.5-year history.
- pdfplumber's word tokenizer splits amounts on the thousands-separator
  space ("2 215,90" -> "2" + "215,90") — merge_amount_tokens reassembles
  them before the amount regex runs.
- A long transaction description sometimes wraps onto a following line with
  no leading dates (seen on real statements, e.g. an extra "Default" line or
  a stray end-to-end transfer reference) — any line that doesn't start with
  two `DD.MM` date tokens is folded into the previous transaction's
  description instead of starting a new one.
- Transaction dates are `DD.MM` with no year; the year is resolved against
  each statement's own Ancien/Nouveau solde dates (which do carry a year),
  handling the Dec->Jan rollover at a statement's boundary.
- Checked against all 33 real statements on this account (Nov 2023 - Jul
  2026): 10 of them spread onto a 2nd PDF page, but in every case that's
  legal boilerplate overflow — the full transaction table, Total des
  opérations, and Nouveau solde always land on page 1. The parser still
  walks pages in order and only trusts the Ancien-solde/Total-des-opérations
  markers to bound the transaction region, so a statement that genuinely
  needed a 2nd transactions page would still parse correctly; it just
  hasn't been observed on this account.
"""
import argparse
import datetime
import glob
import json
import os
import re
import subprocess
import sys

import pdfplumber

SOLDE_RE = re.compile(r'^(Ancien|Nouveau) solde (créditeur|débiteur) au (\d{2}\.\d{2}\.\d{4})')
DATE_TOKEN_RE = re.compile(r'^\d{2}\.\d{2}$')
AMOUNT_RE = re.compile(r'^[\d ]+,\d{2}$')
DECORATIVE = {'¨', 'þ'}


def parse_fr_amount(s):
    s = s.strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    return round(float(s) * 100)


def cluster_lines(words, tol=3.0):
    """Group words into visual rows by y ('top'), tolerating the few-pixel
    baseline jitter PDF generators introduce between a label and a number
    meant to sit on the same row (observed: a balance amount landing ~1-2pt
    off from its 'Ancien solde'/'Nouveau solde' label)."""
    words = sorted(words, key=lambda w: (w['top'], w['x0']))
    lines, cur, cur_top = [], [], None
    for w in words:
        if cur_top is None or abs(w['top'] - cur_top) <= tol:
            cur.append(w)
            cur_top = sum(x['top'] for x in cur) / len(cur)
        else:
            lines.append(cur)
            cur, cur_top = [w], w['top']
    if cur:
        lines.append(cur)
    return [sorted(l, key=lambda w: w['x0']) for l in lines]


def merge_amount_tokens(tokens):
    merged = []
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if (i + 1 < len(tokens)
                and re.fullmatch(r'\d{1,3}', t['text'])
                and re.fullmatch(r'\d{3},\d{2}', tokens[i + 1]['text'])
                and tokens[i + 1]['x0'] - t['x1'] < 15):
            combined = dict(t)
            combined['text'] = t['text'] + ' ' + tokens[i + 1]['text']
            combined['x1'] = tokens[i + 1]['x1']
            merged.append(combined)
            i += 2
        else:
            merged.append(t)
            i += 1
    return merged


def parse_statement(pdf_path):
    all_lines = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = [w for w in page.extract_words() if w['upright']]
            for line in cluster_lines(words):
                all_lines.append(merge_amount_tokens(line))

    threshold = None
    for line in all_lines:
        texts = [w['text'] for w in line]
        if 'Débit' in texts and 'Crédit' in texts:
            debit_x = next(w['x0'] for w in line if w['text'] == 'Débit')
            credit_x = next(w['x0'] for w in line if w['text'] == 'Crédit')
            threshold = (debit_x + credit_x) / 2
            break
    if threshold is None:
        raise ValueError(f"{pdf_path}: couldn't find the Débit/Crédit column header")

    ancien = nouveau = None
    total_debit_cents = total_credit_cents = None
    tx_lines = []
    state = 'before'
    for line in all_lines:
        text = ' '.join(w['text'] for w in line)
        m = SOLDE_RE.match(text)
        if m:
            kind, sign, datestr = m.groups()
            val = parse_fr_amount(line[-1]['text'])
            if sign == 'débiteur':
                val = -val
            if kind == 'Ancien':
                ancien = (datestr, val)
                state = 'in'
            else:
                nouveau = (datestr, val)
                state = 'after'
            continue
        if text.startswith('Total des opérations'):
            nums = [w['text'] for w in line if AMOUNT_RE.match(w['text'])]
            if len(nums) >= 2:
                total_debit_cents = parse_fr_amount(nums[0])
                total_credit_cents = parse_fr_amount(nums[1])
            state = 'after'
            continue
        if state == 'in':
            tx_lines.append(line)

    if ancien is None or nouveau is None:
        raise ValueError(f"{pdf_path}: missing Ancien solde / Nouveau solde marker")

    txns = []
    cur = None
    for line in tx_lines:
        if len(line) >= 2 and DATE_TOKEN_RE.match(line[0]['text']) and DATE_TOKEN_RE.match(line[1]['text']):
            if cur:
                txns.append(cur)
            rest = line[2:]
            amount_idx = next((i for i, w in enumerate(rest) if AMOUNT_RE.match(w['text'])), None)
            if amount_idx is None:
                raise ValueError(f"{pdf_path}: no amount found on transaction line: {text}")
            amount_tok = rest[amount_idx]
            desc = ' '.join(w['text'] for w in rest[:amount_idx])
            amt = parse_fr_amount(amount_tok['text'])
            is_credit = amount_tok['x0'] >= threshold
            cur = {
                'date_val': line[1]['text'],
                'type': rest[0]['text'] if rest[:amount_idx] else '',
                'description': desc,
                'amount': amt if is_credit else -amt,
            }
        else:
            if cur is not None:
                extra = ' '.join(w['text'] for w in line if w['text'] not in DECORATIVE)
                if extra:
                    cur['description'] += ' ' + extra
    if cur:
        txns.append(cur)

    debit_sum = sum(-t['amount'] for t in txns if t['amount'] < 0)
    credit_sum = sum(t['amount'] for t in txns if t['amount'] > 0)
    if total_debit_cents is not None and debit_sum != total_debit_cents:
        raise ValueError(f"{pdf_path}: debit sum {debit_sum} != stated total {total_debit_cents}")
    if total_credit_cents is not None and credit_sum != total_credit_cents:
        raise ValueError(f"{pdf_path}: credit sum {credit_sum} != stated total {total_credit_cents}")

    net = sum(t['amount'] for t in txns)
    if ancien[1] + net != nouveau[1]:
        raise ValueError(
            f"{pdf_path}: balance chain broken within statement: "
            f"{ancien[1]} + {net} != {nouveau[1]}"
        )

    start_date = datetime.datetime.strptime(ancien[0], '%d.%m.%Y').date()
    end_date = datetime.datetime.strptime(nouveau[0], '%d.%m.%Y').date()
    return {
        'path': pdf_path,
        'start_date': start_date,
        'opening_cents': ancien[1],
        'end_date': end_date,
        'closing_cents': nouveau[1],
        'raw_transactions': txns,
    }


FRENCH_MONTHS = {
    'janvier': 1, 'février': 2, 'mars': 3, 'avril': 4, 'mai': 5, 'juin': 6,
    'juillet': 7, 'août': 8, 'septembre': 9, 'octobre': 10, 'novembre': 11, 'décembre': 12,
}


def parse_french_date(s):
    # e.g. "Samedi 11 juillet 2026" -> day name, day, month name, year.
    parts = s.strip().split()
    return datetime.date(int(parts[3]), FRENCH_MONTHS[parts[2].lower()], int(parts[1]))


def parse_operations_json(path):
    """Parse fetch_operations.sh's output (detail-dav.credit-agricole.fr's
    live operations feed) into the same transaction shape as the relevé
    parser. Unlike the relevés and the CSV, this feed has no stated closing
    balance — the caller must supply --target-balance."""
    with open(path) as f:
        data = json.load(f)
    txns = []
    for bloc in data['operationBlocs']:
        for op in bloc['operationDetails']:
            d = parse_french_date(op['dateValeurAffichee'])
            desc = op['libelleOperation']
            extra = ' '.join(x for x in (op.get('libelleComplementaire'), op.get('libelleComplementaire2')) if x)
            if extra:
                desc = f'{desc} {extra}'
            txns.append({
                'date': d.isoformat(),
                'amount': round(op['montant'] * 100),
                'payee_name': desc,
                'imported_payee': desc,
                'notes': op['libelleTypeOperation'],
                'cleared': True,
            })
    return txns


def resolve_date(ddmm, start_date, end_date):
    dd, mm = (int(x) for x in ddmm.split('.'))
    slack = datetime.timedelta(days=5)
    for y in {start_date.year, end_date.year}:
        try:
            d = datetime.date(y, mm, dd)
        except ValueError:
            continue
        if start_date - slack <= d <= end_date + slack:
            return d
    raise ValueError(f"can't resolve year for date {ddmm} within [{start_date}, {end_date}]")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--releves-dir', required=True)
    ap.add_argument('--operations-json', help='fetch_operations.sh output, to bridge the gap after the last relevé (preferred: pure curl)')
    ap.add_argument('--csv', help='CSV export to bridge the gap after the last relevé instead (see csv_to_transactions.py)')
    ap.add_argument('--target-balance', type=str, default=None,
                     help='Required with --operations-json (that feed has no stated closing balance). '
                          'Ignored with --csv (parsed from its own "Solde au ..." line).')
    ap.add_argument('--out', required=True)
    ap.add_argument('--opening-payee', default='Starting Balance')
    args = ap.parse_args()

    if args.operations_json and args.csv:
        print('ERROR: pass only one of --operations-json / --csv.', file=sys.stderr)
        sys.exit(1)
    if args.operations_json and args.target_balance is None:
        print('ERROR: --operations-json requires --target-balance (that feed has no stated closing balance).', file=sys.stderr)
        sys.exit(1)

    paths = sorted(glob.glob(os.path.join(args.releves_dir, '*.pdf')))
    if not paths:
        print(f'ERROR: no PDFs found in {args.releves_dir}', file=sys.stderr)
        sys.exit(1)

    statements = [parse_statement(p) for p in paths]
    statements.sort(key=lambda s: s['start_date'])

    for i in range(1, len(statements)):
        prev, cur = statements[i - 1], statements[i]
        if prev['closing_cents'] != cur['opening_cents']:
            print(
                f"ERROR: balance chain broken between statements:\n"
                f"  {prev['path']} closes at {prev['closing_cents']} ({prev['end_date']})\n"
                f"  {cur['path']} opens at {cur['opening_cents']} ({cur['start_date']})",
                file=sys.stderr,
            )
            sys.exit(2)
        if prev['end_date'] != cur['start_date']:
            print(
                f"WARNING: date gap between statements: {prev['path']} ends "
                f"{prev['end_date']}, {cur['path']} starts {cur['start_date']}",
                file=sys.stderr,
            )

    all_txns = []
    for stmt in statements:
        for t in stmt['raw_transactions']:
            d = resolve_date(t['date_val'], stmt['start_date'], stmt['end_date'])
            all_txns.append({
                'date': d.isoformat(),
                'amount': t['amount'],
                'payee_name': t['description'] or t['type'],
                'imported_payee': t['description'],
                'notes': t['type'],
                'cleared': True,
            })

    last_close_date = statements[-1]['end_date']
    target_cents = None
    bridge_source = None

    if args.operations_json:
        bridge_source = args.operations_json
        target_cents = round(float(args.target_balance) * 100)
        ops = parse_operations_json(args.operations_json)
        bridge = [t for t in ops if t['date'] >= last_close_date.isoformat()]
        print(f'Operations bridge: {len(bridge)} transaction(s) from {last_close_date.isoformat()} onward')
        all_txns.extend(bridge)
    elif args.csv:
        bridge_source = args.csv
        worktmp_json = args.out + '.csv_bridge.json'
        subprocess.run(
            [sys.executable,
             os.path.join(os.path.dirname(__file__), 'csv_to_transactions.py'),
             '--csv', args.csv, '--out', worktmp_json],
            check=True,
        )
        with open(worktmp_json) as f:
            csv_out = json.load(f)
        os.remove(worktmp_json)
        target_cents = csv_out['meta']['target_cents']
        bridge = [t for t in csv_out['transactions'] if t['date'] >= last_close_date.isoformat()]
        print(f'CSV bridge: {len(bridge)} transaction(s) from {last_close_date.isoformat()} onward')
        all_txns.extend(bridge)
    else:
        target_cents = statements[-1]['closing_cents']

    all_txns.sort(key=lambda t: t['date'])

    total_cents = sum(t['amount'] for t in all_txns)
    opening_cents = target_cents - total_cents

    if opening_cents != statements[0]['opening_cents']:
        print(
            f"ERROR: end-to-end reconciliation failed. Computed opening balance "
            f"({opening_cents}) does not match the oldest statement's own stated "
            f"Ancien solde ({statements[0]['opening_cents']}) as of "
            f"{statements[0]['start_date']}. Difference: "
            f"{opening_cents - statements[0]['opening_cents']} cents.",
            file=sys.stderr,
        )
        sys.exit(3)

    opening_date = (statements[0]['start_date'] - datetime.timedelta(days=1)).isoformat()
    opening_txn = {
        'date': opening_date,
        'amount': opening_cents,
        'payee_name': args.opening_payee,
        'notes': f'Balance reconciled from {len(statements)} Crédit Agricole relevés'
                 + (f' + operations bridge ({bridge_source})' if args.operations_json
                    else f' + CSV bridge ({bridge_source})' if args.csv else '') + '.',
        'cleared': True,
    }

    out = {
        'opening': opening_txn,
        'transactions': all_txns,
        'meta': {
            'count': len(all_txns),
            'sum_cents': total_cents,
            'opening_cents': opening_cents,
            'target_cents': target_cents,
            'earliest_date': all_txns[0]['date'] if all_txns else opening_date,
            'latest_date': all_txns[-1]['date'] if all_txns else opening_date,
            'statement_count': len(statements),
            'source': 'credit-agricole-releves',
        },
    }
    with open(args.out, 'w') as f:
        json.dump(out, f, indent=2)

    print(f'wrote {args.out}')
    print(f'  {len(statements)} statements chain-verified, {len(all_txns)} transactions total')
    print(f'  {all_txns[0]["date"]} -> {all_txns[-1]["date"]}')
    print(f'  opening: {opening_cents/100:.2f}  sum: {total_cents/100:.2f}  '
          f'-> final: {(opening_cents+total_cents)/100:.2f} (target: {target_cents/100:.2f})')


if __name__ == '__main__':
    main()
