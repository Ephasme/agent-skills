#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["httpx>=0.27", "pyyaml>=6"]
# ///
"""Overlord helpers for landing worktree pull requests.

Every fact and every ordering decision lives here, so a pass costs one script run and
almost no model reasoning:

    inventory   one row per git worktree of the repositories given
    status      exit 0 when no worktree holds landable work (a loop gate)
    order       the merge plan for the open PRs: clusters by touched files, stacks
                after their base, smallest diff first, plus what still blocks each
    plans       proposed plans and their hardening state; --inject sends
                /skill:harden-plan, --approve picks the first option (run the plan
                and drop the current context)
    prune       remove worktrees whose PR merged and whose tree is clean
                (--apply does it)

Pull requests come from the GitHub REST API with the token `gh auth token` hands out,
so a repository costs a couple of requests instead of one subprocess per branch.
herdr is optional throughout: it only adds the agent state per workspace and is the
only way to press a key in a pane.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml

STOP_FILE = Path(os.environ.get("LAND_WORK_STOP", f"{os.environ.get('TMPDIR', '/tmp')}/land-work-stop"))
IDLE_MINUTES = 20
ACTIVITY_FILE = Path(os.environ.get("TMPDIR", "/tmp")) / "overlord-last-active"
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "summon-the-overlord"
REGISTRY = STATE_DIR / "worktrees.json"
OVERLORD_DIR = Path(os.environ.get("OVERLORD_HOME", Path.home() / ".overlord"))
CONFIG_FILE = OVERLORD_DIR / "config.yaml"
PROMPTS = Path(os.environ.get("OVERLORD_PROMPTS", Path(__file__).resolve().parent.parent / "prompts"))
# `herdr agent start` takes the model on its own command line: this machine's config.yml
# leaves every modelRole at `nothing`, so an agent started without one dies on its first
HARDENED_RE = re.compile(r"^<!-- hardened: ([0-9a-f]{40,64}) -->$")
PLAN_TOGGLE = "Alt+Shift+P"


def model_policy() -> tuple[list[str], str]:
    models = read_yaml(CONFIG_FILE, "config").get("models") or {}
    allowed = [str(name) for name in (models.get("allowed") or [])]
    default = str(models.get("default") or (allowed[0] if allowed else WORKER_MODEL))
    return allowed, default


def resolve_model(requested: str) -> tuple[str, str]:
    allowed, default = model_policy()
    model = requested or default
    if allowed and model not in allowed:
        return "", f"model {model!r} is not allowed; use one of: {', '.join(allowed)}"
    return model, ""


def registry() -> dict[str, dict[str, str]]:
    """The worktrees this overlord owns: path -> repo, branch, mode, task, created_at.

    A corrupt registry raises instead of reading as empty: forgetting ownership would let
    prune and relabel walk past work this overlord still answers for.
    """
    if not REGISTRY.exists():
        return {}
    try:
        data = json.loads(REGISTRY.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"registry unreadable ({REGISTRY}): {error}")
    if not isinstance(data, dict):
        raise SystemExit(f"registry is not an object ({REGISTRY})")
    if backfill_names(data):
        save_registry(data)
    return data


def title_slug(source: str) -> str:
    words = [word for word in re.split(r"[^a-z0-9]+", source.lower()) if word]
    kept = [word for word in words if word not in STOP_WORDS][:4]
    return "-".join(kept) or "untitled"


def register_entry(entries: dict, path: str, meta: dict, title: str = "") -> None:
    if path in entries:
        return
    meta["name"] = f"m{entries.get('next_name', 1)}"
    entries["next_name"] = int(entries.get("next_name", 1)) + 1
    meta["title"] = title_slug(title or meta.get("task", "") or Path(path).name)
    entries[path] = meta


def backfill_names(entries: dict) -> bool:
    changed = False
    if "next_name" not in entries:
        numbers = [int(meta["name"][1:]) for key, meta in entries.items()
                   if key != "next_name" and isinstance(meta, dict)
                   and re.fullmatch(r"m[1-9][0-9]*", meta.get("name", ""))]
        entries["next_name"] = max(numbers, default=0) + 1
        changed = True
    for path in sorted(key for key in entries if key != "next_name"):
        meta = entries[path]
        if "name" not in meta:
            meta["name"] = f"m{entries['next_name']}"
            entries["next_name"] += 1
            changed = True
        if "title" not in meta:
            source = meta.get("task", "")
            if not source and meta.get("kind") == "git":
                source = run(["git", "-C", path, "log", "-1", "--format=%s"])
            meta["title"] = title_slug(source or Path(path).name)
            changed = True
    return changed


def save_registry(entries: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRY.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(entries, indent=2, sort_keys=True))
    temporary.replace(REGISTRY)


def read_yaml(path: Path, what: str) -> dict:
    """A YAML state file: empty when absent, an error when unreadable.

    A corrupt config never reads as empty: preflight would forget that it already ran.
    """
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except (OSError, yaml.YAMLError) as error:
        raise SystemExit(f"{what} unreadable ({path}): {error}")
    if not isinstance(data, dict):
        raise SystemExit(f"{what} is not a mapping ({path})")
    return data


def write_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(yaml.safe_dump(data, sort_keys=False))
    temporary.replace(path)


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")



# A pass is one process: every table reuses the facts already read, so a bootstrap costs
# one GitHub round trip and one git probe per worktree instead of one per command.
_MEMO: dict = {}


def shared(key, build):
    if key not in _MEMO:
        _MEMO[key] = build()
    return _MEMO[key]


def own_workspace() -> str:
    """The workspace this overlord runs in: the realm every adopted target moves into."""
    return os.environ.get("HERDR_WORKSPACE_ID") or os.environ.get("HERDR_PANE_ID", "").split(":")[0]


def herdr_json(argv: list[str]) -> dict:
    """One herdr command's result object: empty when herdr is absent or answers garbage."""
    try:
        return json.loads(run(argv) or "{}").get("result") or {}
    except json.JSONDecodeError:
        return {}


def herdr_agents() -> dict[str, dict]:
    """workspace id -> the live agent record there, session file included. Empty without herdr."""
    if os.environ.get("HERDR_ENV") != "1":
        return {}
    return {agent.get("workspace_id", ""): agent for agent in herdr_json(["herdr", "agent", "list"]).get("agents", [])}


def herdr_places() -> dict[str, list[str]]:
    """workspace id -> every path it holds: its checkout and its panes' working directories."""
    if os.environ.get("HERDR_ENV") != "1":
        return {}
    places = {
        ws.get("workspace_id", ""): [(ws.get("worktree") or {}).get("checkout_path") or ""]
        for ws in herdr_json(["herdr", "workspace", "list"]).get("workspaces", [])
    }
    for pane in herdr_json(["herdr", "pane", "list"]).get("panes", []):
        places.setdefault(pane.get("workspace_id", ""), []).extend(
            path for path in (pane.get("foreground_cwd"), pane.get("cwd")) if path
        )
    return places


def agent_name(path: Path) -> str:
    """A live herdr identity: the registered minion name, else the checkout slug."""
    meta = registry().get(str(path.resolve()))
    if meta and meta.get("name"):
        return meta["name"]
    slug = re.sub(r"[^a-z0-9-]+", "-", path.name.lower()).strip("-") or "adopted"
    return (slug if slug[:1].isalpha() else f"a-{slug}")[:32].rstrip("-") or "adopted"


def enter_plan_mode(pane: str) -> bool:
    """Toggle omp plan mode with its own keybinding, then prove it took from the pane banner.

    A chord sent while the shell is still starting is swallowed, hence the retry: `spawn` must
    never hand feat work over in normal mode, where the minion implements before any plan.
    """
    for _ in range(10):
        if ok(["herdr", "agent", "send-keys", pane, PLAN_TOGGLE]) and "plan mode" in run(
            ["herdr", "pane", "read", pane, "--source", "recent", "--lines", "40"]
        ).lower():
            return True
        time.sleep(1)
    return False


def start_agent(name: str, pane: str, model: str) -> bool:
    """Start omp with explicit main, plan and smol models; nothing is never inherited."""
    for _ in range(10):
        if ok(["herdr", "agent", "start", name, "--kind", "omp", "--pane", pane, "--", "--model", model, "--plan", model, "--smol", model], timeout=120):
            return True
        time.sleep(1)
    return False


def open_workspace(path: Path, model: str) -> tuple[str, str]:
    """Open a plain herdr workspace on this checkout and start its minion."""
    created = herdr_json(["herdr", "workspace", "create", "--cwd", str(path), "--no-focus"])
    pane = (created.get("root_pane") or {}).get("pane_id", "")
    workspace = ((created.get("workspace") or {}).get("workspace_id")
                 or (created.get("root_pane") or {}).get("workspace_id", ""))
    if not pane:
        return workspace, ""
    return workspace, (pane if start_agent(agent_name(path), pane, model) else "")


def resume_agent(record: dict, pane: str, path: Path) -> str:
    """Start the moved agent again and point it at the session file it lost."""
    model, refusal = resolve_model("")
    if refusal or not start_agent(agent_name(path), pane, model):
        return "agent restart failed"
    session = (record.get("agent_session") or {}).get("value", "")
    if not session:
        return "agent restarted, no session file to resume"
    instruction = f"Your pane moved to a new workspace. Resume the session at {session} and carry on where you left off."
    if not ok(["herdr", "agent", "prompt", pane, instruction]):
        return "agent restarted, resume prompt failed"
    return "agent resumed"


