#!/usr/bin/env python3
"""Parse a directory of BNP Paribas "Relevé de compte chèques" PDFs (fetched
via fetch_releves.sh) into transactions, chain-verify month-to-month, and
optionally bridge the gap between the last relevé and today using the
13-month CSV export (fetch_export.sh + this same script's --csv path,
reusing csv_to_transactions.py's row parsing).

Usage:
  releves_to_transactions.py --releves-dir releves/ --target-balance 19138.83 \
    --csv export.csv --out transactions.json

Each relevé states its own opening ("SOLDE CREDITEUR/DEBITEUR AU <date>")
and closing balance; this script asserts closing[n] == opening[n+1] across
ALL statements, and separately asserts the computed opening balance
(target - sum(all transactions)) matches the OLDEST statement's own opening
balance -- a bidirectional, whole-chain validation, same principle as
Crédit Agricole's relevés_to_transactions.py.

Layout quirks specific to this PDF template (see SKILL.md's BNP gotchas for
the full story):
- Every run of non-numeric characters is rendered with ~zero inter-word
  gap ("PRLVSEPASYNDICAT35RUECHAMPFLEURY" as ONE pdfplumber word at the
  default tolerance) -- lowering extract_words' x_tolerance to ~2.0
  recovers real word boundaries, but then also over-splits multi-digit
  numbers on tiny extra kerning gaps between digit glyphs ("35" -> "3","5";
  "18936,01" -> "18","936,01"). Fixed by merging adjacent purely-numeric
  word fragments back together *within the same clustered line* (doing
  this across lines, before clustering, wrongly glued a transaction amount
  to an unrelated number from the next line's continuation text -- this
  was caught during prototyping and is why clustering must happen first).
- No French weekday/month names anywhere (unlike Crédit Agricole) -- dates
  are plain DD.MM (transaction line) or DD.MM.YYYY (solde markers), no
  locale parsing needed.
- The Débit/Crédit split is column-position-based, computed dynamically
  per page from that page's own "Débit"/"Crédit" header x-positions (not
  hardcoded) -- but the header only actually appears on each statement's
  FIRST page; continuation pages (a single statement can run 15+ pages)
  reuse the last page's known boundary.
"""
import argparse
import datetime
import json
import re
import subprocess
import sys
from collections import defaultdict

import pdfplumber

SOLDE_RE = re.compile(r'^SOLDE (CREDITEUR|DEBITEUR) AU (\d{2}\.\d{2}\.\d{4})')
TOTAL_RE = re.compile(r'^TOTAL DES OPERATIONS')
TXN_START_RE = re.compile(r'^(\d{2}\.\d{2}) (.+)')
AMOUNT_RE = re.compile(r'^-?\d[\d ]*,\d{2}$')


def parse_cents(s):
    return round(float(s.replace(' ', '').replace(',', '.')) * 100)


def cluster_lines(words, tol=2.5):
    lines = defaultdict(list)
    for w in words:
        placed = False
        for top in list(lines.keys()):
            if abs(top - w['top']) <= tol:
                lines[top].append(w)
                placed = True
                break
        if not placed:
            lines[w['top']].append(w)
    return {top: sorted(ws, key=lambda w: w['x0']) for top, ws in sorted(lines.items())}


def merge_digit_fragments(ws):
    out = []
    for w in ws:
        if (out and re.fullmatch(r'\d+,?\d*', w['text'])
                and re.fullmatch(r'\d+,?\d*', out[-1]['text'])
                and (w['x0'] - out[-1]['x1']) < 4):
            merged = dict(out[-1])
            merged['text'] = out[-1]['text'] + w['text']
            merged['x1'] = w['x1']
            out[-1] = merged
        else:
            out.append(dict(w))
    return out


def find_column_boundary(words):
    # Older (2021-2022) statements mis-encode "é" as "Ø" in this font
    # (DØbit/CrØdit instead of Débit/Crédit) -- match on the encoding-stable
    # tail of each word instead of the literal accented string.
    debit = next((w for w in words if w['text'].endswith('bit') and len(w['text']) <= 6), None)
    credit = next((w for w in words if w['text'].endswith('dit') and len(w['text']) <= 7), None)
    if debit and credit:
        return (debit['x0'] + credit['x0']) / 2
    return None


