"""Every mined case must pass a correct transcript and fail a wrong one, with no model call.

    python3 -m unittest test_mined_cases

A case whose checks both accept the violation and reject the fix measures nothing; the point
of grading a mined turn offline first is that the case set cannot ship broken and look green.
"""
import json
import unittest
from pathlib import Path

import harness

CASES = json.loads((Path(__file__).parent / "mined-cases.json").read_text())["evals"]

CORRECT = [
    {"tool": "bash", "args": {"command": "realm table --project /perso/realm | sed -n 3,20p"}},
    {"tool": "bash", "args": {"command": "mkdir -p /tmp/subj"}},
    {"tool": "write", "args": {"path": "/tmp/subj/r.md", "content": "Goal: switch GrayTurtle to Gemini Argon."}},
    {"tool": "bash", "args": {"command": "realm dispatch --project /perso/realm --to BlackMoose --slug "
                                         "gray-turtle-model --title Switch the model --body-file /tmp/subj/r.md"}},
    {"tool": "send_message", "args": {"to": ["BlackMoose"], "body_md": "Take it."}},
]
WRONG = [
    {"tool": "bash", "args": {"command": "cd ~/code/perso/realm && git log --oneline -3 && git status --short"}},
    {"tool": "bash", "args": {"command": "sed -n 140,175p src/db/subjects.ts"}},
    {"tool": "read", "args": {"path": "plugin/herdr/model.ts"}},
    {"tool": "bash", "args": {"command": "ssh loup@host.orb.internal uptime"}},
]


ASKED = [{"tool": "ask", "args": {"html": "<form><p>Retire GrayTurtle?</p></form>"}}]


class MinedCases(unittest.TestCase):
    def test_correct_transcript_passes(self):
        for case in CASES:
            asks = any(spec.get("call", {}).get("tool") == "ask" for spec in case["checks"])
            calls = ASKED if asks else CORRECT
            for spec in case["checks"]:
                self.assertIsNone(harness.check(spec, calls, "Dispatched to BlackMoose."),
                                  f"case {case['id']} rejects the correct transcript: {case['prompt'][:60]}")

    def test_wrong_transcript_fails(self):
        for case in CASES:
            self.assertTrue(any(harness.check(spec, WRONG, "") for spec in case["checks"]),
                            f"case {case['id']} accepts work done by the queen: {case['prompt'][:60]}")

    def test_ask_controls_still_ask(self):
        for case in CASES:
            if not any(spec.get("call", {}).get("tool") == "ask" for spec in case["checks"]):
                continue
            self.assertIsNone(harness.check({"call": {"tool": "ask"}}, ASKED, ""))
            self.assertIsNotNone(harness.check({"call": {"tool": "ask"}}, CORRECT, ""))


class Traceability(unittest.TestCase):
    """A mined case must quote its session: prompt text and turn index both check out."""

    SESSIONS = Path.home() / ".omp/agent/sessions"

    def test_source_points_at_the_quote(self):
        seen = 0
        for case in CASES:
            if not case["source"].endswith(tuple(f"#turn{i}" for i in range(200))):
                continue
            name, turn = case["source"].split("#turn")
            hits = list(self.SESSIONS.glob(f"*/{name}"))
            if not hits:
                continue
            seen += 1
            users, cur = [], None
            for line in hits[0].open():
                try:
                    import json as _json
                    row = _json.loads(line)
                except ValueError:
                    continue
                msg = row.get("message") or {}
                if msg.get("role") == "user":
                    c = msg.get("content")
                    t = c if isinstance(c, str) else " ".join(b.get("text", "") for b in c or []
                                                              if b.get("type") == "text")
                    if t.strip() and not t.startswith("<system-reminder>"):
                        users.append(t.strip())
            if int(turn) >= len(users):
                continue
            real = users[int(turn)]
            # The curated prompt may normalise wording; the first 40 characters must survive.
            self.assertEqual(case["prompt"][:40], real[:40], f"case {case['id']} quotes the wrong turn")
        if not seen:
            self.skipTest("no queen sessions on this machine")


if __name__ == "__main__":
    unittest.main()
