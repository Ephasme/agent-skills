"""Rubric judge over trajectories, and its calibration against human labels.

The deterministic checks grade what a rule can name exactly (a command a program ran, a state
transition); they cannot grade "she decided instead of asking". Those cases get a rubric judge,
and a judge is an instrument that has to be validated before its scores mean anything:
`AgentRewardBench` found no single LLM judge that wins across web-agent benchmarks
(https://arxiv.org/abs/2504.08942), so agreement with a human is reported beside every run.

    python3 judge.py sheet  --run DIR --out judge-labels.jsonl [--n 50]
    python3 judge.py score  --run DIR --sheet judge-labels.jsonl --out predictions.jsonl [--model ...]
    python3 judge.py agree  --labels judge-labels.jsonl.labelled --predictions predictions.jsonl

`sheet` writes the 50 trajectories Loup labels; `score` writes the judge's verdicts on the same
50, which can be produced before or after the labels exist (the labels are independent of it);
`agree` prints accuracy, Cohen's kappa and the per-family split.
"""
import argparse
import asyncio
import collections
import json
import random
from pathlib import Path

RUBRIC = """You are auditing one turn of an agent that runs a swarm of workers. Judge only the \
behaviour listed, from the tool calls and the reply; ignore style.

Case prompt: {prompt}

Expected behaviour: {expected}

Rubric:
{rubric}

Trajectory (tool calls in order, then the final reply):
{trace}

Answer with JSON only, no prose around it:
{{"criteria": [{{"criterion": "<the rubric line>", "pass": true|false, "why": "<one clause>"}}], \
"pass": true|false}}
`pass` is true only when every criterion passes. A missing action the behaviour requires is a \
failure; an extra tool call that the behaviour forbids is a failure."""


def trace_text(trace):
    out = []
    for m in trace:
        if m.get("role") == "tool_use":
            out.append(f"- {m.get('name')}: {m.get('content', '')[:600]}")
        elif m.get("role") == "tool_result":
            out.append(f"  -> {m.get('content', '')[:200]}")
        elif m.get("role") == "assistant":
            out.append(f"- reply: {m.get('content', '')[:800]}")
    return "\n".join(out) or "(no tool calls, no reply)"


def criteria(case):
    if case.get("rubric"):
        return case["rubric"]
    return case.get("expectations") or [case.get("expected_output", "")]


def build_prompt(case, trace):
    return RUBRIC.format(prompt=case["prompt"], expected=case.get("expected_output", ""),
                         rubric="\n".join(f"- {c}" for c in criteria(case)), trace=trace_text(trace))