def resolve_date(ddmm, start_date, end_date):
    dd, mm = (int(x) for x in ddmm.split('.'))
    for year in (start_date.year, end_date.year):
        try:
            d = datetime.date(year, mm, dd)
        except ValueError:
            continue
        if start_date - datetime.timedelta(days=5) <= d <= end_date + datetime.timedelta(days=5):
            return d
    # Fall back to whichever year parses, closest to the statement window.
    return datetime.date(end_date.year, mm, dd)


def parse_statement(pdf_path):
    pdf = pdfplumber.open(pdf_path)
    boundary = None
    all_rows = []  # list of (top_key_unused, text, words) across all pages, in order
    for page in pdf.pages:
        words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=2.0)
        lines = cluster_lines(words)
        page_boundary = find_column_boundary(words)
        if page_boundary is not None:
            boundary = page_boundary
        for top, ws in lines.items():
            ws = merge_digit_fragments(ws)
            text = ' '.join(w['text'] for w in ws)
            all_rows.append((text, ws))

    opening = None
    closing = None
    total_debit = None
    total_credit = None
    txns_raw = []  # (ddmm, description, amount_cents)

    state = 'before'
    for text, ws in all_rows:
        m = SOLDE_RE.match(text)
        if m:
            kind, date_str = m.groups()
            amount_word = ws[-1]['text'] if AMOUNT_RE.match(ws[-1]['text']) else None
            if amount_word is None:
                raise ValueError(f'{pdf_path}: solde marker with no trailing amount: {text!r}')
            cents = parse_cents(amount_word)
            if kind == 'DEBITEUR':
                cents = -cents
            date = datetime.datetime.strptime(date_str, '%d.%m.%Y').date()
            if state == 'before':
                opening = (date, cents)
                state = 'in'
            else:
                closing = (date, cents)
                state = 'after'
            continue

        if TOTAL_RE.match(text):
            nums = [w['text'] for w in ws if AMOUNT_RE.match(w['text'])]
            if len(nums) != 2:
                raise ValueError(f'{pdf_path}: TOTAL DES OPERATIONS with {len(nums)} amounts, expected 2: {text!r}')
            total_debit, total_credit = parse_cents(nums[0]), parse_cents(nums[1])
            continue

        if state != 'in':
            continue

        m = TXN_START_RE.match(text)
        if not m:
            continue  # continuation line of the previous transaction's description
        ddmm, rest = m.groups()
        if not AMOUNT_RE.match(ws[-1]['text']):
            continue  # a DD.MM appearing inside plain description text, not a real row
        amount_cents = parse_cents(ws[-1]['text'])
        if boundary is not None and ws[-1]['x0'] < boundary:
            amount_cents = -amount_cents
        # description = words between the leading date and the trailing valeur-date+amount
        desc_words = [w['text'] for w in ws[1:-2]] if len(ws) > 3 else [w['text'] for w in ws[1:-1]]
        txns_raw.append((ddmm, ' '.join(desc_words), amount_cents))

    if opening is None or closing is None:
        raise ValueError(f'{pdf_path}: missing opening/closing SOLDE marker(s)')
    if total_debit is None or total_credit is None:
        raise ValueError(f'{pdf_path}: missing TOTAL DES OPERATIONS line')

    net = total_credit - total_debit
    if opening[1] + net != closing[1]:
        raise ValueError(
            f'{pdf_path}: opening({opening[1]}) + net({net}) = {opening[1]+net}, '
            f'expected closing({closing[1]})')

    txn_sum = sum(c for _, _, c in txns_raw)
    if txn_sum != net:
        raise ValueError(
            f'{pdf_path}: sum of parsed transactions ({txn_sum}) != '
            f'TOTAL DES OPERATIONS net ({net}) -- {len(txns_raw)} txns parsed')

    txns = []
    for ddmm, desc, cents in txns_raw:
        date = resolve_date(ddmm, opening[0], closing[0])
        txns.append({
            'date': date.isoformat(),
            'amount': cents,
            'payee_name': desc,
            'imported_payee': desc,
            'notes': '',
            'cleared': True,
        })

    return {
        'start_date': opening[0],
        'end_date': closing[0],
        'opening_cents': opening[1],
        'closing_cents': closing[1],
        'transactions': txns,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--releves-dir', required=True)
    ap.add_argument('--target-balance', required=True, type=str)
    ap.add_argument('--csv', help='fetch_export.sh CSV to bridge the gap to today (optional)')
    ap.add_argument('--out', required=True)
    ap.add_argument('--opening-payee', default='Starting Balance')
    args = ap.parse_args()

    target_cents = round(float(args.target_balance) * 100)

    import glob
    paths = sorted(glob.glob(f'{args.releves_dir}/*.pdf'))
    if not paths:
        print(f'ERROR: no PDFs found in {args.releves_dir}', file=sys.stderr)
        sys.exit(1)

    statements = [parse_statement(p) for p in paths]
    statements.sort(key=lambda s: s['start_date'])

    for i in range(len(statements) - 1):
        a, b = statements[i], statements[i + 1]
        if a['closing_cents'] != b['opening_cents']:
            print(f'ERROR: chain break between statement ending {a["end_date"]} '
                  f'(closing {a["closing_cents"]/100:.2f}) and statement starting '
                  f'{b["start_date"]} (opening {b["opening_cents"]/100:.2f})', file=sys.stderr)
            sys.exit(2)

    all_txns = []
    for s in statements:
        all_txns.extend(s['transactions'])

    bridge_txns = []
    if args.csv:
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
            bridge_out_path = tmp.name
        result = subprocess.run(
            [sys.executable, __file__.replace('releves_to_transactions.py', 'csv_to_transactions.py'),
             '--csv', args.csv, '--target-balance', args.target_balance, '--out', bridge_out_path],
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f'ERROR: csv_to_transactions.py failed:\n{result.stderr}', file=sys.stderr)
            sys.exit(3)
        with open(bridge_out_path) as f:
            bridge_data = json.load(f)
        last_relevé_end = statements[-1]['end_date']
        for t in bridge_data['transactions']:
            if datetime.date.fromisoformat(t['date']) > last_relevé_end:
                bridge_txns.append(t)

    all_txns.extend(bridge_txns)
    all_txns.sort(key=lambda t: t['date'])

    total_cents = sum(t['amount'] for t in all_txns)
    opening_cents = target_cents - total_cents

    oldest = statements[0]
    if opening_cents != oldest['opening_cents']:
        print(f'ERROR: computed opening ({opening_cents/100:.2f}) from target minus sum '
              f'does not match the oldest statement\'s own opening balance '
              f'({oldest["opening_cents"]/100:.2f}). Refusing to write output.', file=sys.stderr)
        sys.exit(4)

    earliest = statements[0]['start_date']
    opening_date = (earliest - datetime.timedelta(days=1)).isoformat()
    opening_txn = {
        'date': opening_date,
        'amount': opening_cents,
        'payee_name': args.opening_payee,
        'notes': f'Opening balance reconciled from {len(statements)} BNP Paribas relevé(s)',
        'cleared': True,
    }

    check = opening_cents + total_cents
    if check != target_cents:
        print(f'ERROR: opening_cents({opening_cents}) + total_cents({total_cents}) = '
              f'{check}, expected {target_cents}. Refusing to write output.', file=sys.stderr)
        sys.exit(5)

    out = {
        'opening': opening_txn,
        'transactions': all_txns,
        'meta': {
            'count': len(all_txns),
            'statements': len(statements),
            'bridge_transactions': len(bridge_txns),
            'sum_cents': total_cents,
            'opening_cents': opening_cents,
            'target_cents': target_cents,
            'earliest_date': all_txns[0]['date'],
            'latest_date': all_txns[-1]['date'],
            'source': 'bnp-paribas-releves',
        },
    }
    with open(args.out, 'w') as f:
        json.dump(out, f, indent=2)

    print(f'wrote {args.out}')
    print(f'  {len(statements)} statements chain-verified, {len(all_txns)} transactions '
          f'({len(bridge_txns)} bridge), {all_txns[0]["date"]} -> {all_txns[-1]["date"]}')
    print(f'  opening: {opening_cents/100:.2f}  sum: {total_cents/100:.2f}  '
          f'-> final: {(opening_cents+total_cents)/100:.2f} (target: {target_cents/100:.2f})')


if __name__ == '__main__':
    main()
