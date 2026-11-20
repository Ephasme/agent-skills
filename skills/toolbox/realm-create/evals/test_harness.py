"""Harness self-test, no model calls: `python3 -m unittest test_harness` from this directory (needs inspect-ai)."""

import asyncio
import json
import unittest
from pathlib import Path

from inspect_ai.util import store
from inspect_ai.util._store import Store, init_subtask_store

import harness

CASES = {c["id"]: c for p in ("evals.json", "brief-evals.json")
         for c in json.loads((Path(__file__).parent / p).read_text())["evals"]}


def bash(case, command):
    init_subtask_store(Store())
    store().set("case", case)
    out = asyncio.run(harness._bash(command))
    return out, store().get("calls")


class Normalize(unittest.TestCase):
    def test_heredoc_body_is_not_a_command(self):
        cmd = "cat > f <<'EOF'\nrun du -sh /\nEOF\npython3 realm.py dispatch --to A --body-file f"
        self.assertEqual(harness.normalize(cmd), "cat > f <<'EOF'\npython3 realm.py dispatch --to A --body-file f")

    def test_variables_expand(self):
        cmd = 'R="python3 ~/x/realm.py"; P=/t\n$R table --project $P; ${R} sync --project $P'
        self.assertIn("python3 ~/x/realm.py table --project /t", harness.normalize(cmd))
        self.assertIn("python3 ~/x/realm.py sync --project /t", harness.normalize(cmd))


class Stub(unittest.TestCase):
    def test_set_state_then_table_reflects_it(self):
        out, calls = bash(CASES[2], 'R="python3 realm.py"; $R subject set-state --project /test/r --slug api-tests '
                                    '--state done --status "ok" && $R table --project /test/r')
        self.assertIn("| api-tests | AmberFox | done | ok |", out)
        self.assertIsNone(harness.check({"set_states": {"api-tests": "done"}}, calls, ""))

    def test_dispatch_records_and_refuses_duplicates(self):
        case = {**CASES[5]}
        init_subtask_store(Store())
        store().set("case", case)
        first = asyncio.run(harness._bash("python3 realm.py dispatch --to AmberFox --slug e2e --after login-page"))
        again = asyncio.run(harness._bash("python3 realm.py dispatch --to AmberFox --slug e2e"))
        self.assertEqual(json.loads(first)["subject"]["state"], "queued")
        self.assertIn("error", json.loads(again))

    def test_case_rule_wins_per_segment(self):
        out, _ = bash(CASES[7], "python3 realm.py worker list --project /test/r --scale-in; echo done")
        self.assertIn("CedarJay", out)
        self.assertTrue(out.endswith("done"))


class Checks(unittest.TestCase):
    def test_kinds(self):
        calls = [{"tool": "bash", "args": {"command": "realm.py spawn"}},
                 {"tool": "bash", "args": {"command": "realm.py dispatch --to X"}}]
        c = harness.check
        self.assertIsNone(c({"before": [{"tool": "bash", "match": "spawn"}, {"tool": "bash", "match": "dispatch"}]},
                            calls, ""))
        self.assertIsNotNone(c({"before": [{"tool": "bash", "match": "dispatch"}, {"tool": "bash", "match": "spawn"}]},
                               calls, ""))
        self.assertIsNone(c({"any": [{"no_tool": "bash"}, {"reply_matches": "hi"}]}, calls, "hi there"))
        self.assertIsNotNone(c({"reply_max_words": 1}, calls, "two words"))

    def test_every_case_check_is_known(self):
        for case in CASES.values():
            for spec in case.get("checks", []):
                harness.check(spec, [], "")  # raises on an unknown kind


if __name__ == "__main__":
    unittest.main()
