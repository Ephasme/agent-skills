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
STATE_DIR = Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local" / "state")) / "call-overlord"
REGISTRY = STATE_DIR / "worktrees.json"
OVERLORD_DIR = Path(os.environ.get("OVERLORD_HOME", Path.home() / ".overlord"))
CONFIG_FILE = OVERLORD_DIR / "config.yaml"
CACHE_DIR = OVERLORD_DIR / "caches"
DISCOVERY_CACHE = CACHE_DIR / "discovery.yaml"
DISCOVERY_TTL_HOURS = 24
PROMPTS = Path(__file__).resolve().parent.parent / "prompts"


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
    return data


def save_registry(entries: dict[str, dict[str, str]]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = REGISTRY.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(entries, indent=2, sort_keys=True))
    temporary.replace(REGISTRY)


def read_yaml(path: Path, what: str) -> dict:
    """A YAML state file: empty when absent, an error when unreadable.

    A corrupt config or cache never reads as empty: discovery would silently rescan, and
    preflight would forget that it already ran.
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


def config_roots() -> list[Path]:
    """The directories discovery may scan, named in config.yaml: none unless the file says so."""
    section = read_yaml(CONFIG_FILE, "config").get("discovery") or {}
    roots = section.get("roots") or []
    return [Path(os.path.expanduser(str(root))) for root in roots if str(root).strip()]


def scan_roots(roots: list[Path]) -> dict[str, dict]:
    """Every git checkout directly under a root, or the root itself: path -> slug, base, gh.

    A repository whose slug the token cannot read keeps gh false instead of disappearing:
    an invisible remote is a fact the report has to name.
    """
    github = shared("github", Github)
    found: dict[str, dict] = {}
    for root in roots:
        candidates = [root, *sorted(root.iterdir())] if root.is_dir() else [root]
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            toplevel = run(["git", "-C", str(candidate), "rev-parse", "--show-toplevel"])
            if not toplevel:
                continue
            path = Path(toplevel).resolve()
            if str(path) in found:
                continue
            slug = repo_slug(path)
            head = run(["git", "-C", str(path), "symbolic-ref", "--short", "refs/remotes/origin/HEAD"])
            readable = bool(slug) and github.readable(slug)
            found[str(path)] = {"slug": slug, "base": (head or "origin/main").removeprefix("origin/"), "gh": readable}
    return found


def refresh_discovery(roots: list[Path]) -> dict[str, dict]:
    """Rescan the roots and replace the cache: the only writer of discovery.yaml."""
    repos = scan_roots(roots)
    write_yaml(
        DISCOVERY_CACHE,
        {"generated_at": stamp(), "ttl_hours": DISCOVERY_TTL_HOURS, "roots": [str(root) for root in roots], "repos": repos},
    )
    return repos


def cache_age(cache: dict) -> float | None:
    """Seconds since the cache was generated, None when it carries no readable stamp."""
    try:
        then = datetime.strptime(str(cache.get("generated_at") or ""), "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return None
    return (datetime.now(timezone.utc) - then.replace(tzinfo=timezone.utc)).total_seconds()


def discovery(refresh: bool = False) -> dict[str, dict]:
    """Repositories discovery knows: the cache while it is fresh, a rescan once it expired.

    No roots in config.yaml means no discovery at all, so a pass covers --repo and the
    registry alone until the file names a directory to look in.
    """
    roots = config_roots()
    if not roots:
        return {}
    cache = read_yaml(DISCOVERY_CACHE, "discovery cache")
    age = cache_age(cache)
    ttl = float(cache.get("ttl_hours") or DISCOVERY_TTL_HOURS) * 3600
    if refresh or age is None or age > ttl or cache.get("repos") is None:
        return refresh_discovery(roots)
    return cache.get("repos") or {}


def discovered() -> list[Path]:
    return shared("discovered", lambda: [Path(path) for path in discovery() if Path(path).is_dir()])


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
        places.setdefault(pane.get("workspace_id", ""), []).append(pane.get("cwd") or "")
    return places


def agent_name(path: Path) -> str:
    """A live agent name herdr accepts: [a-z][a-z0-9_-]{0,31}, from the checkout name."""
    slug = re.sub(r"[^a-z0-9-]+", "-", path.name.lower()).strip("-") or "adopted"
    return (slug if slug[:1].isalpha() else f"a-{slug}")[:32].rstrip("-") or "adopted"


def resume_agent(record: dict, pane: str, path: Path) -> str:
    """Start the moved agent again and point it at the session file it lost."""
    name = agent_name(path)
    if not ok(["herdr", "agent", "start", name, "--kind", record.get("agent") or "omp", "--pane", pane]):
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
    reopened = (created.get("workspace") or {}).get("workspace_id", "")
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
        entries[resolved] = {"repo": str(repo), "branch": branch, "mode": "adopted", "task": args.task, "kind": kind}
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
            print(path)
        return 0
    if args.add:
        entries = registry()
        for path in args.add:
            entries[str(Path(path).expanduser().resolve())] = {"repo": args.source_repo or "", "task": args.task or ""}
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
            workspace = by_path.get(str(Path(path).resolve()), "-")
            print(f"{workspace}\t{labels.get(str(Path(path).resolve()), meta.get('task', ''))[:40]}\t{path}")
        return 0
    print(json.dumps(entries, indent=2, sort_keys=True))
    return 0
LEGACY_STOP = Path(os.environ.get("TMPDIR", "/tmp")) / "merge-agents-stop"
PLAN_FILE = "PLAN.md"
HARDEN = "/skill:harden-plan"
API = "https://api.github.com"


def run(cmd: list[str], cwd: Path | None = None, timeout: int = 120) -> str:
    try:
        done = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def ok(cmd: list[str], timeout: int = 60) -> bool:
    """True when the command ran and exited 0. gh writes status to stderr, so stdout is useless."""
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def github_token() -> str:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        if token := os.environ.get(name):
            return token
    return run(["gh", "auth", "token"])


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
    )


class Github:
    def __init__(self) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        token = github_token()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self.client = httpx.Client(headers=headers, timeout=30)
        self.pulls: dict[str, dict[str, PullRequest]] = {}

    def branch_pulls(self, slug: str) -> dict[str, PullRequest]:
        """branch -> its most relevant PR: an open one wins over merged or closed."""
        if slug in self.pulls:
            return self.pulls[slug]
        found: dict[str, PullRequest] = {}
        response = self.client.get(f"{API}/repos/{slug}/pulls", params={"state": "all", "per_page": 100, "sort": "updated"})
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
        response = self.client.get(f"{API}/repos/{slug}/pulls", params={"state": "open", "per_page": 100})
        if response.status_code != 200:
            print(f"github: {slug}: {response.status_code} {response.text[:120]}", file=sys.stderr)
            return []
        return [pull_from_json(raw) for raw in response.json()]

    def readable(self, slug: str) -> bool:
        """Whether this token can see the repository at all: what makes its PRs invisible."""
        return self.client.get(f"{API}/repos/{slug}").status_code == 200

    def with_paths(self, slug: str, pull: PullRequest) -> PullRequest:
        """The pull request with its touched files: one request, not a second fetch of the row."""
        files = self.client.get(f"{API}/repos/{slug}/pulls/{pull.number}/files", params={"per_page": 100})
        if files.status_code == 200:
            pull.paths = [item.get("filename", "") for item in files.json() if item.get("filename")]
        return pull

    def checks_green(self, slug: str, number: int, sha: str = "") -> tuple[bool, str]:
        sha = sha or self.head_sha(slug, number)
        if not sha:
            return False, "unknown: head sha unavailable"
        response = self.client.get(f"{API}/repos/{slug}/commits/{sha}/check-runs")
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
        response = self.client.get(f"{API}/repos/{slug}/pulls/{number}")
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


def registry_repos() -> list[Path]:
    """Repositories of adopted worktrees, so a target outside --repo is still overseen."""
    return sorted({Path(meta["repo"]) for meta in registry().values() if meta.get("repo") and Path(meta["repo"]).is_dir()})


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
    """Repositories a pass may act on: named, adopted, or open in herdr.

    Discovery only enumerates checkouts, so a repository it finds is listed and left alone:
    nothing outside the realm is rebased, merged or pruned.
    """
    found = {Path(repo).expanduser().resolve() for repo in [*named, *registry_repos(), *herdr_open_repos()]}
    return sorted(repo for repo in found if repo.is_dir())


def scope_repos(repos: list[Path]) -> list[Path]:
    """Repositories a pass reports on: named, registry and discovered ones. Acting uses `realm_repos`."""
    found: dict[Path, None] = {}
    for repo in [*repos, *registry_repos(), *discovered()]:
        if repo.is_dir():
            found.setdefault(repo.resolve(), None)
    return sorted(found)


def collect(repos: list[Path], base: str) -> list[Worktree]:
    """One row per worktree, read once per pass: every table below shares these facts."""
    key = ("collect", tuple(sorted(str(Path(repo).expanduser().resolve()) for repo in repos)), base)
    return shared(key, lambda: _collect(repos, base))


def _collect(repos: list[Path], base: str) -> list[Worktree]:
    github = shared("github", Github)
    by_path, by_ws = herdr_facts()
    rows: list[Worktree] = []
    seen: set[Path] = set()
    registry_entries = registry()
    repos = scope_repos(repos)
    for repo in repos:
        if not run(["git", "-C", str(repo), "rev-parse", "--git-dir"]):
            print(f"not a git repository: {repo}", file=sys.stderr)
            continue
        registry_paths = {Path(path) for path in registry_entries}
        registered = {
            Path(path)
            for path, meta in registry_entries.items()
            if meta.get("repo") and Path(meta["repo"]).resolve() == repo.resolve()
        }
        for path in sorted(registry_paths):
            if path in seen or not path.is_dir():
                continue
            if run(["git", "-C", str(path), "rev-parse", "--git-dir"]):
                continue
            seen.add(path)
            workspace = by_path.get(str(path.resolve()), "")
            agent, pane = by_ws.get(workspace, ("-", "-")) if workspace else ("-", "-")
            rows.append(
                Worktree(
                    path=path, repo=path, branch="-", dirty=0, ahead=0, upstream="none",
                    slug="", pull=None, agent=agent, pane=pane, vcs=False,
                )
            )
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
            agent, pane = by_ws.get(workspace, ("-", "-")) if workspace else ("-", "-")
            rows.append(
                Worktree(
                    path=path,
                    repo=repo,
                    branch=branch,
                    dirty=dirty,
                    ahead=int(ahead_text) if ahead_text.isdigit() else 0,
                    upstream=run(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "@{u}"]) or "none",
                    slug=slug,
                    pull=github.branch_pulls(slug).get(branch) if slug else None,
                    agent=agent,
                    pane=pane,
                    linked=path.resolve() != repo.resolve(),
                )
            )
    return rows


def landable(wt: Worktree) -> str:
    """Empty when landed or empty; otherwise why it still holds work."""
    if not wt.vcs or not wt.linked:
        return ""
    if wt.dirty:
        return "dirty"
    if wt.pull and wt.pull.state == "OPEN":
        return "open-pr"
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


def cmd_order(args: argparse.Namespace) -> int:
    github = shared("github", Github)
    realm = realm_repos(args.repo)
    plan: list[tuple[int, str, PullRequest, bool, str, int, int, str]] = []
    for repo in realm:
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

    print("#rank\trepo\tpr\tbranch\tbase\tfiles\tcluster\tworktree\tready\tblockers")
    for index, (_files, slug, pull, ready, blocker, cluster, _depth, worktree) in enumerate(plan, start=1):
        print(
            f"{index}\t{slug}\t{pull.number}\t{pull.head}\t{pull.base}\t"
            f"{len(pull.paths)}\t{cluster}\t{worktree}\t{'yes' if ready else 'no'}\t{blocker or '-'}"
        )
    outside = sorted(
        {slug for slug in (repo_slug(repo) for repo in scope_repos(args.repo) if repo.resolve() not in set(realm)) if slug}
    )
    if outside:
        print(f"#note\tnot in realm, not planned: {', '.join(outside)}")
    return 0
STOP_WORDS = {
    "feat", "fix", "chore", "docs", "refactor", "test", "tests", "the", "a", "an", "and",
    "to", "of", "for", "in", "on", "with", "per", "by", "is", "it", "this", "that",
}


def plan_state(wt: Worktree) -> tuple[bool, bool, str]:
    """(proposed, hardened, pane text). A plan file counts, and so does the pane banner."""
    return shared(("plan_state", str(wt.path), wt.pane), lambda: _plan_state(wt))


def _plan_state(wt: Worktree) -> tuple[bool, bool, str]:
    proposed = (wt.path / PLAN_FILE).is_file()
    hardened = False
    text = ""
    if wt.pane not in {"-", ""}:
        text = run(["herdr", "pane", "read", wt.pane, "--source", "recent", "--lines", "300"]).lower()
        hardened = "harden-plan" in text
        proposed = proposed or "plan ready for review" in text or "exit plan mode" in text or "plan mode" in text
    return proposed, hardened, text


def short_title(wt: Worktree) -> str:
    """Four kebab words at most: the PR title, else the newest commit subject."""
    source = ""
    if wt.pull and wt.pull.number and wt.slug:
        source = run(["gh", "pr", "view", str(wt.pull.number), "-R", wt.slug, "--json", "title", "--jq", ".title"])
    if not source:
        source = run(["git", "-C", str(wt.path), "log", "-1", "--format=%s"])
    words = [word for word in re.split(r"[^a-z0-9]+", source.lower()) if word]
    kept = [word for word in words if word not in STOP_WORDS][:4]
    if not kept:
        kept = [word for word in wt.branch.replace("worktree/", "").split("-") if word][:2]
    return "-".join(kept) or "untitled"


def step_for(wt: Worktree, proposed: bool, hardened: bool, pane_text: str) -> str:
    """The one stage this worktree is at, from landed back to looking around."""
    if not wt.vcs:
        if proposed and not hardened:
            return "HRD"
        if proposed and hardened:
            return "REV"
        return "PLAN" if "plan mode" in pane_text else "WORK"
    if wt.pull and wt.pull.state == "MERGED":
        return "DONE"
    if wt.pull and wt.pull.draft:
        return "WORK"
    if wt.pull and wt.pull.state == "OPEN":
        return "REB" if wt.pull.merge_state == "DIRTY" else "MRG"
    if proposed and not hardened:
        return "HRD"
    if proposed and hardened:
        return "REV"
    if "plan mode" in pane_text:
        return "PLAN"
    if wt.dirty or wt.ahead > 0:
        return "WORK"
    return "IDLE"


# symbol, colour and what the label says the worktree is doing
STEP_STYLE: dict[str, tuple[str, str]] = {
    "IDLE": ("💤", "#56b6c2"),
    "PLAN": ("🗺", "#61afef"),
    "HRD": ("🛡", "#c678dd"),
    "WORK": ("⚒", "#e5c07b"),
    "REV": ("🔍", "#d19a66"),
    "REB": ("⟳", "#c678dd"),
    "MRG": ("⤵", "#98c379"),
    "DONE": ("✔", "#7f8c8d"),
}

def paint(step: str, title: str) -> str:
    """The visible label. Colour is herdr's config, never text: a hex code in a label is noise."""
    symbol, _colour = STEP_STYLE.get(step, ("•", "#888888"))
    return f"{symbol} {step} {title}"[:64]


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
        return "hotfix", "WORK"
    if feature and (proposed or wt.ahead > 1 or words > 40):
        return "feat", "WORK"
    return "fast", "WORK"


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


