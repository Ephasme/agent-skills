"""Thin runner: the realm_create Inspect harness over ratchet-cases.json, written in the ratchet layout.

Usage: ratchet_run.py --out <dir> --reps N [--train-ids 1,2,…] [--ids …]
Writes <out>/results.jsonl, <out>/errors.jsonl, <out>/traces/<id>_rep<k>.json (every case, unless
--no-traces); resumes on
(case, rep). The grade is the deterministic `rules` scorer only.
"""

import argparse
import json
import os
import time
from pathlib import Path

from inspect_ai import Task, eval as inspect_eval
from inspect_ai.dataset import MemoryDataset, Sample
from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageTool, ChatMessageUser

import harness

HERE = Path(__file__).parent
MODEL = os.environ.get("RATCHET_MODEL", "openai-api/omniroute/work/main")


def done_slots(out):
    slots = set()
    for name in ("results.jsonl",):
        p = out / name
        if p.exists():
            for line in p.read_text().splitlines():
                r = json.loads(line)
                slots.add((r["prompt_id"], r["rep"]))
    return slots


def trace(sample):
    out = []
    for m in sample.messages:
        if isinstance(m, ChatMessageSystem):
            out.append({"role": "system", "content": m.text})
        elif isinstance(m, ChatMessageUser):
            out.append({"role": "user", "content": m.text})
        elif isinstance(m, ChatMessageAssistant):
            if m.text:
                out.append({"role": "assistant", "content": m.text})
            for tc in m.tool_calls or []:
                out.append({"role": "tool_call", "name": tc.function, "content": json.dumps(tc.arguments, ensure_ascii=False)})
        elif isinstance(m, ChatMessageTool):
            out.append({"role": "tool_result", "name": m.function or "", "content": m.text})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--train-ids", default="")
    ap.add_argument("--ids", default="")
    ap.add_argument("--cases", default=str(HERE / "ratchet-cases.json"))
    ap.add_argument("--no-traces", action="store_true",
                    help="skip traces/<id>_rep<k>.json; by default every graded case gets one, so the "
                         "judge label sheet can be built from the run")
    a = ap.parse_args()
    out = Path(a.out)
    (out / "traces").mkdir(parents=True, exist_ok=True)
    cases = json.loads(Path(a.cases).read_text())["evals"]
    if a.ids:
        keep = set(a.ids.split(","))
        cases = [c for c in cases if str(c["id"]) in keep]
    have = done_slots(out)
    for rep in range(1, a.reps + 1):
        todo = [c for c in cases if (str(c["id"]), rep) not in have]
        if not todo:
            continue
        base = harness.task("realm-create", a.cases, None, 1, None)
        samples = [Sample(id=c["id"], input=c["prompt"], target=c["expected_output"],
                          metadata={"family": c["family"], "checks": c.get("checks", []), "case": c}) for c in todo]
        t = Task(dataset=MemoryDataset(samples), solver=base.solver, scorer=[harness.rules()],
                 message_limit=harness.MAX_MESSAGES, time_limit=300)
        t0 = time.time()
        logs = inspect_eval(t, model=MODEL, log_dir=str(out / "inspect"), display="none", max_connections=8,
                            fail_on_error=False, retry_on_error=2)
        for log in logs:
            for s in log.samples or []:
                cid = str(s.id)
                base_row = {"prompt_id": cid, "rep": rep}
                if s.error or "rules" not in (s.scores or {}):
                    with open(out / "errors.jsonl", "a") as f:
                        f.write(json.dumps({**base_row, "class": "sample_error",
                                            "error": (s.error.message if s.error else "no score")[:500]}) + "\n")
                    continue
                sc = s.scores["rules"]
                usage = {}
                served = None
                for model, u in (s.model_usage or {}).items():
                    served = model
                    usage = {"input_tokens": u.input_tokens, "output_tokens": u.output_tokens,
                             "cache_read_tokens": u.input_tokens_cache_read or 0}
                case = s.metadata["case"]
                limit_hit = s.limit is not None
                row = {**base_row, "prompt": case["prompt"], "tags": [case["family"], case.get("polarity", "")],
                       "grade": sc.value == "C", "explanation": sc.explanation, "status": "truncated" if limit_hit else "ok",
                       "model": (s.output.model if s.output and s.output.model else served), "usage": usage,
                       "latency_s": round(s.total_time or (time.time() - t0), 2)}
                with open(out / "results.jsonl", "a") as f:
                    f.write(json.dumps(row, ensure_ascii=False) + "\n")
                if not a.no_traces:
                    (out / "traces" / f"{cid}_rep{rep}.json").write_text(json.dumps(trace(s), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
