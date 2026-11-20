"""Summarise Inspect logs of the realm evals: pass rate per family and scorer, failures, tokens.

Usage: python report.py <log-dir> [<log-dir> …]   (one dir per ref; columns side by side)
A sample passes a scorer when its mean over epochs is 1.0; the rate is the share of epochs that pass.
"""

import sys
from collections import defaultdict
from pathlib import Path

from inspect_ai.log import read_eval_log


def load(log_dir):
    rows, tokens, fails = defaultdict(lambda: defaultdict(list)), defaultdict(int), []
    for f in sorted(Path(log_dir).glob("*.eval")):
        log = read_eval_log(str(f))
        for model, u in (log.stats.model_usage or {}).items():
            tokens[model] += u.total_tokens
        for s in log.samples or []:
            fam = s.metadata["family"]
            for name, sc in s.scores.items():
                ok = sc.value in ("C", 1, 1.0)
                rows[fam][name].append(ok)
                if not ok:
                    fails.append((fam, s.id, s.epoch, name, (sc.explanation or "")[:300]))
    return rows, tokens, fails


def main(dirs):
    data = {d: load(d) for d in dirs}
    fams = sorted({f for rows, _, _ in data.values() for f in rows})
    head = "| family | " + " | ".join(f"{Path(d).name} rules | {Path(d).name} graded" for d in dirs) + " |"
    print(head)
    print("|" + "---|" * (1 + 2 * len(dirs)))
    for fam in fams:
        cells = []
        for d in dirs:
            rows = data[d][0][fam]
            for name in ("rules", "graded"):
                v = rows.get(name, [])
                cells.append(f"{sum(v)}/{len(v)}" if v else "—")
        print(f"| {fam} | " + " | ".join(cells) + " |")
    for d in dirs:
        _, tokens, fails = data[d]
        print(f"\n## {d}\ntokens: {dict(tokens)}\nfailures:")
        for fam, sid, ep, name, why in fails:
            print(f"- {fam} #{sid} e{ep} {name}: {why}")


if __name__ == "__main__":
    main(sys.argv[1:])