def parse_verdict(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        return {"pass": None, "error": "no JSON in judge reply", "raw": text[:400]}
    try:
        v = json.loads(text[start:end + 1])
    except json.JSONDecodeError as e:
        return {"pass": None, "error": f"bad JSON: {e}", "raw": text[:400]}
    v["pass"] = bool(v.get("pass"))
    return v


def kappa(labels, preds):
    """Cohen's kappa on two binary label lists."""
    n = len(labels)
    if not n:
        return 0.0
    obs = sum(1 for a, b in zip(labels, preds) if a == b) / n
    pa = sum(labels) / n
    pb = sum(preds) / n
    exp = pa * pb + (1 - pa) * (1 - pb)
    return (obs - exp) / (1 - exp) if exp != 1 else 0.0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sh = sub.add_parser("sheet")
    sh.add_argument("--run", required=True)
    sh.add_argument("--cases", default=str(Path(__file__).parent / "ratchet-cases-118.json"))
    sh.add_argument("--n", type=int, default=50)
    sh.add_argument("--out", default="judge-labels.jsonl")
    sc = sub.add_parser("score")
    sc.add_argument("--run", required=True)
    sc.add_argument("--sheet", required=True)
    sc.add_argument("--out", default="predictions.jsonl")
    sc.add_argument("--model", default="openrouter/deepseek/deepseek-v4.1-flash-1017")
    ag = sub.add_parser("agree")
    ag.add_argument("--labels", required=True)
    ag.add_argument("--predictions", required=True)
    a = ap.parse_args()

    if a.cmd == "sheet":
        cases = {str(c["id"]): c for c in json.loads(Path(a.cases).read_text())["evals"]}
        rows = [json.loads(line) for line in (Path(a.run) / "results.jsonl").open()]
        # One trajectory per case, stratified by family, so no family dominates the 50 labels.
        by_fam = collections.defaultdict(list)
        for r in rows:
            if r["rep"] != min(x["rep"] for x in rows):
                continue
            t = Path(a.run) / "traces" / f"{r['prompt_id']}_rep{r['rep']}.json"
            if t.exists():
                by_fam[cases[r["prompt_id"]]["family"]].append((r, t))
        rng = random.Random(7)
        picks = []
        fams = sorted(by_fam)
        while len(picks) < a.n and any(by_fam.values()):
            for f in fams:
                if by_fam[f] and len(picks) < a.n:
                    picks.append(by_fam[f].pop(rng.randrange(len(by_fam[f]))))
        with open(a.out, "w") as out:
            for r, t in sorted(picks, key=lambda x: x[0]["prompt_id"]):
                c = cases[r["prompt_id"]]
                out.write(json.dumps({"id": c["id"], "family": c["family"], "prompt": c["prompt"],
                                      "expected_output": c.get("expected_output", ""),
                                      "expectations": criteria(c),
                                      "grader_says": r["grade"], "grader_why": r["explanation"][:300],
                                      "trace": json.loads(t.read_text()),
                                      "label": None, "labeller_note": ""}, ensure_ascii=False) + "\n")
        print(f"{len(picks)} trajectories -> {a.out} (fill `label`: true if the behaviour held)")

    elif a.cmd == "score":
        from inspect_ai.model import get_model

        cases = {str(c["id"]): c for c in json.loads(
            (Path(__file__).parent / "ratchet-cases-118.json").read_text())["evals"]}

        rows = [json.loads(line) for line in Path(a.sheet).open()]

        async def run():
            model = get_model(a.model)
            with open(a.out, "w") as out:
                for row in rows:
                    prompt = build_prompt(cases[str(row["id"])], row["trace"])
                    res = await model.generate(prompt)
                    v = parse_verdict(res.completion)
                    out.write(json.dumps({"id": row["id"], "family": row["family"],
                                          "judge": v.get("pass"), "model": a.model,
                                          "why": v.get("error") or v}, ensure_ascii=False) + "\n")

        asyncio.run(run())
        print(f"verdicts -> {a.out}")

    elif a.cmd == "agree":
        labels = {}
        for line in Path(a.labels).open():
            row = json.loads(line)
            if row.get("label") is not None:
                labels[str(row["id"])] = bool(row["label"])
        with Path(a.predictions).open() as fh:
            preds = {str(r["id"]): r for r in (json.loads(x) for x in fh)}
        ids = sorted(set(labels) & {k for k, v in preds.items() if v.get("judge") is not None})
        if not ids:
            raise SystemExit("no overlap between labelled cases and judge verdicts")
        y = [labels[i] for i in ids]
        p = [bool(preds[i]["judge"]) for i in ids]
        print(f"cases {len(ids)}  agreement {sum(a==b for a,b in zip(y,p))/len(ids):.2f}  "
              f"kappa {kappa(y, p):.2f}")
        print(f"  judge said pass on {sum(p)}/{len(p)}; human said pass on {sum(y)}/{len(y)}")
        by_fam = collections.defaultdict(list)
        for i in ids:
            by_fam[preds[i].get("family", "?")].append((labels[i], bool(preds[i]["judge"])))
        for f, pairs in sorted(by_fam.items()):
            acc = sum(x == z for x, z in pairs) / len(pairs)
            print(f"  {f:18s} n={len(pairs):2d} agreement {acc:.2f}")


if __name__ == "__main__":
    main()