def relocate(path: Path, places: dict[str, list[str]], agents: dict[str, dict], realm: str) -> str:
    """Cut the target from whatever workspace holds it, then reopen it below the realm.

    Unconditional: a working agent is closed like an idle one, then restarted from its session
    file on the new pane. worktree open is refused across repositories, so the reopen is always
    a workspace create, and each adopted target is a workspace, never a tab under the overlord.
    """
    if not realm:
        return "no herdr: not moved"
    resolved = str(path.resolve())
    held = next((ws for ws, paths in places.items() if any(p and str(Path(p).resolve()) == resolved for p in paths)), "")
    if held == realm:
        return f"in realm {realm}"
    record = agents.get(held, {})
    if held and not ok(["herdr", "workspace", "close", held]):
        return f"kept: {held} refused to close"
    created = herdr_json(["herdr", "workspace", "create", "--cwd", str(path), "--no-focus"])
    pane = (created.get("root_pane") or {}).get("pane_id", "")
    reopened = ((created.get("workspace") or {}).get("workspace_id")
                or (created.get("root_pane") or {}).get("workspace_id", ""))
    if not pane or not reopened:
        return "closed, reopen failed"
    places.pop(held, None)
    agents.pop(held, None)
    places[reopened] = [str(path)]
    move = f"{held}→{reopened}" if held else f"opened {reopened}"
    return f"{move}, {resume_agent(record, pane, path)}" if record else f"{move}, no agent"


def cmd_adopt(args: argparse.Namespace) -> int:
    """Take over worktrees this overlord did not create, and move them into its own realm."""
    places = herdr_places()
    agents = herdr_agents()
    realm = own_workspace() if places else ""

    entries = registry()
    print("#target\tpath\tbranch\tstate\trealm")
    adopted = 0
    for target in args.targets:
        path_text = next((p for p in places.get(target, []) if p), target)
        path = Path(path_text).expanduser()
        if not path.is_dir():
            print(f"{target}\t{path}\t-\tmissing\t-")
            continue
        toplevel = run(["git", "-C", str(path), "rev-parse", "--show-toplevel"])
        repo = Path(toplevel) if toplevel else path
        branch = run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]) or "-" if toplevel else "-"
        resolved = str(path.resolve())
        if resolved in entries:
            print(f"{target}\t{path}\t{branch}\talready owned\t-")
            continue
        kind = "git" if toplevel else "dir"
        meta = {"repo": str(repo), "branch": branch, "mode": "adopted", "task": args.task, "kind": kind}
        title = args.task or (run(["git", "-C", str(path), "log", "-1", "--format=%s"]) if toplevel else "") or path.name
        register_entry(entries, resolved, meta, title)
        adopted += 1
        print(f"{target}\t{path}\t{branch}\tadopted\t{relocate(path, places, agents, realm)}")
    if adopted:
        save_registry(entries)
    print(f"\nowned worktrees: {len(entries)}")
    return 0 if adopted or entries else 1


def cmd_registry(args: argparse.Namespace) -> int:
    entries = registry()
    if args.path:
        for path in entries:
            if path != "next_name":
                print(path)
        return 0
    if args.add:
        entries = registry()
        for path in args.add:
            resolved = str(Path(path).expanduser().resolve())
            register_entry(entries, resolved, {"repo": args.source_repo or "", "task": args.task or ""})
        save_registry(entries)
        print(f"registered {len(args.add)} path(s)")
        return 0
    if args.remove:
        entries = registry()
        for path in args.remove:
            entries.pop(str(Path(path).expanduser().resolve()), None)
        save_registry(entries)
        print(f"removed {len(args.remove)} path(s)")
        return 0
    if args.rename_list:
        by_path, _by_ws = herdr_facts()
        labels = {
            str(Path((ws.get("worktree") or {}).get("checkout_path", "")).resolve()): ws.get("label", "")
            for ws in json.loads(run(["herdr", "workspace", "list"]) or "{}").get("result", {}).get("workspaces", [])
            if (ws.get("worktree") or {}).get("checkout_path")
        } if os.environ.get("HERDR_ENV") == "1" else {}
        print("#workspace\tlabel\tpath")
        for path, meta in sorted(entries.items()):
            if path == "next_name":
                continue
            workspace = by_path.get(str(Path(path).resolve()), "-")
            print(f"{workspace}\t{labels.get(str(Path(path).resolve()), meta.get('task', ''))[:40]}\t{path}")
        return 0
    print(json.dumps(entries, indent=2, sort_keys=True))
    return 0
LEGACY_STOP = Path(os.environ.get("TMPDIR", "/tmp")) / "merge-agents-stop"
PLAN_FILE = "PLAN.md"
HARDEN = "/skill:harden-plan"
API = "https://api.github.com"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120, env: dict[str, str] | None = None) -> str:
    try:
        done = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, **env} if env else None,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def ok(cmd: list[str], timeout: int = 60) -> bool:
    """True when the command ran and exited 0. gh writes status to stderr, so stdout is useless."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def gh_accounts() -> list[tuple[str, str, bool]]:
    """(login, token, active) for every account gh is logged into, the active one first.

    gh holds one active account per host, so a pass that spans two organisations picks
    per repository instead of switching the machine's account under the user.
    """
    return shared("gh_accounts", _gh_accounts)


def _gh_accounts() -> list[tuple[str, str, bool]]:
    try:
        hosts = json.loads(run(["gh", "auth", "status", "--json", "hosts"]) or "{}").get("hosts") or {}
    except json.JSONDecodeError:
        return []
    found = [
        (entry.get("login", ""), bool(entry.get("active")))
        for entries in hosts.values()
        for entry in entries
        if entry.get("state") == "success" and entry.get("login")
    ]
    found.sort(key=lambda row: not row[1])
    rows: list[tuple[str, str, bool]] = []
    for login, active in found:
        if token := run(["gh", "auth", "token", "--user", login]):
            rows.append((login, token, active))
    return rows


def repo_access(slug: str, token: str) -> dict:
    """The repository object when this token can see it, else empty."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = httpx.get(f"{API}/repos/{slug}", headers=headers, timeout=20)
    except httpx.HTTPError:
        return {}
    return response.json() if response.status_code == 200 else {}


_CREDENTIAL: dict[str, tuple[str, str, bool]] = {}


def credential(slug: str) -> tuple[str, str, bool]:
    """(login, token, readable) for one repository: an account that can push wins, else one that can read.

    An explicit GITHUB_TOKEN or GH_TOKEN pins every repository to it.
    """
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if token := os.environ.get(name):
            return "-", token, True
    if slug in _CREDENTIAL:
        return _CREDENTIAL[slug]
    fallback: tuple[str, str, bool] = ("-", "", False)
    for login, token, _active in gh_accounts():
        repo = repo_access(slug, token)
        if not repo:
            continue
        if (repo.get("permissions") or {}).get("push"):
            _CREDENTIAL[slug] = (login, token, True)
            return _CREDENTIAL[slug]
        fallback = fallback if fallback[2] else (login, token, True)
    _CREDENTIAL[slug] = fallback
    return fallback


def repo_slug(path: Path) -> str:
    """owner/name from any remote URL: ssh alias, ssh, or https."""
    url = run(["git", "-C", str(path), "remote", "get-url", "origin"])
    if not url:
        return ""
    tail = url.rsplit(":", 1)[-1].removeprefix("//")
    tail = tail.replace("https://", "").replace("http://", "")
    if "/" in tail and "." in tail.split("/", 1)[0]:
        tail = tail.split("/", 1)[1]
    parts = [part for part in tail.removesuffix(".git").split("/") if part]
    return "/".join(parts[-2:]) if len(parts) >= 2 else ""


def worktree_paths(repo: Path) -> list[Path]:
    out = run(["git", "-C", str(repo), "worktree", "list", "--porcelain"])
    return [Path(line.removeprefix("worktree ")) for line in out.splitlines() if line.startswith("worktree ")]


def herdr_facts() -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    """checkout path -> workspace id, workspace id -> (agent state, pane). Empty without herdr."""
    return shared("herdr_facts", _herdr_facts)


def _herdr_facts() -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    if os.environ.get("HERDR_ENV") != "1":
        return {}, {}
    try:
        workspaces = json.loads(run(["herdr", "workspace", "list"]) or "{}")
        agents = json.loads(run(["herdr", "agent", "list"]) or "{}")
    except json.JSONDecodeError:
        return {}, {}
    by_path = {
        str(Path(checkout).resolve()): ws.get("workspace_id", "")
        for ws in workspaces.get("result", {}).get("workspaces", [])
        for checkout in [(ws.get("worktree") or {}).get("checkout_path", "")]
        if checkout
    }
    # A plain workspace holds no herdr worktree record; its pane's directory is the only
    # place its checkout shows up, and it is where this skill puts every job anyway.
    for pane in herdr_json(["herdr", "pane", "list"]).get("panes", []):
        cwd = pane.get("foreground_cwd") or pane.get("cwd") or ""
        if cwd:
            by_path.setdefault(str(Path(cwd).resolve()), pane.get("workspace_id", ""))
    by_ws = {
        agent.get("workspace_id", ""): (agent.get("agent_status", "unknown"), agent.get("pane_id", ""))
        for agent in agents.get("result", {}).get("agents", [])
    }
    return by_path, by_ws


@dataclass
class PullRequest:
    number: int
    state: str
    mergeable: str
    merge_state: str
    draft: bool
    files: int
    head: str = ""
    base: str = ""
    sha: str = ""
    paths: list[str] = field(default_factory=list)
    updated_at: str = ""
    body: str = ""


def pull_from_json(pull: dict) -> PullRequest:
    """REST reports a merged pull request as closed, with merged_at set."""
    state = "MERGED" if pull.get("merged_at") or pull.get("merged") else str(pull.get("state", "")).upper()
    return PullRequest(
        number=int(pull.get("number", 0)),
        state=state,
        mergeable=str(pull.get("mergeable") or "-").upper(),
        merge_state=str(pull.get("mergeable_state") or "-").upper(),
        draft=bool(pull.get("draft", False)),
        files=int(pull.get("changed_files", 0) or 0),
        head=((pull.get("head") or {}).get("ref") or ""),
        base=((pull.get("base") or {}).get("ref") or ""),
        sha=((pull.get("head") or {}).get("sha") or ""),
        updated_at=str(pull.get("updated_at") or pull.get("merged_at") or ""),
        body=str(pull.get("body") or ""),
    )