def cmd_rename(args: argparse.Namespace) -> int:
    """Prefix every worktree and pane with its step symbol, then say what it is about."""
    by_path, _by_ws = herdr_facts()
    print("#path\tworkspace\tpane\tstep\tsymbol\tlabel")
    own_pane = os.environ.get("HERDR_PANE_ID", "")
    if own_pane:
        workspace = label_self(own_pane) if args.apply else own_workspace()
        print(f"self\t{workspace or '-'}\t{own_pane}\t-\t👁\t👁 OVERLORD")
    for wt in collect(args.repo, args.base):
        proposed, hardened, text = plan_state(wt)
        step = step_for(wt, proposed, hardened, text)
        symbol = STEP_STYLE.get(step, ("•", "#888888"))[0]
        label = paint(step, short_title(wt))
        workspace = by_path.get(str(wt.path.resolve()), "")
        print(f"{wt.path}\t{workspace or '-'}\t{wt.pane}\t{step}\t{symbol}\t{label}")
        if not args.apply:
            continue
        if workspace:
            herdr_apply(["herdr", "workspace", "rename", workspace, label])
            herdr_apply(
                ["herdr", "workspace", "report-metadata", workspace, "--source", "overlord",
                 "--token", f"step={step}"]
            )
        if wt.pane not in {"-", ""}:
            herdr_apply(["herdr", "pane", "rename", wt.pane, label])
            herdr_apply(["herdr", "pane", "report-metadata", wt.pane, "--source", "overlord", "--token", f"step={step}"])
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    """Capture the screen of every worktree waiting on review, for a visual check."""
    out_dir = Path(args.capture or (Path(os.environ.get("TMPDIR", "/tmp")) / "overlord-review"))
    out_dir.mkdir(parents=True, exist_ok=True)
    print("#path\tpane\tstep\tcapture")
    for wt in collect(args.repo, args.base):
        proposed, hardened, text = plan_state(wt)
        step = step_for(wt, proposed, hardened, text)
        if step not in {"REV", "MRG"}:
            continue
        target = out_dir / f"{wt.path.name}-{step}.txt"
        capture = ""
        if wt.pane not in {"-", ""}:
            capture = run(["herdr", "pane", "read", wt.pane, "--source", "visible", "--lines", "200", "--format", "ansi"])
        if not capture:
            capture = run(["git", "-C", str(wt.path), "diff", "--stat", f"origin/{args.base}...HEAD"])
        target.write_text(capture or "empty capture\n")
        print(f"{wt.path}\t{wt.pane}\t{step}\t{target}")
    return 0


