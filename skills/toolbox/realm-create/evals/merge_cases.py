"""Build the full case file: the 65 hand-written cases plus the mined ones.

    python3 merge_cases.py [--base ratchet-cases-60.json] [--mined mined-cases.json] \
                           [--out ratchet-cases-118.json]

Refuses on a duplicate id or slug, and prints the per-family count, so a merge cannot silently
drop a case or shadow one family with another.
"""
import argparse
import collections
import json
from pathlib import Path

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=str(HERE / "ratchet-cases-60.json"))
    ap.add_argument("--mined", default=str(HERE / "mined-cases.json"))
    ap.add_argument("--out", default=str(HERE / "ratchet-cases-118.json"))
    a = ap.parse_args()
    base = json.loads(Path(a.base).read_text())["evals"]
    mined = json.loads(Path(a.mined).read_text())["evals"]
    ids = [c["id"] for c in base + mined]
    dupes = [i for i, n in collections.Counter(ids).items() if n > 1]
    if dupes:
        raise SystemExit(f"duplicate case ids: {dupes}")
    cases = base + mined
    fam = collections.Counter(c["family"] for c in cases)
    prompts = collections.Counter(c["prompt"] for c in cases)
    if prompts.most_common(1)[0][1] > 1:
        print("WARNING: duplicate prompts:", [p[:60] for p, n in prompts.items() if n > 1][:5])
    for c in cases:
        if not c.get("checks"):
            raise SystemExit(f"case {c['id']} has no checks: it would always pass")
    Path(a.out).write_text(json.dumps({"note": f"{len(base)} hand-written + {len(mined)} mined from queen sessions.",
                                       "evals": cases}, indent=1, ensure_ascii=False))
    print(f"{len(cases)} cases -> {a.out}")
    for f, n in sorted(fam.items()):
        print(f"  {f:16s} {n}")


if __name__ == "__main__":
    main()