class Github:
    def __init__(self) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        self.client = httpx.Client(headers=headers, timeout=30)
        self.pulls: dict[str, dict[str, PullRequest]] = {}

    def get(self, slug: str, path: str = "", **params) -> httpx.Response:
        """One request as the account that reaches this repository, so two orgs fit in one pass."""
        _login, token, _readable = credential(slug)
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return self.client.get(f"{API}/repos/{slug}{path}", params=params, headers=headers)

    def account(self, slug: str) -> str:
        """The login this pass acts as on that repository: what a gh command has to be told."""
        return credential(slug)[0]

    def branch_pulls(self, slug: str) -> dict[str, PullRequest]:
        """branch -> its most relevant PR: an open one wins over merged or closed."""
        if slug in self.pulls:
            return self.pulls[slug]
        found: dict[str, PullRequest] = {}
        response = self.get(slug, "/pulls", state="all", per_page=100, sort="updated")
        if response.status_code != 200:
            print(f"github: {slug}: {response.status_code} {response.text[:120]}", file=sys.stderr)
            self.pulls[slug] = found
            return found
        for raw in response.json():
            pull = pull_from_json(raw)
            current = found.get(pull.head)
            if current is None or [pull.state, current.state].count("OPEN") == 1 and pull.state == "OPEN":
                found[pull.head] = pull
        self.pulls[slug] = found
        return found

    def open_pulls(self, slug: str) -> list[PullRequest]:
        response = self.get(slug, "/pulls", state="open", per_page=100)
        if response.status_code != 200:
            print(f"github: {slug}: {response.status_code} {response.text[:120]}", file=sys.stderr)
            return []
        return [pull_from_json(raw) for raw in response.json()]

    def readable(self, slug: str) -> bool:
        """Whether an account here can see the repository at all: what makes its PRs invisible."""
        return self.get(slug).status_code == 200

    def with_paths(self, slug: str, pull: PullRequest) -> PullRequest:
        """The pull request with its touched files: one request, not a second fetch of the row."""
        files = self.get(slug, f"/pulls/{pull.number}/files", per_page=100)
        if files.status_code == 200:
            pull.paths = [item.get("filename", "") for item in files.json() if item.get("filename")]
        return pull

    def checks_green(self, slug: str, number: int, sha: str = "") -> tuple[bool, str]:
        sha = sha or self.head_sha(slug, number)
        if not sha:
            return False, "unknown: head sha unavailable"
        response = self.get(slug, f"/commits/{sha}/check-runs")
        if response.status_code != 200:
            return False, f"unknown: check-runs {response.status_code}"
        runs = response.json().get("check_runs", [])
        if not runs:
            return True, ""
        bad = [
            run_["name"]
            for run_ in runs
            if run_.get("status") == "completed" and run_.get("conclusion") not in {"success", "skipped", "neutral"}
        ]
        pending = [run_["name"] for run_ in runs if run_.get("status") != "completed"]
        if bad:
            return False, "failed: " + ", ".join(bad[:3])
        if pending:
            return False, "pending: " + ", ".join(pending[:3])
        return True, ""

    def head_sha(self, slug: str, number: int) -> str:
        response = self.get(slug, f"/pulls/{number}")
        if response.status_code != 200:
            return ""
        return (response.json().get("head") or {}).get("sha", "")


@dataclass
class Worktree:
    path: Path
    repo: Path
    branch: str
    dirty: int
    ahead: int
    upstream: str
    slug: str
    pull: PullRequest | None
    agent: str = "-"
    pane: str = "-"
    vcs: bool = True
    linked: bool = False
    name: str = "-"
    title: str = ""
    agent_status: str = "unknown"
    last_subject: str = ""
    last_commit_at: str = ""
    checks: str = "none"
    task: str = ""


def registry_repos() -> list[Path]:
    """Repositories of adopted worktrees, so a target outside --repo is still overseen."""
    return sorted({Path(meta["repo"]) for key, meta in registry().items() if key != "next_name" and meta.get("repo") and Path(meta["repo"]).is_dir()})


def herdr_open_repos() -> set[Path]:
    """Repository roots holding a live pane: a checkout the user put in herdr themselves."""
    return shared("herdr_open_repos", _herdr_open_repos)


def _herdr_open_repos() -> set[Path]:
    if os.environ.get("HERDR_ENV") != "1":
        return set()
    try:
        panes = json.loads(run(["herdr", "pane", "list"]) or "{}")
    except json.JSONDecodeError:
        return set()
    repos: set[Path] = set()
    for pane in panes.get("result", {}).get("panes", []):
        for key in ("foreground_cwd", "cwd"):
            cwd = pane.get(key) or ""
            if not cwd:
                continue
            common = run(["git", "-C", cwd, "rev-parse", "--path-format=absolute", "--git-common-dir"])
            if common:
                repos.add(Path(common).parent if Path(common).name == ".git" else Path(common))
    return repos


def realm_repos(named: list[Path]) -> list[Path]:
    """Explicit repositories, owned worktrees' repos, and repositories open in herdr."""
    found = {Path(repo).expanduser().resolve() for repo in [*named, *registry_repos(), *herdr_open_repos()]}
    return sorted(repo for repo in found if repo.is_dir())



def collect(repos: list[Path], base: str) -> list[Worktree]:
    """One row per worktree, read once per pass: every table below shares these facts.

    Always a list, empty when nothing is in the realm: every caller iterates the result.
    """
    key = ("collect", tuple(sorted(str(Path(repo).expanduser().resolve()) for repo in repos)), base)
    rows = shared(key, lambda: _collect(repos, base))
    return rows if isinstance(rows, list) else []


def _collect(repos: list[Path], base: str) -> list[Worktree]:
    github = shared("github", Github)
    by_path, by_ws = herdr_facts()
    rows: list[Worktree] = []
    seen: set[Path] = set()
    identities = {
        str(Path(path).resolve()): meta
        for path, meta in registry().items() if path != "next_name"
    }
    repos = realm_repos(repos)
    for repo in repos:
        if not run(["git", "-C", str(repo), "rev-parse", "--git-dir"]):
            print(f"not a git repository: {repo}", file=sys.stderr)
            continue
        registry_paths = {Path(path) for path in identities}
        registered = {
            Path(path)
            for path, meta in identities.items()
            if meta.get("repo") and Path(meta["repo"]).resolve() == repo.resolve()
        }
        for path in sorted(registry_paths):
            if path in seen or not path.is_dir():
                continue
            if run(["git", "-C", str(path), "rev-parse", "--git-dir"]):
                continue
            seen.add(path)
            workspace = by_path.get(str(path.resolve()), "")
            meta = identities.get(str(path.resolve()), {})
            agent, pane = by_ws.get(workspace, ("-", "-")) if workspace else ("-", "-")
            rows.append(Worktree(
                path=path, repo=path, branch="-", dirty=0, ahead=0, upstream="none",
                slug="", pull=None, agent=agent, pane=pane, vcs=False,
                name=meta.get("name", "-"), title=meta.get("title", ""),
                task=str(meta.get("task") or ""),
                agent_status=by_ws.get(workspace, ("unknown", "-"))[0] if workspace else "unknown",
            ))
        for path in worktree_paths(repo) + sorted(registered):
            if not path.is_dir() or path in seen:
                continue
            seen.add(path)
            branch = run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"]) or "-"
            status = run(["git", "-C", str(path), "status", "--porcelain"])
            dirty = len([line for line in status.splitlines() if line.strip()])
            ahead_text = run(["git", "-C", str(path), "rev-list", "--count", f"origin/{base}..HEAD"])
            slug = repo_slug(path)
            workspace = by_path.get(str(path.resolve()), "")
            meta = identities.get(str(path.resolve()), {})
            agent, pane = by_ws.get(workspace, ("-", "-")) if workspace else ("-", "-")
            pull = github.branch_pulls(slug).get(branch) if slug else None
            rows.append(Worktree(
                path=path, repo=repo, branch=branch, dirty=dirty,
                ahead=int(ahead_text) if ahead_text.isdigit() else 0,
                upstream=run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{u}"]) or "none",
                slug=slug, pull=pull,
                agent=agent, pane=pane, linked=path.resolve() != repo.resolve(),
                name=meta.get("name", "-"), title=meta.get("title", ""),
                task=str(meta.get("task") or ""),
                agent_status=by_ws.get(workspace, ("unknown", "-"))[0] if workspace else "unknown",
                last_subject=run(["git", "-C", str(path), "log", "-1", "--format=%s"]),
                last_commit_at=run(["git", "-C", str(path), "log", "-1", "--format=%cI"]),
                checks=(shared(("checks", slug, pull.number), lambda: github.checks_green(slug, pull.number, pull.sha)[1] or "green")
                        if pull and pull.state == "OPEN" else "none"),
            ))
    return rows


def landable(wt: Worktree) -> str:
    """Empty when landed or empty; otherwise why it still holds work."""
    if not wt.vcs or not wt.linked:
        return ""
    if wt.dirty:
        return "dirty"
    if wt.pull and wt.pull.state == "OPEN":
        # a review of an older commit is evidence about that commit, never about this head
        state = review_state(wt.slug, wt.pull)
        return "open-pr" if state == "current" and ocr_present() else f"unreviewed: {state}"
    if wt.pull and wt.pull.state == "MERGED":
        return ""
    return "no-pr" if wt.ahead > 0 else ""