def cmd_plans(args: argparse.Namespace) -> int:
    print("#path\tpane\tagent\tproposed\thardened\taction")
    for wt in collect(args.repo, args.base):
        proposed = (wt.path / PLAN_FILE).is_file()
        hardened = False
        if wt.pane not in {"-", ""}:
            pane_output = run(["herdr", "pane", "read", wt.pane, "--source", "recent", "--lines", "300"]).lower()
            hardened = "harden-plan" in pane_output
            proposed = proposed or "plan ready for review" in pane_output or "exit plan mode" in pane_output

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
        if args.approve and action == "approve":
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

DEPENDENCIES = (
    ("git", "git", "brew install git"),
    ("gh", "gh", "brew install gh"),
    ("uv", "uv", "brew install uv"),
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
    token = "ok" if github_token() else "missing"
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


def cmd_discover(args: argparse.Namespace) -> int:
    """The repositories under the configured roots, and whether this token can read them."""
    roots = [Path(os.path.expanduser(root)) for root in args.root] or config_roots()
    if not roots:
        print("#path\tslug\tbase\tgh")
        print(f"#note\tno roots: add discovery.roots to {CONFIG_FILE}")
        return 0
    cache = read_yaml(DISCOVERY_CACHE, "discovery cache")
    age = cache_age(cache)
    ttl = float(cache.get("ttl_hours") or DISCOVERY_TTL_HOURS) * 3600
    stale = args.refresh or age is None or age > ttl or cache.get("repos") is None
    repos = refresh_discovery(roots) if stale else (cache.get("repos") or {})
    print("#path\tslug\tbase\tgh")
    for path, meta in sorted(repos.items()):
        print(f"{path}\t{meta.get('slug') or '-'}\t{meta.get('base') or '-'}\t{'yes' if meta.get('gh') else 'no'}")
    state = "rescanned" if stale else f"fresh, {int((age or 0) // 60)}m of {int(ttl // 60)}m"
    print(f"#cache\t{state}\t{DISCOVERY_CACHE}", file=sys.stderr)
    return 0



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


def handover(mode: str, task: str, clause: str) -> str | None:
    """The text a worker starts from: preamble, mode prompts, task, completion clause.

    A prompt file that is missing or empty is reported and returns None: the worker would
    otherwise start without the rules it is meant to obey.
    """
    names = ["preamble", "work"] + (["hotfix"] if mode == "hotfix" else [])
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
    return "\n\n".join(parts + [task] + ([clause] if clause else []))


def cmd_spawn(args: argparse.Namespace) -> int:
    """Start a job: create its worktree, then print the one command that hands over the task."""
    if args.mode not in {"fast", "hotfix", "feat"}:
        print("mode must be fast, hotfix or feat", file=sys.stderr)
        return 2
    if not args.task:
        print("spawn needs --task", file=sys.stderr)
        return 2

    repo = args.repo[0] if args.repo else Path.cwd()
    slug = "-".join(word for word in re.split(r"[^a-z0-9]+", args.task.lower()) if word and word not in STOP_WORDS)[:60] or "job"
    branch = f"worktree/{slug}"
    path = Path(args.dest).expanduser() / slug if args.dest else Path.home() / ".herdr" / "worktrees" / repo.name / slug
    # The worker reports into this pane; without it there is no address to bake in, and a
    # guessed one would send a completion line nowhere.
    pane = os.environ.get("HERDR_PANE_ID", "")
    if not pane:
        print("#warning\tHERDR_PANE_ID unset: completion clause omitted", file=sys.stderr)
    text = handover(args.mode, args.task, completion(branch, pane) if pane else "")
    if text is None:
        return 1

    print(f"#worktree\t{path}\nbranch\t{branch}\nmode\t{args.mode}")
    if args.dry_run:
        print(f"would run\tgit -C {repo} worktree add -b {branch} {path} origin/{args.base}")
    elif not ok(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(path), f"origin/{args.base}"]):
        print("worktree creation failed", file=sys.stderr)
        return 1
    else:
        entries = registry()
        entries[str(path.resolve())] = {"repo": str(repo), "branch": branch, "mode": args.mode, "task": args.task}
        save_registry(entries)
        print("next\tstart an agent in that path, then:")
    print(f'\therdr agent prompt <pane> "{text}"')
    return 0




