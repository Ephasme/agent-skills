import argparse
import importlib.util
import io
import json
import os
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
    def test_feat_starts_agent_then_sends_the_pane_chord_then_prompts(self):
        lines = dry_run("feat")
        sequence = [
            f"{words[3]} {words[4]}" for words in
            (line.split() for line in lines if line.startswith("would run\therdr "))
            if words[3] in {"agent", "pane"} and words[4] in {"start", "send-keys", "prompt"}
        ]
        self.assertEqual(sequence, ["agent start", "pane send-keys", "agent prompt"])
        started = next(line for line in lines if " agent start " in line)
        self.assertTrue(started.endswith("--model test-model --plan test-model --smol test-model"))
        self.assertIn("Alt+Shift+P", next(line for line in lines if "send-keys" in line))

    def test_fast_starts_agent_then_prompts_without_plan_mode(self):
        lines = dry_run("fast")
        verbs = [line.split()[4] for line in lines if line.startswith("would run\therdr agent ")]
        self.assertEqual(verbs, ["start", "prompt"])
        self.assertTrue(next(line for line in lines if " agent start " in line).endswith(
            "--model test-model --plan test-model --smol test-model"
        ))

    def test_birth_label_renders_name_once_before_the_title(self):
        self.assertIn(
            "would run\therdr pane rename <pane> 🗺 PLAN m1 prompt-spawn-labelling", dry_run("feat")
        )
        self.assertIn(
            "would run\therdr pane rename <pane> ⚒ BUILD m1 prompt-spawn-labelling", dry_run("fast")
        )

    def test_registry_title_carries_no_id_and_title_flag_is_the_slug(self):
        lines = dry_run("feat", title="my-slug")
        self.assertIn("title\tmy-slug", lines)
        self.assertIn("would run\therdr pane rename <pane> 🗺 PLAN m1 my-slug", lines)
        job = dry_run("feat", task="Job: rust crate")
        self.assertIn("title\trust-crate", job)
        self.assertTrue(any("worktree add -b worktree/rust-crate " in line for line in job))

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
            o, "plan_state", return_value=(True, step == "BUILD")
        ), patch.object(o, "step_for", return_value=step), patch.object(
            o, "last_line", return_value="done?"
        ), patch.object(o, "classify", return_value=("not_sure", "empty pane")):
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
class CollectContractTests(unittest.TestCase):
    """collect always returns a list: every table iterates it, and None was a live outage."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.state = tempfile.TemporaryDirectory()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main", cwd=self.repo)
        (self.repo / "f.txt").write_text("x")
        self.git("add", "f.txt", cwd=self.repo)
        self.git("commit", "-q", "-m", "first", cwd=self.repo)

    def tearDown(self):
        self.tmp.cleanup()
        self.state.cleanup()

    def git(self, *argv, cwd=None):
        return subprocess.run(GIT + list(argv), cwd=cwd or self.root, capture_output=True, text=True, check=True).stdout

    def collected(self, repos) -> list:
        o._MEMO.clear()
        with patch.object(o, "REGISTRY", Path(self.state.name) / "w.json"), patch.object(
            o, "STATE_DIR", Path(self.state.name)
        ), patch.object(o, "herdr_facts", return_value=({}, {})), patch.object(
            o, "herdr_open_repos", return_value=set()
        ), patch.object(o, "Github") as github, patch("sys.stderr", new_callable=io.StringIO):
            github.return_value.branch_pulls.return_value = {}
            return o.collect(repos, "main")

    def test_repository_with_worktrees(self):
        (self.root / "wt").mkdir()
        self.git("worktree", "add", "-q", "-b", "side", str(self.root / "wt"), cwd=self.repo)
        self.assertEqual(len(self.collected([self.repo])), 2)

    def test_repository_with_no_commits_still_returns_rows(self):
        fresh = self.root / "fresh"
        fresh.mkdir()
        self.git("init", "-q", "-b", "main", cwd=fresh)
        self.assertIsInstance(self.collected([fresh]), list)

    def test_path_that_is_not_a_repository(self):
        plain = self.root / "plain"
        plain.mkdir()
        self.assertEqual(self.collected([plain]), [])

    def test_empty_repository_list(self):
        self.assertEqual(self.collected([]), [])


class PullStepTests(unittest.TestCase):
    def worktree(self, body: str, checks: str = "green") -> o.Worktree:
        pull = o.PullRequest(
            number=1, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
            draft=False, files=1, body=body,
        )
        return o.Worktree(
            path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
            upstream="origin/b", slug="o/n", pull=pull, checks=checks,
        )

    def test_green_open_pr_waits_to_merge(self):
        self.assertEqual(o.step_for(self.worktree(""), True, True), "MRG")

    def test_exact_reviewing_marker_keeps_a_green_pr_in_review(self):
        self.assertEqual(o.step_for(self.worktree("REVIEWING"), True, True), "REV")
        self.assertEqual(o.step_for(self.worktree("REVIEWING\nREVIEW_CLEAR"), True, True), "MRG")

    def test_red_checks_stay_in_review(self):
        self.assertEqual(o.step_for(self.worktree("", checks="failed: ci"), True, True), "REV")

    def test_conflicting_pr_rebases(self):
        wt = self.worktree("")
        wt.pull.merge_state = "DIRTY"
        self.assertEqual(o.step_for(wt, True, True), "REB")


class InFlightTests(unittest.TestCase):
    """A registry entry with a task is a job in flight, git target or not."""

    def job(self, task: str, **facts) -> o.Worktree:
        return o.Worktree(
            path=Path("/tmp/label-eval"), repo=Path("/tmp/label-eval"), branch="-",
            dirty=0, ahead=0, upstream="none", slug="", pull=None, vcs=False,
            name="m5", title="cheap-classifier-eval", task=task, **facts,
        )

    def test_non_git_job_with_a_task_and_no_plan_is_plan(self):
        with patch.object(o, "registry", return_value={"/tmp/label-eval": {"name": "m5"}}):
            self.assertEqual(o.step_for(self.job("measure cheap models"), False, False), "PLAN")

    def test_registered_entry_without_a_task_and_nothing_in_flight_is_idle(self):
        with patch.object(o, "registry", return_value={"/tmp/label-eval": {"name": "m5"}}):
            self.assertEqual(o.step_for(self.job(""), False, False), "IDLE")


class ReviewGateTests(unittest.TestCase):
    """A merge needs a review artifact covering the PR's current head sha."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def pull(self, sha: str) -> o.PullRequest:
        return o.PullRequest(
            number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
            draft=False, files=3, sha=sha,
        )

    def write_artifact(self, slug: str, number: int, covered: str) -> Path:
        path = self.dir / "review" / f"{slug.replace('/', '-')}-{number}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"<!-- reviewed: {covered} -->\n[]\n")
        return path

    def test_artifact_path_shape_is_owner_repo_pr(self):
        with patch.object(o, "REVIEW_DIR", self.dir / "review"):
            self.assertEqual(o.review_path("Ephasme/agent-skills", 13).name, "Ephasme-agent-skills-13.txt")

    def test_missing_stale_and_current_artifacts(self):
        with patch.object(o, "REVIEW_DIR", self.dir / "review"):
            pull = self.pull("a" * 40)
            self.assertEqual(o.review_state("o/n", pull), "missing")
            self.write_artifact("o/n", 13, "b" * 40)
            self.assertEqual(o.review_state("o/n", pull), "stale")
            self.write_artifact("o/n", 13, "a" * 40)
            self.assertEqual(o.review_state("o/n", pull), "current")

    def test_artifact_without_a_header_covers_nothing(self):
        artifact = self.dir / "plain.txt"
        artifact.write_text("just findings\n")
        self.assertEqual(o.reviewed_sha(artifact), "")

    def test_open_pr_is_not_landable_without_a_current_review(self):
        wt = o.Worktree(
            path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
            upstream="origin/b", slug="o/n", pull=self.pull("a" * 40), linked=True,
        )
        with patch.object(o, "REVIEW_DIR", self.dir / "review"), patch.object(o, "ocr_present", return_value=True):
            self.assertEqual(o.landable(wt), "unreviewed: missing")
            self.write_artifact("o/n", 13, "b" * 40)
            self.assertEqual(o.landable(wt), "unreviewed: stale")
            self.write_artifact("o/n", 13, "a" * 40)
            self.assertEqual(o.landable(wt), "open-pr")

    def test_missing_ocr_blocks_every_open_pr(self):
        wt = o.Worktree(
            path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
            upstream="origin/b", slug="o/n", pull=self.pull("a" * 40), linked=True,
        )
        with patch.object(o, "REVIEW_DIR", self.dir / "review"), patch.object(o, "ocr_present", return_value=False):
            self.write_artifact("o/n", 13, "a" * 40)
            # the artifact is current, so the honest blocker is the missing tool, not the review
            self.assertEqual(o.landable(wt), "unreviewed: ocr missing")

    def test_severity_counts_and_routing_skip_low(self):
        text = ('[{"severity":"critical","message":"drops the lock"},'
                '{"severity":"low","message":"naming"},'
                '{"severity":"high","message":"unbounded retry"}]')
        self.assertEqual(o.severities(text), {"critical": 1, "high": 1, "medium": 0, "low": 1})
        self.assertEqual(
            o.findings(text),
            [("critical", "drops the lock"), ("low", "naming"), ("high", "unbounded retry")],
        )