def cmd_inventory(args: argparse.Namespace) -> int:
    columns = ("path", "branch", "dirty", "ahead", "upstream", "slug", "pr", "state", "mergeable", "draft", "files", "agent", "pane")
    print("#" + "\t".join(columns))
    for wt in collect(args.repo, args.base):
        pull = wt.pull
        print(
            "\t".join(
                str(value)
                for value in (
                    wt.path, wt.branch, wt.dirty, wt.ahead, wt.upstream, wt.slug or "-",
                    pull.number if pull else "-", pull.state if pull else "-",
                    pull.mergeable if pull else "-", str(pull.draft).lower() if pull else "-",
                    pull.files if pull else "-", wt.agent, wt.pane,
                )
            )
        )
    return 0


def consume_stop() -> bool:
    for path in (STOP_FILE, LEGACY_STOP):
        if path.is_file():
            path.unlink(missing_ok=True)
            print(f"stop file consumed: {path}")
            return True
    return False


def cmd_status(args: argparse.Namespace) -> int:
    if args.stop:
        STOP_FILE.write_text("")
        print(f"stop file created: {STOP_FILE}")
        return 0
    if consume_stop():
        return 0
    # realm only: a pass never waits on a repository it may not touch
    realm = {repo.resolve() for repo in realm_repos(args.repo)}
    rows = [wt for wt in collect(args.repo, args.base) if wt.repo.resolve() in realm]
    # a pass with work in flight keeps a loop alive; once nothing is landable, only
    # a quiet spell stops it, so a worker mid-turn is never cut off
    if any(landable(wt) or wt.agent == "working" for wt in rows):
        ACTIVITY_FILE.write_text(str(int(time.time())))
    remaining = 0
    for wt in rows:
        reason = landable(wt)
        if reason:
            remaining += 1
        if args.verbose or reason:
            print(f"{wt.path.name}\t{reason or 'landed'}")
    if remaining:
        return 1
    idle_minutes = (time.time() - ACTIVITY_FILE.stat().st_mtime) / 60 if ACTIVITY_FILE.exists() else 1e9
    if idle_minutes >= args.idle_minutes:
        return 0
    print(
        f"waiting\t{int(idle_minutes)}m idle of {args.idle_minutes}m: nothing landable, nothing in flight",
        file=sys.stderr,
    )
    return 1


def clusters(pulls: list[PullRequest]) -> dict[int, int]:
    """PR number -> cluster id, where an id groups every PR whose file sets intersect."""
    parent = {pull.number: pull.number for pull in pulls}

    def find(number: int) -> int:
        while parent[number] != number:
            parent[number] = parent[parent[number]]
            number = parent[number]
        return number

    for index, left in enumerate(pulls):
        for right in pulls[index + 1 :]:
            if set(left.paths) & set(right.paths):
                parent[find(right.number)] = find(left.number)
    return {pull.number: find(pull.number) for pull in pulls}


def stack_depth(pull: PullRequest, by_head: dict[str, PullRequest]) -> int:
    """How many pulls this one sits on inside the plan: its position in the stack."""
    depth, seen = 0, set()
    while pull.base in by_head and pull.base not in seen:
        seen.add(pull.base)
        pull = by_head[pull.base]
        depth += 1
    return depth


def order_plan(args: argparse.Namespace) -> list[tuple[int, str, PullRequest, bool, str, int, int, str]]:
    """The merge plan as data: (files, slug, pull, ready, blockers, cluster, depth, worktree)."""
    github = shared("github", Github)
    plan: list[tuple[int, str, PullRequest, bool, str, int, int, str]] = []
    for repo in realm_repos(args.repo):
        slug = repo_slug(repo)
        if not slug:
            continue
        checkouts: dict[str, Path] = {}
        for path in worktree_paths(repo):
            branch = run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"])
            checkouts.setdefault(branch, path)
        # every open pull request counts, checked out locally or not: one whose worktree was
        # pruned is still work this pass owes, not a pull request to abandon silently
        pulls = [github.with_paths(slug, pull) for pull in github.open_pulls(slug)]
        groups = clusters(pulls)
        by_head = {pull.head: pull for pull in pulls}
        for pull in pulls:
            green, blocker = github.checks_green(slug, pull.number, pull.sha)
            blockers = []
            if pull.draft:
                blockers.append("draft")
            if pull.merge_state != "CLEAN":
                blockers.append(f"mergeable={pull.merge_state if pull.merge_state != '-' else 'unknown'}")
            if not green:
                blockers.append(blocker)
            review = review_state(slug, pull)
            if not ocr_present():
                blockers.append("unreviewed: ocr missing")
            elif review != "current":
                blockers.append(f"unreviewed: {review}")
            if pull.base in by_head:
                blockers.append(f"stacked on {pull.base}")
            plan.append(
                (
                    len(pull.paths), slug, pull, not blockers,
                    "; ".join(b for b in blockers if b), groups[pull.number],
                    stack_depth(pull, by_head), str(checkouts.get(pull.head, "-")),
                )
            )

    # stack depth first so a stacked pull stays behind its base, then cluster,
    # smallest diff first, then PR number
    plan.sort(key=lambda row: (row[6], row[5], row[0], row[2].number))
    return plan


def cmd_order(args: argparse.Namespace) -> int:
    github = shared("github", Github)
    print("#rank\trepo\taccount\tpr\tbranch\tbase\tfiles\tcluster\tworktree\tready\tblockers")
    for index, (_files, slug, pull, ready, blocker, cluster, _depth, worktree) in enumerate(order_plan(args), start=1):
        print(
            f"{index}\t{slug}\t{github.account(slug)}\t{pull.number}\t{pull.head}\t{pull.base}\t"
            f"{len(pull.paths)}\t{cluster}\t{worktree}\t{'yes' if ready else 'no'}\t{blocker or '-'}"
        )
    return 0
STOP_WORDS = {
    "feat", "fix", "chore", "docs", "refactor", "test", "tests", "the", "a", "an", "and",
    "to", "of", "for", "in", "on", "with", "per", "by", "is", "it", "this", "that",
}


def plan_hardened(path: Path) -> bool:
    """True when PLAN.md's last line names the commit holding exactly this plan text.

    The marker is `<!-- hardened: <sha> -->`, the sha of the plan commit. Appending the marker
    commits once more, so the sha cannot name the commit that carries the marker: it names the
    commit whose PLAN.md equals the current file without that last line. Any later edit of the
    plan makes the marker stale, which is what sends the worktree back to HRD.
    """
    plan = path / PLAN_FILE
    if not plan.is_file() or not run(["git", "-C", str(path), "ls-files", "--error-unmatch", PLAN_FILE]):
        return False
    lines = plan.read_text(errors="replace").splitlines()
    match = HARDENED_RE.fullmatch(lines[-1]) if lines else None
    if not match:
        return False
    shown = run(["git", "-C", str(path), "show", f"{match.group(1)}:{PLAN_FILE}"]).splitlines()
    return shown == lines[:-1]


def plan_state(wt: Worktree) -> tuple[bool, bool, str]:
    proposed = (wt.path / PLAN_FILE).is_file()
    hardened = plan_hardened(wt.path)
    text = ""
    if wt.pane not in {"-", ""}:
        text = run(["herdr", "pane", "read", wt.pane, "--source", "recent", "--lines", "300"])
    return proposed, hardened, text


def short_title(wt: Worktree) -> str:
    """Four kebab words at most: the PR title, else the newest commit subject."""
    source = ""
    if wt.pull and wt.pull.number and wt.slug:
        _login, token, _readable = credential(wt.slug)
        source = run(
            ["gh", "pr", "view", str(wt.pull.number), "-R", wt.slug, "--json", "title", "--jq", ".title"],
            env={"GH_TOKEN": token} if token else None,
        )
    if not source:
        source = run(["git", "-C", str(wt.path), "log", "-1", "--format=%s"])
    words = [word for word in re.split(r"[^a-z0-9]+", source.lower()) if word]
    kept = [word for word in words if word not in STOP_WORDS][:4]
    if not kept:
        kept = [word for word in wt.branch.replace("worktree/", "").split("-") if word][:2]
    return "-".join(kept) or "untitled"


def check_green(wt: Worktree) -> bool:
    """Green means every check run on the PR head succeeded: the fact collect already read."""
    return wt.checks == "green"


def review_marker(wt: Worktree) -> str:
    """Whichever exact marker line comes last in the PR body: REVIEWING or REVIEW_CLEAR."""
    if not wt.pull:
        return ""
    found = ""
    for line in wt.pull.body.splitlines():
        if line.strip() in {"REVIEWING", "REVIEW_CLEAR"}:
            found = line.strip()
    return found


def step_for(wt: Worktree, proposed: bool, hardened: bool, pane_text: str = "") -> str:
    """Select step from plan commit marker, git and PR facts only."""
    if wt.pull and wt.pull.state == "MERGED":
        return "DONE" if wt.dirty == 0 else "BUILD"
    if wt.pull and wt.pull.state == "OPEN":
        if wt.pull.merge_state == "DIRTY":
            return "REB"
        if not check_green(wt) or review_marker(wt) == "REVIEWING":
            return "REV"
        return "MRG"
    committed_plan = bool(run(["git", "-C", str(wt.path), "ls-files", "--error-unmatch", PLAN_FILE]))
    if proposed and not committed_plan:
        return "PLAN"
    if committed_plan and not hardened:
        return "HRD"
    if committed_plan and hardened:
        return "BUILD"
    if wt.ahead > 0 or wt.dirty:
        return "BUILD"
    # A registry entry carrying a task is a job in flight even with no git: IDLE means nothing
    # started and nothing in flight, so it excludes every entry that has one.
    return "PLAN" if wt.task else "IDLE"


