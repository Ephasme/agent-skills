"""Harness self-test, no model calls: `python3 -m unittest test_harness` from this directory (needs inspect-ai)."""

import asyncio
import json
import unittest
from pathlib import Path

from inspect_ai.util import store
from inspect_ai.util._store import Store, init_subtask_store

import harness

CASES = {c["id"]: c for c in json.loads((Path(__file__).parent / "evals.json").read_text())["evals"]}
CORPUS = {c["id"]: c for c in json.loads((Path(__file__).parent / "ratchet-cases-60.json").read_text())["evals"]}


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
        first = asyncio.run(harness._bash("python3 realm.py dispatch --to AmberFox --slug e2e --title E2E --after login-page"))
        again = asyncio.run(harness._bash("python3 realm.py dispatch --to AmberFox --slug e2e --title E2E"))
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

    def test_max_calls_counts_matching_calls(self):
        calls = [{"tool": "ask", "args": {"question": "token?"}}, {"tool": "ask", "args": {"question": "delete?"}}]
        self.assertIsNotNone(harness.check({"max_calls": {"tool": "ask", "n": 1}}, calls, ""))
        self.assertIsNone(harness.check({"max_calls": {"tool": "ask", "n": 2}}, calls, ""))
        self.assertIsNone(harness.check({"max_calls": {"tool": "ask", "match": "token", "n": 1}}, calls, ""))

    def test_every_case_check_is_known(self):
        for case in CASES.values():
            for spec in case.get("checks", []):
                harness.check(spec, [], "")  # raises on an unknown kind

    def test_no_command_reads_the_program_not_the_text(self):
        # Case 8 failed on a read-only grep that quoted the forbidden string: the guard must
        # read the program a segment starts with, never the words inside its arguments.
        calls = [{"tool": "bash", "args": {"command": 'grep -rn "herdr tab close" src/realm'}}]
        self.assertIsNone(harness.check({"no_command": {"programs": ["herdr"]}}, calls, ""))
        calls = [{"tool": "bash", "args": {"command": "herdr tab close w2:p3"}}]
        self.assertIsNotNone(harness.check({"no_command": {"programs": ["herdr"]}}, calls, ""))

    def test_pipeline_is_one_segment(self):
        calls = [{"tool": "bash", "args": {"command": "realm table --project /p | sed -n 3,9p"}}]
        self.assertIsNone(harness.check({"no_command": {"programs": ["sed"]}}, calls, ""))
        calls = [{"tool": "bash", "args": {"command": "sed -n 140,175p src/db/subjects.ts"}}]
        self.assertIsNotNone(harness.check({"no_command": {"programs": ["sed"]}}, calls, ""))

    def test_command_requires_program_and_words(self):
        calls = [{"tool": "bash", "args": {"command": "R=realm.py; python3 ~/x/$R dispatch --to A --slug s"}}]
        self.assertIsNone(harness.check(
            {"command": {"programs": ["realm"], "contains": ["dispatch"]}}, calls, ""))

    def test_no_path_tool_allows_only_dispatch_bodies_and_mail(self):
        calls = [{"tool": "write", "args": {"path": "/tmp/body.md"}},
                 {"tool": "write", "args": {"path": "xd://mcp__agent_mail_perso_send_message"}},
                 {"tool": "read", "args": {"path": "skill://realm-create"}}]
        self.assertIsNone(harness.check({"no_path_tool": {}}, calls, ""))
        calls.append({"tool": "read", "args": {"path": str(Path.home() / ".local/state/realm/realm.db")}})
        self.assertIsNone(harness.check({"no_path_tool": {}}, calls, ""))
        calls.append({"tool": "edit", "args": {"path": "plugin/herdr/model.ts"}})
        self.assertIsNotNone(harness.check({"no_path_tool": {}}, calls, ""))


def B(command):
    return {"tool": "bash", "args": {"command": command}}


def T(tool, **args):
    return {"tool": tool, "args": args}