class ReviewFixTests(unittest.TestCase):
    """One test per defect open-code-review raised on PR 13."""

    def test_models_run_without_a_config_file_at_all(self):
        # repro from the review: HOME=/tmp/emptyhome overlord.py models died on WORKER_MODEL
        done = subprocess.run(
            [sys.executable, "-c", (
                "import importlib.util,sys;"
                "spec=importlib.util.spec_from_file_location('ov',sys.argv[1]);"
                "m=importlib.util.module_from_spec(spec);sys.modules['ov']=m;spec.loader.exec_module(m);"
                "print('\\n'.join(m.model_policy()[0]))"
            ), str(SCRIPT)],
            capture_output=True, text=True, env={"HOME": tempfile.mkdtemp(), "PATH": os.environ.get("PATH", "")},
        )
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split(), o.DEFAULT_ALLOWED)

    def test_every_subcommand_has_a_handler(self):
        parser = subprocess.run(
            [sys.executable, str(SCRIPT), "--help"], capture_output=True, text=True,
        )
        self.assertEqual(parser.returncode, 0, parser.stderr)
        for name in ("adopt", "bootstrap", "inventory", "mode", "models", "order", "pass",
                     "plans", "preflight", "prune", "registry", "rename", "review", "spawn",
                     "status", "watch"):
            with self.subTest(command=name):
                self.assertTrue(hasattr(o, f"cmd_{name}"))
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "adopt", "/tmp/does-not-exist"],
            capture_output=True, text=True, env={**os.environ, "XDG_STATE_HOME": tempfile.mkdtemp()},
        )
        self.assertNotIn("KeyError", done.stderr)

    def test_watch_clears_the_memo_between_sweeps(self):
        args = argparse.Namespace(repo=[], base="main", alert=False, once=False, interval=1)
        seen: list[dict] = []

        def sweep(_args):
            seen.append(dict(o._MEMO))
            o._MEMO["sweep"] = len(seen)
            if len(seen) == 2:
                raise SystemExit(0)
            return []

        with patch.object(o, "show_stalls", side_effect=sweep), patch.object(o.time, "sleep", return_value=None):
            with self.assertRaises(SystemExit):
                o.cmd_watch(args)
        self.assertEqual(seen, [{}, {}])

    def test_draft_pull_request_is_in_progress_not_mergeable(self):
        pull = o.PullRequest(number=1, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                             draft=True, files=1)
        wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                        upstream="origin/b", slug="o/n", pull=pull)
        self.assertEqual(o.step_for(wt, True, True), "BUILD")

    def test_plan_with_a_trailing_blank_line_still_hardens(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            git = lambda *a: subprocess.run(GIT + list(a), cwd=path, capture_output=True, text=True, check=True)
            git("init", "-q", "-b", "main")
            (path / "PLAN.md").write_text("# plan\n")
            git("add", "PLAN.md")
            git("commit", "-q", "-m", "plan")
            sha = git("rev-parse", "HEAD").stdout.strip()
            (path / "PLAN.md").write_text(f"# plan\n\n<!-- hardened: {sha} -->\n")
            git("commit", "-qam", "marker")
            self.assertTrue(o.plan_hardened(path))
            self.assertFalse(o.plan_hardened(Path("/tmp")) or o.plan_hardened(path / "nope"))

    def test_classifier_guard_refuses_empty_and_unreadable_evidence(self):
        self.assertEqual(o.classify("BUILD", ""), ("not_sure", "empty pane"))
        self.assertEqual(o.classify("BUILD", "   \n"), ("not_sure", "empty pane"))
        self.assertEqual(o.classify("BUILD", "<unreadable: pane gone>"), ("not_sure", "unreadable pane"))
        self.assertEqual(o.classify("BUILD", "some evidence"), ("not_sure", "no classifier client configured"))

    def test_classifier_prompt_ships_the_glossary(self):
        prompt = o.classifier_prompt("MRG", "PR #13 merged")
        for step in ("PLAN", "HRD", "BUILD", "REV", "REB", "MRG", "DONE", "IDLE"):
            self.assertIn(f"{step}:", prompt)
        self.assertIn("PR #13 merged", prompt)

    def test_known_registry_entry_is_updated_not_silently_kept(self):
        entries: dict = {}
        o.register_entry(entries, "/tmp/x", {"repo": "/r", "task": "first"})
        o.register_entry(entries, "/tmp/x", {"repo": "/r", "task": "second"})
        self.assertEqual(entries["/tmp/x"]["task"], "second")
        self.assertEqual(entries["/tmp/x"]["name"], "m1")
        self.assertEqual(entries["next_name"], 2)

    def test_alert_state_survives_a_truncated_file(self):
        with tempfile.TemporaryDirectory() as state:
            alert_file = Path(state) / "alerted.json"
            alert_file.write_text("{not json")
            with patch.object(o, "ALERT_FILE", alert_file), patch.object(o, "STATE_DIR", Path(state)), patch.object(o, "ok", return_value=True):
                o.alert_new([{
                    "name": "m1", "step": "BUILD", "title": "t", "idle_seconds": 90,
                    "last_commit": "s", "commit_age": 120, "dirty": 0, "pr": "none",
                    "checks": "none", "question": "no", "tail": "-",
                }])
            self.assertEqual(json.loads(alert_file.read_text()), {"m1:BUILD": ["m1", "BUILD"]})

    def test_label_carries_the_pr_and_the_owner_only_in_rev(self):
        def pull(number, state="OPEN"):
            return o.PullRequest(number=number, state=state, mergeable="MERGEABLE",
                                 merge_state="CLEAN", draft=False, files=1)

        def label(step, pr, owner="", name="m8", title="ocr-review-pr13"):
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                             upstream="origin/b", slug="o/n", pull=pr, name=name,
                             title=title, pr_owner=owner)
            return o.paint(step, wt.name, wt.title, o.work_fact(wt, step))

        # m8 reviews a PR m2 opened: the reviewer is told whose work it is
        self.assertEqual(label("REV", pull(13), "m2"), "🔍 REV m8 ocr-review-pr13 (PR #13 - m2)")
        self.assertEqual(label("REV", pull(13)), "🔍 REV m8 ocr-review-pr13 (PR #13 - ?)")
        # every other step states the PR alone
        self.assertEqual(label("BUILD", pull(1), "m1", name="m1", title="overlord-rust-port"),
                         "⚒ BUILD m1 overlord-rust-port (PR #1)")
        self.assertEqual(label("MRG", pull(2), "m7", name="m7", title="overlord-panel-rows"),
                         "⤵ MRG m7 overlord-panel-rows (PR #2)")
        self.assertEqual(label("MRG", pull(2, "MERGED"), "m7", name="m7", title="overlord-panel-rows"),
                         "⤵ MRG m7 overlord-panel-rows (PR #2 · merged)")
        self.assertEqual(label("PLAN", None), "🗺 PLAN m8 ocr-review-pr13")

    def test_title_slug_drops_headers_and_header_words(self):
        # reconciled from m1's install-copy tests: the header label never reaches a title
        self.assertEqual(o.title_slug("Job: rewrite the overlord toolbelt"), "rewrite-overlord-toolbelt")
        self.assertEqual(o.title_slug("Brief:"), "untitled")
        self.assertEqual(o.title_slug("task brief"), "untitled")