# symbol, colour and what the label says the worktree is doing
STEP_STYLE: dict[str, tuple[str, str]] = {
    "IDLE": ("💤", "#56b6c2"),
    "PLAN": ("🗺", "#61afef"),
    "HRD": ("🛡", "#c678dd"),
    "BUILD": ("⚒", "#e5c07b"),
    "REV": ("🔍", "#d19a66"),
    "REB": ("⟳", "#c678dd"),
    "MRG": ("⤵", "#98c379"),
    "DONE": ("✔", "#7f8c8d"),
}

def paint(step: str, name: str, title: str) -> str:
    """`<symbol> <STEP> <name> <title>`: the label is the only place the id is rendered."""
    symbol, _colour = STEP_STYLE.get(step, ("•", "#888888"))
    return f"{symbol} {step} {name} {title}"[:64]


BUG_WORDS = ("fix", "bug", "crash", "broken", "regression", "panic", "error", "flake", "hotfix")
FEATURE_WORDS = ("feat", "add", "implement", "design", "redesign", "support", "introduce")


def recent_text(wt: Worktree, args: argparse.Namespace) -> str:
    """Deterministic evidence: commit subjects since the base, plus an optional transcript tail."""
    parts = [run(["git", "-C", str(wt.path), "log", "--format=%s", f"origin/{args.base}..HEAD"])]
    parts.append(str(wt.pull.head if wt.pull else ""))
    if args.transcript:
        try:
            tail = Path(args.transcript).read_text(errors="ignore")[-20000:]
        except OSError:
            tail = ""
        parts.append(tail)
    return " ".join(parts).lower()


def pick_mode(wt: Worktree, text: str, proposed: bool) -> tuple[str, str]:
    """Mode and step from evidence alone: same facts in, same answer out."""
    words = sum(1 for _ in text.split())
    small = wt.ahead <= 1 and wt.dirty <= 2 and (wt.pull.files if wt.pull else 0) <= 3
    bug = any(word in text for word in BUG_WORDS)
    feature = any(word in text for word in FEATURE_WORDS) or proposed
    if wt.dirty == 0 and wt.ahead == 0 and not wt.pull and not proposed:
        return "ask", "IDLE"
    if bug and small and not proposed:
        return "hotfix", "BUILD"
    if feature and (proposed or wt.ahead > 1 or words > 40):
        return "feat", "BUILD"
    return "fast", "BUILD"


def cmd_mode(args: argparse.Namespace) -> int:
    """Say which mode a piece of work belongs to and which step it is at."""
    print("#path\tmode\tstep\tevidence")
    overall = "ask"
    for wt in collect(args.repo, args.base):
        proposed, hardened, pane_text = plan_state(wt)
        text = recent_text(wt, args) + " " + pane_text
        mode, chosen = pick_mode(wt, text, proposed)
        step = step_for(wt, proposed, hardened, pane_text)
        if mode != "ask" and step in {"IDLE", "DONE"}:
            step = chosen
        if mode == "feat" and overall in {"ask", "fast", "hotfix"}:
            overall = "feat"
        elif mode == "hotfix" and overall == "ask":
            overall = "hotfix"
        elif mode == "fast" and overall == "ask":
            overall = "fast"
        print(f"{wt.path}\t{mode}\t{step}\t{wt.branch} dirty {wt.dirty} ahead {wt.ahead}")
    print(f"overall\t{overall}")
    return 0


def herdr_apply(cmd: list[str]) -> bool:
    """A herdr command that has to work, or say so: a rename nobody applied is a lie."""
    if ok(cmd):
        return True
    print(f"herdr failed: {' '.join(cmd)}", file=sys.stderr)
    return False


def label_self(own_pane: str) -> str:
    """Name the overlord's own pane and the workspace holding it: one name, no step, no title."""
    label = "👁 OVERLORD"
    workspace = own_workspace()
    herdr_apply(["herdr", "pane", "rename", own_pane, label])
    herdr_apply(["herdr", "pane", "report-metadata", own_pane, "--source", "overlord", "--token", "step=OVERLORD"])
    if workspace:
        herdr_apply(["herdr", "workspace", "rename", workspace, label])
        herdr_apply(
            ["herdr", "workspace", "report-metadata", workspace, "--source", "overlord",
             "--token", "step=OVERLORD"]
        )
    return workspace


def live_places() -> dict[str, tuple[str, str]]:
    """checkout path -> (workspace, pane) for every live pane, whatever the agent list says.

    A workspace closed and reopened keeps no agent record until one starts there, and its label
    resets to the directory name; this is what lets `rename` put the label back.
    """
    places: dict[str, tuple[str, str]] = {}
    for pane in herdr_json(["herdr", "pane", "list"]).get("panes", []):
        for key in ("foreground_cwd", "cwd"):
            cwd = pane.get(key) or ""
            if cwd:
                places.setdefault(str(Path(cwd).resolve()), (pane.get("workspace_id", ""), pane.get("pane_id", "")))
    return places


def cmd_rename(args: argparse.Namespace) -> int:
    """Rename every registered worktree from its frozen identity and current step."""
    by_path, _by_ws = herdr_facts()
    places = live_places() if os.environ.get("HERDR_ENV") == "1" else {}
    print("#path\tworkspace\tpane\tname\tstep\tsymbol\tlabel")
    own_pane = os.environ.get("HERDR_PANE_ID", "")
    if own_pane:
        workspace = label_self(own_pane) if args.apply or args.label_self else own_workspace()
        print(f"self\t{workspace or '-'}\t{own_pane}\t-\t-\t👁\t👁 OVERLORD")
    for wt in collect(args.repo, args.base):
        proposed, hardened, _text = plan_state(wt)
        step = step_for(wt, proposed, hardened)
        symbol = STEP_STYLE.get(step, ("•", "#888888"))[0]
        label = paint(step, wt.name, wt.title or short_title(wt))
        live_workspace, live_pane = places.get(str(wt.path.resolve()), ("", ""))
        workspace = by_path.get(str(wt.path.resolve()), "") or live_workspace
        pane = wt.pane if wt.pane not in {"-", ""} else live_pane
        print(f"{wt.path}\t{workspace or '-'}\t{pane or '-'}\t{wt.name}\t{step}\t{symbol}\t{label}")
        if not args.apply:
            continue
        if workspace:
            herdr_apply(["herdr", "workspace", "rename", workspace, label])
            herdr_apply(["herdr", "workspace", "report-metadata", workspace, "--source", "overlord", "--token", f"step={step}"])
        if pane:
            herdr_apply(["herdr", "pane", "rename", pane, label])
            herdr_apply(["herdr", "pane", "report-metadata", pane, "--source", "overlord", "--token", f"step={step}"])
    return 0


REVIEW_DIR = STATE_DIR / "review"
REVIEWED_RE = re.compile(r"^<!-- reviewed: ([0-9a-f]{7,64}) -->$")
SEVERITIES = ("critical", "high", "medium", "low")


def review_path(slug: str, number: int) -> Path:
    """Artifact path, identical in every implementation: <state>/review/<owner>-<repo>-<pr>.txt."""
    return REVIEW_DIR / f"{slug.replace('/', '-')}-{number}.txt"


def reviewed_sha(path: Path) -> str:
    """The head sha an artifact covers: its first line, empty when absent or unreadable."""
    try:
        first = path.read_text(errors="replace").splitlines()[:1]
    except OSError:
        return ""
    match = REVIEWED_RE.fullmatch(first[0]) if first else None
    return match.group(1) if match else ""


def review_state(slug: str, pull: PullRequest) -> str:
    """`current`, `stale` or `missing`: a review of an older commit is evidence about it only."""
    path = review_path(slug, pull.number)
    covered = reviewed_sha(path)
    if not covered:
        return "missing"
    return "current" if covered == pull.sha[:len(covered)] else "stale"


def severities(text: str) -> dict[str, int]:
    """Findings per severity, from the review's own `"severity": "<level>"` fields."""
    counts = {level: 0 for level in SEVERITIES}
    for level in re.findall(r'"severity"\s*:\s*"([a-z]+)"', text.lower()):
        if level in counts:
            counts[level] += 1
    return counts


def findings(text: str) -> list[tuple[str, str]]:
    """(severity, message) per finding, so each defect routes as one instruction."""
    return [
        (level.lower(), message.strip()[:300])
        for level, message in re.findall(
            r'"severity"\s*:\s*"([a-zA-Z]+)"[^}]*?"(?:message|title|body)"\s*:\s*"([^"]*)"', text
        )
        if level.lower() in SEVERITIES
    ]


def ocr_present() -> bool:
    return bool(run(["which", "ocr"]))


def cmd_review(args: argparse.Namespace) -> int:
    """Review each PR's diff with the ocr CLI; the artifact gates every merge."""
    if not ocr_present():
        print("ocr\tmissing\tinstall the ocr CLI; no PR is landable without a review", file=sys.stderr)
        return 1
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    print("#repository\tpr\thead\tartifact\texit\tcritical\thigh\tmedium\tlow\treviewed\tstep")
    routed: list[str] = []
    for wt in collect(args.repo, args.base):
        proposed, hardened, _text = plan_state(wt)
        step = step_for(wt, proposed, hardened)
        if step not in {"REV", "MRG"}:
            continue
        pull = wt.pull
        if not pull or not wt.vcs:
            capture = out_dir_capture(wt, args.base)
            print(f"{wt.slug or '-'}\t{pull.number if pull else '-'}\t-\t{capture}\t0\t-\t-\t-\t-\t-\tscreen")
            continue
        run(["git", "-C", str(wt.path), "fetch", "--quiet", "origin", args.base, pull.head])
        artifact = review_path(wt.slug, pull.number)
        body = run(["git", "-C", str(wt.path), "log", "-1", "--format=%s", pull.sha]) or pull.head
        command = [
            "ocr", "review", "--audience", "agent", "--format", "json",
            "--background", f"PR #{pull.number} on {wt.slug}: {body}"[:400],
            "--from", f"origin/{args.base}", "--to", pull.sha,
            "--repo", str(wt.path), "--output", str(artifact),
        ]
        code = 0 if ok(command, timeout=1800) else 1
        text = artifact.read_text(errors="replace") if artifact.exists() else ""
        counts = severities(text)
        if artifact.exists():
            artifact.write_text(f"<!-- reviewed: {pull.sha} -->\n{text}")
        for level, message in findings(text):
            if level != "low" and message:
                routed.append((wt, pull, level, message))
        print(
            f"{wt.slug}\t{pull.number}\t{pull.sha[:12]}\t{artifact}\t{code}\t"
            + "\t".join(str(counts[level]) for level in SEVERITIES)
            + f"\t{reviewed_sha(artifact)[:12] or '-'}\t{step}"
        )
    if routed:
        print("## findings")
        for wt, pull, level, message in routed:
            print(f'herdr agent prompt {wt.pane} "{level.upper()}: {message} (PR #{pull.number}, {wt.slug})"')
    return 0