def cmd_bootstrap(args: argparse.Namespace) -> int:
    """Every read-only table a pass needs, in one process: one GitHub round trip, one git probe.

    The commands below each read the same facts; run separately they pay for them again.
    """
    print("## preflight")
    code = cmd_preflight(argparse.Namespace(**{**vars(args), "apply": False, "refresh": False}))
    for title, handler, extra in (
        ("discover", cmd_discover, {"refresh": False, "root": []}),
        ("inventory", cmd_inventory, {}),
        ("mode", cmd_mode, {"transcript": ""}),
        ("order", cmd_order, {}),
        ("plans", cmd_plans, {"inject": False, "approve": False}),
        ("rename", cmd_rename, {"apply": False}),
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
    spawn.add_argument("--task", default="", help="what the worker should do")
    spawn.add_argument("--dry-run", action="store_true", help="print instead of creating")
    spawn.add_argument("--dest", default="", help="parent directory for the worktree (default ~/.herdr/worktrees/<repo>)")
    # The same two flags as the top level, so `spawn … --repo PATH` reads as the table says;
    # SUPPRESS keeps a value given before the subcommand instead of resetting it.
    spawn.add_argument("--repo", action="append", default=argparse.SUPPRESS, help="repository to start the job in")
    spawn.add_argument("--base", default=argparse.SUPPRESS, help="base branch for the worktree")

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

    preflight = subs.add_parser("preflight", help="verify dependencies once, then reprint the verdict")
    preflight.add_argument("--apply", action="store_true", help="install what is absent, then re-check")
    preflight.add_argument("--refresh", action="store_true", help="re-check even when a verdict is stored")

    discover = subs.add_parser("discover", help="repositories under the configured roots")
    discover.add_argument("--refresh", action="store_true", help="rescan and replace the cache")
    discover.add_argument("--root", action="append", default=[], help="scan this root instead of the configured ones")

    subs.add_parser("bootstrap", help="every read-only table a pass needs, in one process")
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

    review = subs.add_parser("review", help="capture the screen of worktrees awaiting review")
    review.add_argument("--capture", default="", help="directory for the captures")

    args = parser.parse_args(argv)
    args.repo = [Path(path).expanduser() for path in args.repo]
    if not args.repo and run(["git", "-C", str(Path.cwd()), "rev-parse", "--git-dir"]):
        args.repo = [Path.cwd()]
    handlers = {
        "preflight": cmd_preflight,
        "discover": cmd_discover,
        "registry": cmd_registry,
        "adopt": cmd_adopt,
        "mode": cmd_mode,
        "spawn": cmd_spawn,
        "bootstrap": cmd_bootstrap,
        "inventory": cmd_inventory,
        "order": cmd_order,
        "status": cmd_status,
        "plans": cmd_plans,
        "prune": cmd_prune,
        "rename": cmd_rename,
        "review": cmd_review,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