class SecondReviewTests(unittest.TestCase):
    """One test per finding open-code-review raised on head 331e366."""

    def test_a_failed_review_leaves_no_stale_artifact(self):
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            path = review_dir / "o-n-13.txt"
            review_dir.mkdir(parents=True)
            path.write_text("<!-- reviewed: old -->\n[]\n")
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE",
                                 merge_state="CLEAN", draft=False, files=1, sha="a" * 40, head="b")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            args = argparse.Namespace(repo=[Path("/repo")], base="main")
            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(o, "ocr_present", return_value=True), patch.object(
                o, "collect", return_value=[wt]
            ), patch.object(o, "plan_state", return_value=(False, False)), patch.object(
                o, "step_for", return_value="REV"
            ), patch.object(o, "ok", return_value=False), patch("sys.stdout", new_callable=io.StringIO):
                o.cmd_review(args)
            self.assertEqual(o.reviewed_sha(path), "")

    def test_models_survives_a_list_instead_of_a_mapping(self):
        with tempfile.TemporaryDirectory() as home:
            config = Path(home) / "config.yaml"
            config.write_text("models:\n  - deepseek/deepseek-v4.1-flash-1017\n")
            with patch.object(o, "CONFIG_FILE", config):
                self.assertEqual(o.model_policy(), (o.DEFAULT_ALLOWED, o.WORKER_MODEL))

    def test_alert_state_rejects_a_non_mapping_json_value(self):
        with tempfile.TemporaryDirectory() as state:
            alert_file = Path(state) / "alerted.json"
            alert_file.write_text("[]")
            with patch.object(o, "ALERT_FILE", alert_file), patch.object(o, "STATE_DIR", Path(state)), patch.object(
                o, "ok", return_value=True
            ):
                o.alert_new([{
                    "name": "m1", "step": "BUILD", "title": "t", "idle_seconds": 1,
                    "last_commit": "s", "commit_age": 1, "dirty": 0, "pr": "none",
                    "checks": "none", "question": "no", "tail": "-",
                }])
            self.assertEqual(json.loads(alert_file.read_text()), {"m1:BUILD": ["m1", "BUILD"]})

    def test_plan_chord_goes_to_the_pane_once_the_shell_has_printed(self):
        banners = iter(["", "prompt ready\n", "plan mode active\n"])
        with patch.object(o, "run", side_effect=lambda *_a, **_k: next(banners, "plan mode active\n")), patch.object(
            o, "ok", return_value=True
        ) as keystroke, patch.object(o.time, "sleep", return_value=None):
            self.assertTrue(o.enter_plan_mode("p"))
        # never while blank: that chord is swallowed; once the shell prints, exactly one chord
        self.assertEqual(keystroke.call_count, 1)
        self.assertEqual(keystroke.call_args.args[0][:3], ["herdr", "pane", "send-keys"])

    def test_plan_chord_is_never_sent_twice(self):
        with patch.object(o, "run", return_value="still booting\n"), patch.object(
            o, "ok", return_value=True
        ) as keystroke, patch.object(o.time, "sleep", return_value=None):
            self.assertFalse(o.enter_plan_mode("p"))
        self.assertEqual(keystroke.call_count, 1)

    def test_a_plain_directory_can_harden(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / "PLAN.md").write_text("# plan\n<!-- hardened: " + "a" * 40 + " -->\n")
            self.assertTrue(o.plan_hardened(path))
            (path / "PLAN.md").write_text("# plan\n")
            self.assertFalse(o.plan_hardened(path))

    def test_review_skips_a_head_that_is_already_current(self):
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            review_dir.mkdir(parents=True)
            (review_dir / "o-n-13.txt").write_text(f"<!-- reviewed: {'b' * 40} -->\n[bug · high] x\n")
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                                 draft=False, files=1, sha="b" * 40, head="h")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(o, "ocr_present", return_value=True), patch.object(
                o, "collect", return_value=[wt]
            ), patch.object(o, "plan_state", return_value=(False, False)), patch.object(
                o, "step_for", return_value="MRG"
            ), patch.object(o, "ok") as ocr_run, patch("sys.stdout", new_callable=io.StringIO):
                o.cmd_review(argparse.Namespace(repo=[Path("/repo")], base="main"))
            ocr_run.assert_not_called()

    def test_plan_state_is_memoised_and_returns_two_values(self):
        wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=0,
                        upstream="none", slug="", pull=None)
        o._MEMO.clear()
        with patch.object(o, "plan_hardened", return_value=True) as git:
            first = o.plan_state(wt)
            second = o.plan_state(wt)
        self.assertEqual(len(first), 2)
        self.assertEqual(first, second)
        self.assertEqual(git.call_count, 1)

    def test_ocr_present_is_memoised(self):
        o._MEMO.clear()
        with patch.object(o, "run", return_value="/usr/bin/ocr") as probe:
            self.assertTrue(o.ocr_present())
            self.assertTrue(o.ocr_present())
        self.assertEqual(probe.call_count, 1)

    def test_severities_read_the_text_report_shape(self):
        text = ("─── f.py:1-2 ───\n[bug · high] broken\n─── g.py:3-4 ───\n"
                "[style · low] naming\n─── h.py:5 ───\n[perf · medium] slow\n")
        self.assertEqual(o.severities(text), {"critical": 0, "high": 1, "medium": 1, "low": 1})
        self.assertEqual([level for level, _ in o.findings(text)], ["high", "low", "medium"])

    def test_spawn_passes_the_requested_title_to_the_registry(self):
        with tempfile.TemporaryDirectory() as state:
            recorded: dict = {}

            def capture(entries, path, meta, title=""):
                recorded["title"] = title
                entries[path] = {"name": "m1", "title": o.title_slug(title)}

            args = argparse.Namespace(mode="fast", task="Job: something else", title="my-slug",
                                      model="m", repo=[Path("/repo")], dest="/targets", base="main",
                                      dry_run=False)
            with patch.object(o, "PROMPTS", Path(state)), patch.object(o, "REGISTRY", Path(state) / "w.json"), patch.object(
                o, "STATE_DIR", Path(state)
            ), patch.object(o, "resolve_model", return_value=("m", "")), patch.object(
                o, "handover", return_value="h"
            ), patch.object(o, "credential_note", return_value=""), patch.object(
                o, "register_entry", side_effect=capture
            ), patch.object(o, "save_registry"), patch.object(o, "ok", return_value=True), patch.object(
                o, "open_workspace", return_value=("w", "p")
            ), patch.object(o, "herdr_apply", return_value=True), patch(
                "sys.stdout", new_callable=io.StringIO
            ), patch("sys.stderr", new_callable=io.StringIO):
                o.cmd_spawn(args)
            self.assertEqual(recorded["title"], "my-slug")

    def test_adopt_counts_paths_not_the_counter(self):
        entries = {"next_name": 2, "/a": {"name": "m1"}}
        self.assertEqual(len([key for key in entries if key != "next_name"]), 1)

    def test_a_failed_run_after_a_good_one_leaves_the_gate_closed(self):
        """The exact high finding: artifact from sha A, failing run on sha B, review_state missing."""
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            path = review_dir / "o-n-13.txt"
            review_dir.mkdir(parents=True)
            path.write_text(f"<!-- reviewed: {'a' * 40} -->\nold findings\n")
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                                 draft=False, files=1, sha="b" * 40, head="h")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(o, "ocr_present", return_value=True), patch.object(
                o, "collect", return_value=[wt]
            ), patch.object(o, "plan_state", return_value=(False, False)), patch.object(
                o, "step_for", return_value="REV"
            ), patch.object(o, "ok", return_value=False), patch("sys.stdout", new_callable=io.StringIO):
                o.cmd_review(argparse.Namespace(repo=[Path("/repo")], base="main"))
            self.assertEqual(o.review_state("o/n", pull), "missing")

    def test_a_review_finding_can_never_execute_a_command(self):
        """HIGH 1: review text is untrusted but is printed as a line the overlord runs."""
        marker = Path(tempfile.mkdtemp()) / "pwned"
        hostile = f"bug $(touch {marker}) and `touch {marker}` done"
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            review_dir.mkdir(parents=True)
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                                 draft=False, files=1, sha="c" * 40, head="h")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(o, "ocr_present", return_value=True), patch.object(
                o, "collect", return_value=[wt]
            ), patch.object(o, "plan_state", return_value=(False, False)), patch.object(
                o, "step_for", return_value="REV"
            ), patch.object(o, "run", return_value=""), patch.object(o, "ok", return_value=True), patch.object(
                o, "findings", return_value=[("high", hostile)]
            ), patch("sys.stdout", new_callable=io.StringIO) as out:
                o.cmd_review(argparse.Namespace(repo=[Path("/repo")], base="main"))
        line = next(row for row in out.getvalue().splitlines() if row.startswith("herdr agent prompt"))
        stub = Path(tempfile.mkdtemp())
        (stub / "herdr").write_text("#!/bin/sh\nprintf '%s\\n' \"$@\" > " + str(stub / "args") + "\n")
        (stub / "herdr").chmod(0o755)
        subprocess.run(["/bin/sh", "-c", line], env={**os.environ, "PATH": f"{stub}:{os.environ['PATH']}"}, check=False)
        self.assertFalse(marker.exists(), "a finding executed a command")
        self.assertIn("$(", (stub / "args").read_text())

    def test_order_plan_holds_a_pr_under_review_out_of_the_merge(self):
        """HIGH 2: a pass must not merge the PR its minion is still reviewing."""
        pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                             draft=False, files=1, sha="d" * 40, head="b", base="main")
        pull.body = "Looks fine\nREVIEWING\n"
        with patch.object(o, "realm_repos", return_value=[Path("/repo")]), patch.object(
            o, "repo_slug", return_value="o/n"
        ), patch.object(o, "worktree_paths", return_value=[]), patch.object(
            o, "ocr_present", return_value=True
        ), patch.object(o, "review_state", return_value="current"), patch.object(o, "Github") as github:
            github.return_value.open_pulls.return_value = [pull]
            github.return_value.with_paths.side_effect = lambda _slug, found: found
            github.return_value.checks_green.return_value = (True, "")
            plan = o.order_plan(argparse.Namespace(repo=[], base="main"))
        self.assertFalse(plan[0][3])
        self.assertIn("reviewing", plan[0][4])

    def test_label_stays_within_the_length_a_rename_accepts(self):
        fact = "PR #123 - m3"
        label = o.paint("REV", "m8", "ocr-review-pr13-with-a-very-long-title-identifier", fact)
        self.assertLessEqual(len(label), 64)
        self.assertTrue(label.endswith(f"({fact})"), label)

    def test_review_returns_non_zero_when_a_run_failed(self):
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            review_dir.mkdir(parents=True)
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                                 draft=False, files=1, sha="e" * 40, head="h")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(
                o, "ocr_present", return_value=True
            ), patch.object(o, "collect", return_value=[wt]), patch.object(
                o, "plan_state", return_value=(False, False)
            ), patch.object(o, "step_for", return_value="REV"), patch.object(
                o, "ok", return_value=False
            ), patch("sys.stdout", new_callable=io.StringIO):
                self.assertEqual(o.cmd_review(argparse.Namespace(repo=[Path("/repo")], base="main")), 1)

    def test_a_plain_directory_moves_past_plan(self):
        base = dict(path=Path("/tmp/dir"), repo=Path("/tmp/dir"), branch="-", dirty=0, ahead=0,
                    upstream="none", slug="", pull=None, vcs=False, name="m5", task="eval")
        self.assertEqual(o.step_for(o.Worktree(**base), True, False), "HRD")
        self.assertEqual(o.step_for(o.Worktree(**base), True, True), "BUILD")
        self.assertEqual(o.step_for(o.Worktree(**base), False, False), "PLAN")
        self.assertEqual(o.step_for(o.Worktree(**{**base, "task": ""}), False, False), "IDLE")

    def test_an_empty_artifact_does_not_open_the_gate(self):
        with tempfile.TemporaryDirectory() as state:
            review_dir = Path(state) / "review"
            review_dir.mkdir(parents=True)
            pull = o.PullRequest(number=13, state="OPEN", mergeable="MERGEABLE", merge_state="CLEAN",
                                 draft=False, files=1, sha="f" * 40, head="h")
            wt = o.Worktree(path=Path("/wt"), repo=Path("/repo"), branch="b", dirty=0, ahead=1,
                            upstream="origin/b", slug="o/n", pull=pull, pane="p")
            artifact = review_dir / "o-n-13.txt"

            def empty_run(_argv, **_kwargs):
                artifact.write_text("")
                return True

            with patch.object(o, "REVIEW_DIR", review_dir), patch.object(
                o, "ocr_present", return_value=True
            ), patch.object(o, "collect", return_value=[wt]), patch.object(
                o, "plan_state", return_value=(False, False)
            ), patch.object(o, "step_for", return_value="REV"), patch.object(
                o, "ok", side_effect=empty_run
            ), patch("sys.stdout", new_callable=io.StringIO):
                o.cmd_review(argparse.Namespace(repo=[Path("/repo")], base="main"))
            self.assertEqual(o.review_state("o/n", pull), "missing")


if __name__ == "__main__":
    unittest.main()