def out_dir_capture(wt: Worktree, base: str) -> Path:
    """Screen fallback for a target that cannot produce a diff: never mistaken for a review."""
    out_dir = Path(os.environ.get("TMPDIR", "/tmp")) / "overlord-review"
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"{wt.path.name}-screen.txt"
    capture = ""
    if wt.pane not in {"-", ""}:
        capture = run(["herdr", "pane", "read", wt.pane, "--source", "visible", "--lines", "200", "--format", "ansi"])
    target.write_text(capture or run(["git", "-C", str(wt.path), "diff", "--stat", f"origin/{base}...HEAD"]) or "empty\n")
    return target


def cmd_plans(args: argparse.Namespace) -> int:
    print("#path\tpane\tagent\tproposed\thardened\taction")
    for wt in collect(args.repo, args.base):
        proposed = (wt.path / PLAN_FILE).is_file()
        hardened = plan_hardened(wt.path)
        action = "none"
        if proposed and not hardened:
            action = "harden"
        elif proposed and hardened:
            action = "approve"
        print(f"{wt.path}\t{wt.pane}\t{wt.agent}\t{'yes' if proposed else 'no'}\t{'yes' if hardened else 'no'}\t{action}")

        if wt.pane in {"-", ""}:
            continue
        if args.inject and action == "harden":
            run(["herdr", "pane", "run", wt.pane, HARDEN])
            print(f"sent {HARDEN} to {wt.pane}", file=sys.stderr)
        if args.approve:
            if action != "approve":
                print(f"refused to approve {wt.path}: PLAN.md is not hardened (no current marker)", file=sys.stderr)
                continue
            # the first option runs the plan and drops the current context
            run(["herdr", "pane", "send-keys", wt.pane, "1"])
            print(f"approved the plan in {wt.pane} (option 1)", file=sys.stderr)
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    print("#path\tbranch\tpr\taction")
    registered = {str(Path(path).resolve()) for path in registry()}
    for wt in collect(args.repo, args.base):
        # the registry is the only source of ownership: a worktree this overlord never
        # adopted or spawned is not its to delete
        if str(wt.path.resolve()) not in registered:
            continue
        if not wt.vcs or not wt.linked:
            continue
        if not wt.pull or wt.pull.state != "MERGED" or wt.dirty or wt.agent in {"working", "blocked"}:
            continue
        print(f"{wt.path}\t{wt.branch}\t{wt.pull.number}\tremove")
        if not args.apply:
            continue
        if not ok(["git", "-C", str(wt.repo), "worktree", "remove", "--force", str(wt.path)]):
            print(f"could not remove {wt.path}", file=sys.stderr)
            continue
        entries = registry()
        entries.pop(str(wt.path.resolve()), None)
        entries.pop(str(wt.path), None)
        save_registry(entries)
        run(["git", "-C", str(wt.repo), "branch", "-D", wt.branch])
        if wt.pane not in {"-", ""}:
            _by_path, by_ws = herdr_facts()
            for workspace, (_state, pane) in by_ws.items():
                if pane == wt.pane:
                    run(["herdr", "workspace", "close", workspace])
                    break
    return 0


STALLED_STEPS = {"HRD", "BUILD", "REV", "REB", "MRG"}
ALERT_FILE = STATE_DIR / "alerted.json"
IDLE_RE = re.compile(r"^\s*(?:>\s*)?(.+?)\?\s*$")


def seconds_since(moment: str) -> int:
    """Seconds from an ISO-8601 stamp to now: -1 when the stamp is missing or unreadable."""
    if not moment:
        return -1
    try:
        then = datetime.fromisoformat(moment.replace("Z", "+00:00"))
    except ValueError:
        return -1
    return max(0, int((datetime.now(timezone.utc) - then).total_seconds()))


def last_line(pane: str) -> str:
    """The last non-empty line a minion printed, clipped: the tail of the conversation."""
    if pane in {"-", ""}:
        return ""
    rows = [row.strip() for row in run(["herdr", "pane", "read", pane, "--source", "recent-unwrapped", "--lines", "40"]).splitlines()]
    return next((row for row in reversed(rows) if row), "")[:160]


def stall_rows(args: argparse.Namespace) -> list[dict[str, str]]:
    """One row per minion that is idle while its step still implies work."""
    rows: list[dict[str, str]] = []
    for wt in collect(args.repo, args.base):
        if wt.agent_status != "idle":
            continue
        proposed, hardened, _text = plan_state(wt)
        step = step_for(wt, proposed, hardened)
        if step not in STALLED_STEPS:
            continue
        tail = last_line(wt.pane)
        pull = wt.pull
        rows.append({
            "name": wt.name,
            "step": step,
            "title": wt.title or short_title(wt),
            "idle_seconds": min(ages) if (ages := [age for age in (
                seconds_since(pull.updated_at if pull else ""),
                seconds_since(wt.last_commit_at),
            ) if age >= 0]) else -1,
            "last_commit": wt.last_subject or "-",
            "commit_age": seconds_since(wt.last_commit_at),
            "dirty": wt.dirty,
            "pr": f"#{pull.number} {pull.state} {pull.mergeable}" if pull else "none",
            "checks": wt.checks,
            "question": "yes" if IDLE_RE.match(tail) else "no",
            "tail": tail or "-",
            "pane": wt.pane,
        })
    return rows


def show_stalls(args: argparse.Namespace) -> list[dict]:
    rows = stall_rows(args)
    print("#name\tstep\ttitle\tidle_seconds\tlast_commit\tcommit_age\tdirty\tpr\tchecks\tquestion\ttail")
    for row in rows:
        print("\t".join(str(row[key]) for key in (
            "name", "step", "title", "idle_seconds", "last_commit", "commit_age",
            "dirty", "pr", "checks", "question", "tail",
        )))
    return rows


def alert_text(row: dict) -> str:
    """The evidence the overlord decides on: everything it needs in one prompt."""
    return (
        f"Stall: minion {row['name']} is idle at {row['step']} ({row['title']}). "
        f"{row['idle_seconds']}s idle, last commit {row['last_commit']!r} {row['commit_age']}s ago, "
        f"{row['dirty']} dirty paths, PR {row['pr']}, checks {row['checks']}, "
        f"last pane line a question: {row['question']} — {row['tail']}. "
        f"Decide: resume it, answer it, merge it, prune it, respawn it, or leave a legitimate wait."
    )


def alert_new(rows: list[dict]) -> None:
    """Prompt this pane once per stall, keyed by minion+step and cleared once that stall is gone."""
    alerted = json.loads(ALERT_FILE.read_text()) if ALERT_FILE.exists() else {}
    live = {f"{row['name']}:{row['step']}" for row in rows}
    for row in rows:
        key = f"{row['name']}:{row['step']}"
        if key in alerted:
            continue
        if ok(["herdr", "agent", "prompt", os.environ.get("HERDR_PANE_ID", ""), alert_text(row)]):
            alerted[key] = [row["name"], row["step"]]
    alerted = {key: value for key, value in alerted.items() if key in live}
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_FILE.write_text(json.dumps(alerted, indent=2, sort_keys=True))


def cmd_watch(args: argparse.Namespace) -> int:
    """Print stalls, alert this pane once per new one, and repeat until --once or --stop."""
    while True:
        rows = show_stalls(args)
        if args.alert:
            alert_new(rows)
        if args.once or not args.interval:
            return 0
        time.sleep(args.interval)

DEPENDENCIES = (
    ("git", "git", "brew install git"),
    ("gh", "gh", "brew install gh"),
    ("uv", "uv", "brew install uv"),
    ("ocr", "ocr", "install the open-code-review CLI: its artifact gates every merge"),
)


def preflight_rows() -> tuple[list[dict[str, str]], list[str]]:
    """Every check this skill needs, as rows a stored verdict can reprint unchanged."""
    rows: list[dict[str, str]] = []
    missing: list[str] = []
    for name, command, fix in DEPENDENCIES:
        present = bool(run(["which", command]))
        rows.append({"check": name, "state": "ok" if present else "missing", "fix": fix})
        if not present:
            missing.append(name)

    version = run(["python3", "-c", "import sys; print('%d.%d' % sys.version_info[:2])"]) or "0.0"
    major, _, minor = version.partition(".")
    new_enough = int(major or 0) > 3 or (int(major or 0) == 3 and int(minor or 0) >= 11)
    rows.append(
        {"check": "python3", "state": version, "fix": "ok" if new_enough else "needs 3.11+: brew install python@3.13"}
    )
    if not new_enough:
        missing.append(f"python{version}")

    if run(["which", "gh"]):
        authed = ok(["gh", "auth", "status"])
        rows.append({"check": "gh auth", "state": "ok" if authed else "not logged in", "fix": "gh auth login"})
        if not authed:
            missing.append("gh-auth")
    else:
        rows.append({"check": "gh auth", "state": "unknown", "fix": "install gh first"})

    herdr = bool(run(["which", "herdr"])) and os.environ.get("HERDR_ENV") == "1"
    rows.append({"check": "herdr", "state": "ok" if herdr else "optional, absent", "fix": "nothing: git and gh cover the work"})
    pinned = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
    logins = [login for login, _token, _active in gh_accounts()]
    token = ", ".join(logins) or ("env token" if pinned else "missing")
    rows.append({"check": "token", "state": token, "fix": "gh auth login, or export GITHUB_TOKEN"})
    if token == "missing":
        missing.append("github-token")
    return rows, missing