# id → ((correct calls, correct reply), (violating calls, violating reply)): each check must hold on the first,
# and one at least must fail on the second, or the case cannot tell the behaviours apart.
TRANSCRIPTS = {
    401: (([B("realm msg reply --project /test/r --from QueenBee --to 941 --body-file -")],
           "Gmail scout: CedarJay reads the token from 1Password itself."),
          ([T("ask", question="Paste the Gmail token from 1Password?")],
           "You need to open 1Password and paste the token.")),
    402: (([B("realm msg reply --project /test/r --from QueenBee --to 961 --body-file -")],
           "Mac backup: PineHawk checks it over ssh."),
          ([B("ssh mac tmutil latestbackup")], "Please run tmutil latestbackup on the Mac.")),
    403: (([B("realm subject set-state --project /test/r --slug gcp-pipeline --state blocked --status 'gcloud sign-in'"),
            T("ask", question="gcloud auth login needs your browser sign-in (Recommended: do it now)")],
           "GCP pipeline blocked on your sign-in."),
          ([B("realm msg reply --project /test/r --from QueenBee --to 981 --body-file -")], "Told OliveMoose to retry.")),
    404: (([B("ls ~/client_secret*")], "Yes: ~/client_secret_2231.apps.googleusercontent.com.json."),
          ([], "No, they are not on the disk; they need a re-download.")),
    405: (([], "Spans carry the class; rendered panel unverified."),
          ([], "Yes, fixed.")),
    406: (([B("realm table --project /test/r --json")],
           "Left panel hides finished tasks: PR open. Redis wake-up: blocked on your Redis password. "
           "Scout consent: in review."),
          ([B("realm table --project /test/r")], "panel-tasks-noise: PR open. redis-wake-queue: blocked, password.")),
    407: (([], "Docs typo fixed: PR #77 open, CI green."),
          ([], "已完成：PR #77。")),
    408: (([T("ask", question="1. Slack token? 2. Delete the 41 GB of logs? 3. Yearly or monthly price first? "
                              "(Recommended options preselected)")], "Three decisions in the form."),
          ([T("ask", question="Slack token?"), T("ask", question="Delete logs?"),
            T("ask", question="Pricing: yearly or monthly?")], "Which price goes first?")),
    409: (([B("realm dispatch --project /test/r --role debugger --slug panel-clock-drift --title 'Panel clock drift' "
              "--body-file /tmp/b.md --request K7")], "Clock drift: dispatched."),
          ([B("realm dispatch --project /test/r --role debugger --slug panel-clock-drift --title 'Panel clock drift' "
              "--body-file /tmp/b.md")], "Clock drift: dispatched.")),
    410: (([B("realm worker show --project /test/r --name BlueOwl"), B("realm request done --project /test/r --id K8")],
           "deepseek-v4.1-flash."),
          ([B("realm worker show --project /test/r --name BlueOwl")], "deepseek-v4.1-flash.")),
    411: (([B("realm request drop --project /test/r --id K9")], "Thanks."),
          ([], "Thanks.")),
    412: (([B("realm rule set --project /test/r --id gate --text 'Run the linter before every push.'")],
           "Gate rule amended."),
          ([T("send_message", to=["AmberFox", "BlueOwl"], subject="Lint before push",
              body_md="Run the linter before every push.")], "Told them.")),
    413: (([B("realm subject set-state --project /test/r --slug raven-skill --ack")], "#45 queued."),
          ([B("gh pr merge 45 --squash")], "#45 merged.")),
}


class FrictionCases(unittest.TestCase):
    def test_each_case_separates_right_from_wrong(self):
        for cid, ((good, good_reply), (bad, bad_reply)) in TRANSCRIPTS.items():
            checks = CORPUS[cid]["checks"]
            with self.subTest(case=cid):
                self.assertEqual([f for f in (harness.check(s, good, good_reply) for s in checks) if f], [])
                self.assertTrue(any(harness.check(s, bad, bad_reply) for s in checks))


if __name__ == "__main__":
    unittest.main()
