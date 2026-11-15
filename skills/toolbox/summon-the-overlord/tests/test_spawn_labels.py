import argparse
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "overlord.py"
spec = importlib.util.spec_from_file_location("overlord", SCRIPT)
o = importlib.util.module_from_spec(spec)
sys.modules["overlord"] = o
spec.loader.exec_module(o)


GIT = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]


def dry_run(mode: str, task: str = "feat prompt and spawn labelling", title: str = "") -> list[str]:
    args = argparse.Namespace(
        mode=mode, task=task, title=title, model="test-model",
        repo=[Path("/repo")], dest="/targets", base="main", dry_run=True,
    )
    with tempfile.TemporaryDirectory() as prompts, tempfile.TemporaryDirectory() as state:
        with patch.object(o, "PROMPTS", Path(prompts)), patch.object(o, "REGISTRY", Path(state) / "w.json"), patch.object(
            o, "STATE_DIR", Path(state)
        ), patch.object(o, "resolve_model", return_value=("test-model", "")), patch.object(
            o, "credential_note", return_value=""
        ), patch.object(o, "handover", return_value="handover"), patch("sys.stdout", new_callable=io.StringIO) as output:
            o._MEMO.clear()
            assert o.cmd_spawn(args) == 0
        return output.getvalue().splitlines()


class SpawnOrderTests(unittest.TestCase):
    def test_feat_starts_agent_then_toggles_plan_mode_then_prompts(self):
        lines = dry_run("feat")
        verbs = [
            line.split()[4] for line in lines
            if line.startswith("would run\therdr agent ")
        ]
        self.assertEqual(verbs, ["start", "send-keys", "prompt"])
        started = next(line for line in lines if " agent start " in line)
        self.assertTrue(started.endswith("--model test-model --plan test-model --smol test-model"))
        self.assertTrue(next(line for line in lines if "send-keys" in line).endswith("Alt+Shift+P"))

    def test_fast_starts_agent_then_prompts_without_plan_mode(self):
        lines = dry_run("fast")
        verbs = [line.split()[4] for line in lines if line.startswith("would run\therdr agent ")]
        self.assertEqual(verbs, ["start", "prompt"])
        self.assertTrue(next(line for line in lines if " agent start " in line).endswith(
            "--model test-model --plan test-model --smol test-model"
        ))

    def test_dry_run_label_carries_allocated_name_and_frozen_title(self):
        self.assertIn(
            "would run\therdr pane rename <pane> 🗺 PLAN m1 prompt-spawn-labelling", dry_run("feat")
        )
        self.assertIn(
            "would run\therdr pane rename <pane> ⚒ BUILD m1 prompt-spawn-labelling", dry_run("fast")
        )

    def test_title_flag_wins_and_leading_job_word_is_dropped(self):
        self.assertIn("would run\therdr pane rename <pane> 🗺 PLAN m1 my-slug", dry_run("feat", title="my-slug"))
        lines = dry_run("feat", task="Job: rust crate")
        self.assertTrue(any("worktree add -b worktree/rust-crate " in line for line in lines))

    def test_invalid_title_is_refused(self):
        args = argparse.Namespace(
            mode="feat", task="x", title="Bad Title", model="test-model",
            repo=[Path("/repo")], dest="/targets", base="main", dry_run=True,
        )
        with patch.object(o, "resolve_model", return_value=("test-model", "")), patch("sys.stderr", new_callable=io.StringIO):
            self.assertEqual(o.cmd_spawn(args), 2)


class HardeningMarkerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name)
        self.run_git("init", "-q", "-b", "main")

    def tearDown(self):
        self.tmp.cleanup()

    def run_git(self, *argv: str) -> str:
        return subprocess.run(GIT + list(argv), cwd=self.path, capture_output=True, text=True, check=True).stdout.strip()

    def plan_sha(self) -> str:
        return self.run_git("rev-parse", "HEAD")

    def commit_plan(self, text: str) -> str:
        (self.path / "PLAN.md").write_text(text)
        self.run_git("add", "PLAN.md")
        self.run_git("commit", "-q", "-m", "plan")
        return self.plan_sha()

    def test_committed_plan_without_marker_is_hardened_false(self):
        self.commit_plan("# plan\n")
        self.assertFalse(o.plan_hardened(self.path))

    def test_marker_naming_the_plan_commit_is_hardened_true(self):
        sha = self.commit_plan("# plan\n")
        self.commit_plan(f"# plan\n<!-- hardened: {sha} -->\n")
        self.assertTrue(o.plan_hardened(self.path))

    def test_marker_naming_an_older_commit_is_hardened_false(self):
        sha = self.commit_plan("# plan\n")
        self.commit_plan(f"# plan changed\n<!-- hardened: {sha} -->\n")
        self.assertFalse(o.plan_hardened(self.path))

    def test_uncommitted_plan_is_never_hardened(self):
        (self.path / "PLAN.md").write_text("# plan\n")
        self.assertFalse(o.plan_hardened(self.path))

    def step(self) -> str:
        wt = o.Worktree(
            path=self.path, repo=self.path, branch="main", dirty=0, ahead=0,
            upstream="none", slug="", pull=None,
        )
        return o.step_for(wt, True, o.plan_hardened(self.path))

    def test_step_selects_hrd_build_hrd_for_the_three_marker_states(self):
        sha = self.commit_plan("# plan\n")
        self.assertEqual(self.step(), "HRD")
        self.commit_plan(f"# plan\n<!-- hardened: {sha} -->\n")
        self.assertEqual(self.step(), "BUILD")
        self.commit_plan(f"# plan changed\n<!-- hardened: {sha} -->\n")
        self.assertEqual(self.step(), "HRD")

    def herdr_calls(self, fake_run) -> list[str]:
        return [" ".join(call.args[0]) for call in fake_run.call_args_list if call.args[0][0] == "herdr"]

    def test_approve_refuses_an_unhardened_plan_then_approves_a_hardened_one(self):
        sha = self.commit_plan("# plan\n")
        wt = o.Worktree(
            path=self.path, repo=self.path, branch="main", dirty=0, ahead=0,
            upstream="none", slug="", pull=None, pane="p",
        )
        args = argparse.Namespace(repo=[self.path], base="main", inject=False, approve=True)
        real_run = o.run
        with patch.object(o, "collect", return_value=[wt]), patch.object(
            o, "run", side_effect=lambda cmd, **kw: "" if cmd[0] == "herdr" else real_run(cmd, **kw)
        ) as fake_run, patch("sys.stderr", new_callable=io.StringIO):
            o.cmd_plans(args)
        self.assertEqual(self.herdr_calls(fake_run), [])
        self.commit_plan(f"# plan\n<!-- hardened: {sha} -->\n")
        with patch.object(o, "collect", return_value=[wt]), patch.object(
            o, "run", side_effect=lambda cmd, **kw: "" if cmd[0] == "herdr" else real_run(cmd, **kw)
        ) as fake_run, patch("sys.stderr", new_callable=io.StringIO):
            o.cmd_plans(args)
        self.assertTrue(any("send-keys p 1" in call for call in self.herdr_calls(fake_run)))

class StallTests(unittest.TestCase):
    def worktree(self, step: str, status: str = "idle") -> o.Worktree:
        return o.Worktree(
            path=Path(f"/wt/{step}"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
            upstream="origin/b", slug="", pull=None, pane="p", name="m1",
            title="t", agent_status=status, last_subject="s", last_commit_at="",
        )

    def rows(self, step: str, status: str = "idle") -> list[dict]:
        args = argparse.Namespace(repo=[Path("/repo")], base="main")
        with patch.object(o, "collect", return_value=[self.worktree(step, status)]), patch.object(
            o, "plan_state", return_value=(True, step == "BUILD", "")
        ), patch.object(o, "step_for", return_value=step), patch.object(o, "last_line", return_value="done?"):
            return o.stall_rows(args)

    def test_only_unfinished_steps_that_are_idle_stall(self):
        for step in ("HRD", "BUILD", "REV", "REB", "MRG"):
            self.assertEqual([row["step"] for row in self.rows(step)], [step])
        for step in ("PLAN", "DONE", "IDLE"):
            self.assertEqual(self.rows(step), [])
        self.assertEqual(self.rows("BUILD", "working"), [])

    def test_row_carries_the_decision_evidence(self):
        row = self.rows("BUILD")[0]
        self.assertEqual((row["name"], row["title"], row["question"], row["tail"]), ("m1", "t", "yes", "done?"))
        self.assertIn("dirty paths", o.alert_text(row))
        self.assertIn("checks", o.alert_text(row))

    def test_alert_prompts_once_per_minion_and_step(self):
        with tempfile.TemporaryDirectory() as state:
            alerted = Path(state) / "alerted.json"
            args = argparse.Namespace(repo=[Path("/repo")], base="main", alert=True, once=True, interval=0)
            with patch.object(o, "ALERT_FILE", alerted), patch.object(o, "STATE_DIR", Path(state)), patch.object(
                o, "collect", return_value=[self.worktree("BUILD")]
            ), patch.object(o, "step_for", return_value="BUILD"), patch.object(
                o, "last_line", return_value=""
            ), patch.object(o, "ok", return_value=True) as prompt, patch("sys.stdout", new_callable=io.StringIO):
                o.cmd_watch(args)
                o.cmd_watch(args)
            self.assertEqual(prompt.call_count, 1)
            self.assertEqual(json.loads(alerted.read_text()), {"m1:BUILD": ["m1", "BUILD"]})


if __name__ == "__main__":
    unittest.main()