def cmd_preflight(args: argparse.Namespace) -> int:
    """Check every dependency once, then reprint the stored verdict until --refresh."""
    config = read_yaml(CONFIG_FILE, "config")
    cached = config.get("preflight") or {}
    if cached and not (args.refresh or args.apply):
        print(f"#cached\t{cached.get('checked_at', '?')}\tpreflight --refresh to re-check")
        for row in cached.get("rows") or []:
            print(f"{row.get('check', '?')}\t{row.get('state', '?')}\t{row.get('fix', '')}")
        return 0 if not cached.get("missing") else 1

    if args.apply:
        for name, command, _fix in DEPENDENCIES:
            if not run(["which", command]):
                run(["brew", "install", name])

    rows, missing = preflight_rows()
    print("#check\tstate\tfix")
    for row in rows:
        print(f"{row['check']}\t{row['state']}\t{row['fix']}")
    config["preflight"] = {"checked_at": stamp(), "ok": not missing, "rows": rows, "missing": missing}
    write_yaml(CONFIG_FILE, config)
    print(f"#stored\t{CONFIG_FILE}\tpreflight --refresh to re-check", file=sys.stderr)
    if missing:
        print(f"missing: {', '.join(missing)}", file=sys.stderr)
    return 0 if not missing else 1


def completion(branch: str, pane: str) -> str:
    """The clause that makes a worker report itself, so the overlord waits on nothing."""
    line = f"DONE {branch}: <outcome, commit sha, PR url, what you ran, anything unverified>"
    return (
        "When you are done, report it in the overlord's pane as your last action:\n"
        f'`herdr agent prompt {pane} "{line}"`\n'
        "Send it once, then stop: the overlord reads that line when its turn resumes and never waits "
        "on you, so start no background job and poll nothing.\n"
        f'Optional, so a human sees it too: `herdr notification show "DONE {branch}" '
        '--body "<one line>" --sound done`.'
    )


def credential_note(repo: Path) -> str:
    """The line that keeps a worker's gh calls on the account that reaches its repository."""
    slug = repo_slug(repo)
    if not slug:
        return ""
    login, _token, _readable = credential(slug)
    active = next((name for name, _token, is_active in gh_accounts() if is_active), "")
    if not login or login == "-" or login == active:
        return ""
    return (
        f"GitHub: {slug} answers to the `{login}` gh account, not the active one. Prefix every gh "
        f'call with `GH_TOKEN="$(gh auth token --user {login})"`, or gh acts as `{active}` and 404s.'
    )


def handover(mode: str, task: str, clause: str, note: str = "") -> str | None:
    """The text a minion starts from: preamble, mode prompts, credential note, task, completion clause.

    A prompt file that is missing or empty is reported and returns None: the minion would
    otherwise start without the rules it is meant to obey.
    """
    names = ["preamble"] + (["hotfix"] if mode == "hotfix" else ["feat"] if mode == "feat" else []) + ["work"]
    parts: list[str] = []
    for name in names:
        path = PROMPTS / f"{name}.md"
        try:
            text = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            print(f"prompt file unreadable: {path} ({exc.strerror})", file=sys.stderr)
            return None
        if not text:
            print(f"prompt file empty: {path}", file=sys.stderr)
            return None
        parts.append(text)
    return "\n\n".join(parts + ([note] if note else []) + [task] + ([clause] if clause else []))

def cmd_models(args: argparse.Namespace) -> int:
    allowed, default = model_policy()
    print("#model\tdefault")
    for name in allowed or [default]:
        print(f"{name}\t{'yes' if name == default else 'no'}")
    return 0


def cmd_spawn(args: argparse.Namespace) -> int:
    """Start a minion's job in a fresh worktree."""
    if args.mode not in {"fast", "hotfix", "feat"}:
        print("mode must be fast, hotfix or feat", file=sys.stderr)
        return 2
    if not args.task:
        print("spawn needs --task", file=sys.stderr)
        return 2
    model, refusal = resolve_model(getattr(args, "model", "") or os.environ.get("OVERLORD_MODEL", ""))
    if refusal:
        print(refusal, file=sys.stderr)
        return 2

    repo = args.repo[0] if args.repo else Path.cwd()
    title = getattr(args, "title", "") or ""
    if title and not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", title):
        print("--title must be lowercase letters, digits and single hyphens", file=sys.stderr)
        return 2
    if title:
        slug = title
    else:
        words = [word for word in re.split(r"\s+", args.task) if word and not word.endswith(":")]
        words = [word for word in words if word.lower().strip(".:,;!?()[]{}") not in {"job", "task", "brief"}]
        slug = "-".join(word for word in re.split(r"[^a-z0-9]+", " ".join(words).lower()) if word and word not in STOP_WORDS)[:60] or "job"
    branch = f"worktree/{slug}"
    path = Path(args.dest).expanduser() / slug if args.dest else Path.home() / ".herdr" / "worktrees" / repo.name / slug
    pane = os.environ.get("HERDR_PANE_ID", "")
    if not pane:
        print("#warning\tHERDR_PANE_ID unset: completion clause omitted", file=sys.stderr)
    text = handover(args.mode, args.task, completion(branch, pane) if pane else "", credential_note(repo))
    if text is None:
        return 1

    step = "PLAN" if args.mode == "feat" else "BUILD"
    name = f"m{registry().get('next_name', 1)}"
    birth = title_slug(slug)
    preview = paint(step, name, birth)
    print(f"#worktree\t{path}\nbranch\t{branch}\nmode\t{args.mode}\nmodel\t{model}\ntitle\t{birth}")
    if args.dry_run:
        print(f"would run\tgit -C {repo} worktree add -b {branch} {path} origin/{args.base}")
        print(f"would run\therdr workspace create --cwd {path} --no-focus")
        print(f"would run\therdr agent start {agent_name(path)} --kind omp --pane <pane> -- --model {model} --plan {model} --smol {model}")
        if args.mode == "feat":
            print(f"would run\therdr agent send-keys <pane> {PLAN_TOGGLE}")
            print("would run\tverify plan mode from the pane banner, fail the spawn otherwise")
        print("would run\therdr agent prompt <pane> <handover>")
        print(f"would run\therdr workspace rename <workspace> {preview}")
        print(f"would run\therdr pane rename <pane> {preview}")
        return 0
    if not ok(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(path), f"origin/{args.base}"]):
        print("worktree creation failed", file=sys.stderr)
        return 1
    entries = registry()
    register_entry(entries, str(path.resolve()), {"repo": str(repo), "branch": branch, "mode": args.mode, "task": args.task})
    save_registry(entries)
    label = paint(step, entries[str(path.resolve())]["name"], birth)
    workspace, minion = open_workspace(path, model)
    if not minion:
        print(f"worktree ready, no minion started in {workspace or 'herdr'}: start one there", file=sys.stderr)
        return 1
    print(f"worker\t{workspace}:{minion}")
    if args.mode == "feat" and not enter_plan_mode(minion):
        print(f"plan mode did not engage in {minion}: spawn failed before the handover", file=sys.stderr)
        return 1
    if not ok(["herdr", "agent", "prompt", minion, text], timeout=120):
        print("handover prompt failed", file=sys.stderr)
        return 1
    if workspace and not herdr_apply(["herdr", "workspace", "rename", workspace, label]):
        print(f"minion label failed for workspace {workspace}", file=sys.stderr)
    if not herdr_apply(["herdr", "pane", "rename", minion, label]):
        print(f"minion label failed for pane {minion}", file=sys.stderr)
    return 0




