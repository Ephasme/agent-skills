"""Paired analysis of one ratchet round: what the numbers can and cannot support.

    python3 analysis.py --baseline /path/op-main --branch /path/op-r2 \
        [--cases ratchet-cases-118.json] [--prespecified 105,206,215,218] [--out report.md]

Reads the ratchet's own `results.jsonl` (one row per case x rep) and reports:

- a manifest check: model mix, reps per case, case sets matching, and grades and tokens taken
  from the same directory (the bookkeeping defects the research report found: token figures
  called medians that were means, and a PR table whose grades and tokens came from two runs);
- paired per-case pass-rate difference with a bootstrap clustered on family, plus a sign-flip
  permutation p-value — the primary comparison;
- McNemar exact on the 2/2 binarisation, restricted to cases listed with `--prespecified`,
  because an unprespecified McNemar over every case is a maximum over noise;
- A/A: the two reps of one run treated as two conditions, which is the noise floor a change
  has to beat;
- tokens as median, mean and per-rep range.

Pure stdlib, fixed seeds; every figure in a round's report can be reproduced from the run dirs.
"""
import argparse
import collections
import json
import math
import random
import statistics
from pathlib import Path


def load(d):
    p = Path(d) / "results.jsonl"
    return [json.loads(line) for line in p.open()]


def by_case(rows):
    out = collections.defaultdict(dict)
    for r in rows:
        out[str(r["prompt_id"])][r["rep"]] = 1 if r["grade"] else 0
    return out


def rates(cases):
    return {c: sum(v.values()) / len(v) for c, v in cases.items()}


def boot_clustered(diffs, families, n=10000, seed=1):
    """Bootstrap over families, then cases within a family: cases of one family are correlated."""
    rng = random.Random(seed)
    by_fam = collections.defaultdict(list)
    for c, d in diffs.items():
        by_fam[families.get(c, "?")].append(d)
    fams = sorted(by_fam)
    out = []
    for _ in range(n):
        drawn = []
        for _ in fams:
            f = rng.choice(fams)
            drawn += [rng.choice(by_fam[f]) for _ in by_fam[f]]
        out.append(sum(drawn) / len(drawn))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def perm_p(diffs, n=20000, seed=3):
    rng = random.Random(seed)
    vals = list(diffs.values())
    obs = abs(sum(vals) / len(vals))
    hits = sum(1 for _ in range(n)
               if abs(sum(v if rng.random() < .5 else -v for v in vals) / len(vals)) >= obs)
    return (hits + 1) / (n + 1)


def mcnemar(b, c):
    n = b + c
    if not n:
        return 1.0
    k = min(b, c)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def tokens(rows):
    out = [r["usage"]["output_tokens"] for r in rows]
    per = {rep: [r["usage"]["output_tokens"] for r in rows if r["rep"] == rep] for rep in sorted({r["rep"] for r in rows})}
    return (f"median {statistics.median(out):.0f}, mean {statistics.mean(out):.0f}, "
            f"per-rep median " + " / ".join(f"{statistics.median(v):.0f}" for v in per.values()) +
            ", per-rep mean " + " / ".join(f"{statistics.mean(v):.0f}" for v in per.values()))


def manifest(name, rows, expected_ids):
    models = collections.Counter(r["model"] for r in rows)
    ids = {str(r["prompt_id"]) for r in rows}
    reps = collections.Counter(str(r["prompt_id"]) for r in rows)
    bad = [c for c, n in reps.items() if n != max(reps.values())]
    print(f"- **{name}**: {len(rows)} samples, {len(ids)} cases, models {dict(models)}")
    if len(models) > 1:
        print(f"  - WARNING: mixed model families in one run ({dict(models)}); no cross-family comparison.")
    if expected_ids and ids != expected_ids:
        print(f"  - WARNING: case set differs by {len(expected_ids ^ ids)} ids from the case file.")
    if bad:
        print(f"  - WARNING: {len(bad)} cases have fewer reps than the run's maximum.")
    return models


def boot_mean(rates_by_case, families, n=10000, seed=2):
    rng = random.Random(seed)
    by_fam = collections.defaultdict(list)
    for c, r in rates_by_case.items():
        by_fam[families.get(c, "?")].append(r)
    fams = sorted(by_fam)
    out = []
    for _ in range(n):
        drawn = []
        for _ in fams:
            f = rng.choice(fams)
            drawn += [rng.choice(by_fam[f]) for _ in by_fam[f]]
        out.append(sum(drawn) / len(drawn))
    out.sort()
    return out[int(0.025 * n)], out[int(0.975 * n)]