def merge(slug: str, number: int) -> str:
    """Squash-merge one pull request as the gh account that reaches its repository."""
    login = shared("github", Github).account(slug)
    token = next((token for name, token, _active in gh_accounts() if name == login), "")
    env = {**os.environ, **({"GH_TOKEN": token} if token else {})}
    try:
        proc = subprocess.run(
            ["gh", "pr", "merge", str(number), "-R", slug, "--squash", "--delete-branch"],
            capture_output=True, text=True, env=env, timeout=180,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return f"failed: {exc}"
    if proc.returncode == 0:
        return "merged"
    lines = (proc.stderr or proc.stdout).strip().splitlines()
    return f"failed: {lines[-1] if lines else 'no output'}"


def asks(args: argparse.Namespace) -> list[str]:
    """The one prompt each worktree still owes, as a ready command: fixed wording, no judgement.

    A worker with no pane is skipped here and reported by `inventory`: printing a prompt
    addressed to nobody would read as an instruction that was sent.
    """
    base = args.base
    out: list[str] = []
    for wt in collect(args.repo, base):
        pull = wt.pull
        if wt.pane in {"-", ""} or (pull and pull.state == "MERGED"):
            continue
        if pull and pull.merge_state == "DIRTY":
            text = (f"Pull request {pull.number} conflicts with {base}. Rebase onto origin/{base}, "
                    f"keep both sides' intent, then git push --force-with-lease.")
        elif pull and pull.state == "OPEN":
            text = (f"Pull request {pull.number} is not green yet, or still a draft. Make the checks "
                    f"pass, commit and push.")
        elif wt.dirty:
            text = "Commit or revert the uncommitted changes in this worktree, then push."
        elif wt.ahead > 0:
            text = (f"Push {wt.branch} and open the pull request against origin/{base}: "
                    f"gh pr create --base {base} --head {wt.branch} --fill.")
        else:
            continue
        out.append(f'herdr agent prompt {wt.pane} "{text}"')
    return out


def cmd_pass(args: argparse.Namespace) -> int:
    """The whole pass in one process: every table, then every step that needs no judgement.

    Merges, plan keys, renames and prunes are decided by the rules above, so they run here
    and the model reads the last section only: the prompts still owed, already worded.
    """
    code = cmd_bootstrap(args)
    print("## review")
    if getattr(args, "dry_run", False):
        print("would run\treview")
    else:
        cmd_review(args)
    print("## stalls")
    rows = show_stalls(args)
    if not getattr(args, "dry_run", False):
        alert_new(rows)
    if getattr(args, "dry_run", False):
        print("## plans\nwould run\tplans --inject --approve")
        print("## rename\nwould run\trename --apply")
        print("## merge")
        for _files, slug, pull, ready, blocker, _cluster, _depth, _worktree in order_plan(args):
            print(f"{slug}\t{pull.number}\t{'would merge' if ready else 'skipped: ' + blocker}")
        print("## prune\nwould run\tprune --apply")
        print("## ask")
        for line in asks(args):
            print(line)
        return code
    print("## plans --inject --approve")
    cmd_plans(argparse.Namespace(**{**vars(args), "inject": True, "approve": True}))
    print("## rename --apply")
    cmd_rename(argparse.Namespace(**{**vars(args), "apply": True, "label_self": True}))
    print("## merge")
    for _files, slug, pull, ready, blocker, _cluster, _depth, _worktree in order_plan(args):
        if not ready:
            print(f"{slug}\t{pull.number}\tskipped\t{blocker}")
            continue
        print(f"{slug}\t{pull.number}\t{merge(slug, pull.number)}")
    print("## prune --apply")
    cmd_prune(argparse.Namespace(**{**vars(args), "apply": True}))
    print("## ask")
    for line in asks(args):
        print(line)
    return code


def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Every read-only table a pass needs, in one process: one GitHub round trip, one git probe.

    The commands below each read the same facts; run separately they pay for them again.
    """
    print("## preflight")
    code = cmd_preflight(argparse.Namespace(**{**vars(args), "apply": False, "refresh": False}))
    for title, handler, extra in (
        ("inventory", cmd_inventory, {}),
        ("mode", cmd_mode, {"transcript": ""}),
        ("order", cmd_order, {}),
        ("plans", cmd_plans, {"inject": False, "approve": False}),
        # the overlord names its own pane and workspace; worktree labels stay a preview
        # until `rename --apply`
        ("rename", cmd_rename, {"apply": False, "label_self": True}),
    ):
        print(f"## {title}")
        handler(argparse.Namespace(**{**vars(args), **extra}))
    return code


BRIDGED = {"survey": "survey", "labels": "labels", "relabel": "apply", "verify": "verify"}
GLOBAL_FLAGS = ("--repo", "--base")


def bridged(argv: list[str]) -> tuple[str, list[str]] | None:
    """(module, its own argv) when a bridged command is asked for, global flags dropped.

    The helpers keep their own flags and know nothing of --repo or --base, so those are
    removed here. Reading only argv[0] missed every call that puts a global flag first.
    """
    rest: list[str] = []
    skip = False
    for token in argv:
        if skip:
            skip = False
            continue
        if token in GLOBAL_FLAGS:
            skip = True
            continue
        if token.startswith(tuple(flag + "=" for flag in GLOBAL_FLAGS)):
            continue
        rest.append(token)
    index = next((position for position, token in enumerate(rest) if not token.startswith("-")), None)
    if index is None or rest[index] not in BRIDGED:
        return None
    return BRIDGED[rest[index]], rest[:index] + rest[index + 1:]


def main(argv: list[str]) -> int:
    # the helpers keep their own flags, so they are dispatched before argparse ever sees
    # them: their flags would be rejected, and the stubs below only exist for --help
    hop = bridged(argv)
    if hop:
        module, module_args = hop
        sys.dont_write_bytecode = True
        return importlib.import_module(module).main(module_args)
    parser = argparse.ArgumentParser(description="Land worktree pull requests.")
    parser.add_argument("--repo", action="append", default=[], help="repository to inspect (repeatable)")
    parser.add_argument("--base", default="main", help="base branch for ahead counts")
    subs = parser.add_subparsers(dest="command", required=True)

    spawn = subs.add_parser("spawn", help="start a job in a fresh worktree")
    spawn.add_argument("--mode", default="feat", help="fast, hotfix or feat")
    spawn.add_argument("--task", default="", help="what the minion should do")
    spawn.add_argument("--title", default="", help="frozen title slug (lowercase letters, digits, hyphens)")
    spawn.add_argument("--dry-run", action="store_true", help="print instead of creating")
    spawn.add_argument("--dest", default="", help="parent directory for the worktree (default ~/.herdr/worktrees/<repo>)")
    # The same two flags as the top level, so `spawn … --repo PATH` reads as the table says;
    # SUPPRESS keeps a value given before the subcommand instead of resetting it.
    spawn.add_argument("--repo", action="append", default=argparse.SUPPRESS, help="repository to start the job in")
    spawn.add_argument("--base", default=argparse.SUPPRESS, help="base branch for the worktree")
    spawn.add_argument("--model", default="", help="allowed model for this minion")

    for name, help_text in (
        ("survey", "survey every worktree: branch, commits, panes"),
        ("labels", "check labels against the naming rules"),
        ("relabel", "rename workspaces and move their branches"),
        ("verify", "verify labels after a pass"),
    ):
        subs.add_parser(name, help=help_text, add_help=False)

    mode = subs.add_parser("mode", help="which mode a worktree belongs to, and its step")
    mode.add_argument("--transcript", default="", help="session transcript to read for intent keywords")

    adopt = subs.add_parser("adopt", help="take over existing worktrees or workspaces")
    adopt.add_argument("targets", nargs="+", help="workspace id (w1) or checkout path")
    adopt.add_argument("--task", default="", help="what the worktree is for")

    reg = subs.add_parser("registry", help="the worktrees this overlord owns")
    reg.add_argument("--path", action="store_true", help="one path per line")
    reg.add_argument("--add", nargs="*", default=[], help="register these worktree paths")
    reg.add_argument("--remove", nargs="*", default=[], help="forget these worktree paths")
    reg.add_argument("--task", default="", help="what the worktree is for")
    reg.add_argument("--source-repo", default="", help="repository path the worktree came from")
    reg.add_argument("--rename-list", action="store_true", help="workspace, label and path of every owned worktree")

    subs.add_parser("models", help="the models a minion may use, and the default")

    preflight = subs.add_parser("preflight", help="verify dependencies once, then reprint the verdict")
    preflight.add_argument("--apply", action="store_true", help="install what is absent, then re-check")
    preflight.add_argument("--refresh", action="store_true", help="re-check even when a verdict is stored")

    subs.add_parser("bootstrap", help="every read-only table a pass needs, in one process")
    run_pass = subs.add_parser("pass", help="the whole pass: tables, plans, renames, merges, prune, asks")
    run_pass.add_argument("--dry-run", action="store_true", help="print what it would do, change nothing")
    subs.add_parser("inventory", help="one row per worktree")
    subs.add_parser("order", help="merge plan for the open pull requests")

    status = subs.add_parser("status", help="gate: 0 when nothing is left to land")
    status.add_argument("--stop", action="store_true", help="write the stop file instead of checking")
    status.add_argument("--verbose", "-v", action="store_true", help="print landed rows too")
    status.add_argument("--idle-minutes", type=int, default=IDLE_MINUTES, help="stop when nothing moved for this long")

    plans = subs.add_parser("plans", help="proposed plans and their hardening state")
    plans.add_argument("--inject", action="store_true", help=f"type {HARDEN} into unhardened panes")
    plans.add_argument("--approve", action="store_true", help="pick option 1 once a plan is hardened")

    prune = subs.add_parser("prune", help="remove worktrees whose pull request merged")
    prune.add_argument("--apply", action="store_true", help="do it instead of listing")

    rename = subs.add_parser("rename", help="prefix every worktree and pane with its step")
    rename.add_argument("--apply", action="store_true", help="do it instead of listing")
    rename.set_defaults(label_self=False)

    review = subs.add_parser("review", help="review each PR diff with ocr; the artifact gates the merge")

    watch = subs.add_parser("watch", help="stalls: idle minions whose step still implies work")
    watch.add_argument("--alert", action="store_true", help="prompt this pane once per new stall")
    watch.add_argument("--once", action="store_true", help="one sweep, then exit")
    watch.add_argument("--interval", type=int, default=0, help="seconds between sweeps; 0 runs one")

    args = parser.parse_args(argv)
    args.repo = [Path(path).expanduser() for path in args.repo]
    if not args.repo and run(["git", "-C", str(Path.cwd()), "rev-parse", "--git-dir"]):
        args.repo = [Path.cwd()]
    handlers = {
        "preflight": cmd_preflight,
        "registry": cmd_registry,
        "models": cmd_models,
        "mode": cmd_mode,
        "spawn": cmd_spawn,
        "bootstrap": cmd_bootstrap,
        "pass": cmd_pass,
        "inventory": cmd_inventory,
        "order": cmd_order,
        "status": cmd_status,
        "plans": cmd_plans,
        "prune": cmd_prune,
        "rename": cmd_rename,
        "review": cmd_review,
        "watch": cmd_watch,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