def single(a):
    rows = load(a.single)
    cases = {str(c["id"]): c for c in json.loads(Path(a.cases).read_text())["evals"]}
    fam = {k: v["family"] for k, v in cases.items()}
    print("## Manifest\n")
    manifest("run", rows, set(fam))
    bc_all = by_case(rows)
    rates_ = rates(bc_all)
    lo, hi = boot_mean(rates_, fam)
    passes = sum(sum(v.values()) for v in bc_all.values())
    total = sum(len(v) for v in bc_all.values())
    print(f"\n## Pass rate\n\n- {len(rates_)} cases, mean **{sum(rates_.values())/len(rates_):.3f}** "
          f"({passes}/{total} samples), family-clustered 95% CI **[{lo:.3f}, {hi:.3f}]**")
    print("\n| family | n | mean | zero |")
    print("|---|---|---|---|")
    byfam = collections.defaultdict(list)
    for c, r in rates_.items():
        byfam[fam.get(c, "?")].append(r)
    for f, rs in sorted(byfam.items()):
        print(f"| {f} | {len(rs)} | {sum(rs)/len(rs):.2f} | {sum(1 for r in rs if r == 0)} |")
    print("\n## A/A: identical text, rep against rep\n")
    bc = by_case(rows)
    reps = sorted({r["rep"] for r in rows})
    if len(reps) >= 2:
        one = sum(v.get(reps[0], 0) for v in bc.values())
        two = sum(v.get(reps[1], 0) for v in bc.values())
        print(f"- rep {reps[0]} {one} passes, rep {reps[1]} {two} passes, delta {two-one:+d}")
    print("\n## Tokens (output, per row)\n")
    print(f"- {tokens(rows)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--baseline")
    ap.add_argument("--branch")
    ap.add_argument("--single", help="one run to describe: mean pass rate with a clustered CI, "
                                     "per-family rates, and its own A/A noise")
    ap.add_argument("--cases", default=str(Path(__file__).parent / "ratchet-cases-118.json"))
    ap.add_argument("--prespecified", default="")
    ap.add_argument("--out", default="")
    a = ap.parse_args()
    if a.single:
        return single(a)
    if not (a.baseline and a.branch):
        raise SystemExit("give --single, or both --baseline and --branch")
    base, branch = load(a.baseline), load(a.branch)
    fam = {str(c["id"]): c["family"] for c in json.loads(Path(a.cases).read_text())["evals"]}
    print("## Manifest\n")
    manifest("baseline", base, set(fam))
    manifest("branch", branch, set(fam))

    bb, cc = by_case(base), by_case(branch)
    rb, rc = rates(bb), rates(cc)
    common = sorted(set(bb) & set(cc))
    diffs = {c: rc[c] - rb[c] for c in common}
    mean = sum(diffs.values()) / len(diffs)
    lo, hi = boot_clustered(diffs, fam)
    print("\n## Paired comparison (primary)\n")
    print(f"- {len(common)} cases; mean pass rate {sum(rb.values())/len(rb):.3f} -> "
          f"{sum(rc.values())/len(rc):.3f}; difference **{100*mean:+.1f} pp**")
    print(f"- family-clustered bootstrap 95% CI **[{100*lo:+.1f}, {100*hi:+.1f}] pp**; "
          f"sign-flip permutation p = **{perm_p(diffs):.3f}**")
    print(f"- cases changed: {sum(1 for d in diffs.values() if d)}  "
          f"(improved {sum(1 for d in diffs.values() if d > 0)}, worsened {sum(1 for d in diffs.values() if d < 0)})")
    print("\n### By family\n")
    print("| family | n | baseline | branch | diff |")
    print("|---|---|---|---|---|")
    byfam = collections.defaultdict(list)
    for c in common:
        byfam[fam.get(c, "?")].append(c)
    for f, ids in sorted(byfam.items()):
        d = sum(diffs[c] for c in ids) / len(ids)
        print(f"| {f} | {len(ids)} | {sum(rb[c] for c in ids)/len(ids):.2f} | "
              f"{sum(rc[c] for c in ids)/len(ids):.2f} | {100*d:+.0f} pp |")

    pres = {c.strip() for c in a.prespecified.split(",") if c.strip()}
    print("\n## Prespecified cases, McNemar exact (2/2 pass vs not)\n")
    if not pres:
        print("- none listed: the 2/2 rule is not used as evidence this round.")
    else:
        b = c = 0
        for cid in sorted(pres):
            if cid not in bb or cid not in cc:
                print(f"- {cid}: missing from a run")
                continue
            pb = all(bb[cid].values()) and len(bb[cid]) == max(len(v) for v in bb.values())
            pc = all(cc[cid].values()) and len(cc[cid]) == max(len(v) for v in cc.values())
            print(f"- {cid}: baseline {sum(bb[cid].values())}/{len(bb[cid])}, branch "
                  f"{sum(cc[cid].values())}/{len(cc[cid])}")
            b += pc and not pb
            c += pb and not pc
        print(f"\n- discordant +{b}/-{c}; exact p = **{mcnemar(b, c):.3f}**")

    print("\n## A/A: identical text, rep against rep\n")
    for name, rows in (("baseline", base), ("branch", branch)):
        bc = by_case(rows)
        reps = sorted({r["rep"] for r in rows})
        if len(reps) < 2:
            continue
        one = sum(v.get(reps[0], 0) for v in bc.values())
        two = sum(v.get(reps[1], 0) for v in bc.values())
        print(f"- {name}: rep {reps[0]} {one} passes, rep {reps[1]} {two} passes, delta {two-one:+d}")

    print("\n## Tokens (output, per row)\n")
    print(f"- baseline: {tokens(base)}")
    print(f"- branch: {tokens(branch)}")
    txt = ""
    if a.out:
        txt = (f"mean difference {100*mean:+.1f} pp, clustered CI [{100*lo:+.1f}, {100*hi:+.1f}], "
               f"permutation p {perm_p(diffs):.3f}")
        Path(a.out).write_text(txt + "\n")
        print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
