#!/usr/bin/env python3
"""herd — run a DAG of coding tasks as omp agents, one herdr worktree each.

    herd.py check  <manifest>          validate, resolve the model, print the waves and PR stacks
    herd.py render <manifest> [id...]  write prompts/<id>.md previews (worktree path unresolved)
    herd.py start  <manifest>          check, then run the scheduler in its own herdr tab
    herd.py run    <manifest>          the scheduler loop itself (what `start` runs)
    herd.py launch <manifest> <id>     launch one task now; --force ignores unfinished deps
    herd.py status <manifest>          one line per task
    herd.py stack  <manifest>          open/retarget PRs and link each chain as a GitHub stack

A task launches when every task in its `after` list has a done marker AND a clean
worktree. Its branch is cut from its first dependency (or the manifest base) and
every other dependency is merged in; a conflicting merge is aborted and handed to
the agent as its first step. Paths in the manifest are relative to its directory.

With `"pr": "stack"` in the manifest, the dependency graph is also a set of GitHub
stacked pull requests: every chain of single-dependency tasks is one stack, each PR
based on the branch below it. `stack` (run by the scheduler whenever a task is done)
pushes, opens missing PRs as drafts, fixes bases and links the chain.
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_MODEL = "deepseek-v4.1-flash"
DEFAULT_THINKING = "high"
POLL_S = 20
INJECT_TIMEOUT_S = 90
BRANCH_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")
AGENT_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]{0,31}$")


class HerdError(Exception):
    pass


# ---------------------------------------------------------------- plumbing

def sh(*argv, cwd=None, check=True, env=None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, env=env)
    if check and p.returncode != 0:
        raise HerdError(f"{' '.join(shlex.quote(a) for a in argv)} failed ({p.returncode}): {(p.stderr or p.stdout).strip()}")
    return p


def herdr(*args, check=True):
    p = sh("herdr", *args, check=check)
    try:
        return json.loads(p.stdout) if p.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"raw": p.stdout}


def notify(title, body, sound="request"):
    sh("herdr", "notification", "show", title, "--body", body, "--sound", sound, check=False)


class Run:
    def __init__(self, manifest_path):
        self.manifest = Path(manifest_path).expanduser().resolve()
        if not self.manifest.is_file():
            raise HerdError(f"no manifest at {self.manifest}")
        self.dir = self.manifest.parent
        m = json.loads(self.manifest.read_text())
        self.name = m.get("name") or self.dir.name
        self.repo = Path(m["repo"]).expanduser().resolve()
        self.base = m.get("base") or sh("git", "-C", str(self.repo), "symbolic-ref", "--short", "HEAD").stdout.strip()
        self.model = m.get("model", DEFAULT_MODEL)
        self.thinking = m.get("thinking", DEFAULT_THINKING)
        self.plan = m.get("plan", True)
        self.context = m.get("context")
        self.tasks = {t["id"]: t for t in m["tasks"]}
        self.order = [t["id"] for t in m["tasks"]]
        self.pr = m.get("pr", "none")
        if self.pr not in ("none", "stack"):
            raise HerdError(f"`pr` must be \"none\" or \"stack\", not {self.pr!r}")
        for sub in ("done", "started", "failed", "prompts"):
            (self.dir / sub).mkdir(exist_ok=True)

    def log(self, msg):
        line = f"{time.strftime('%F %T')} {msg}"
        print(line, flush=True)
        with open(self.dir / "herd.log", "a") as f:
            f.write(line + "\n")

    def marker(self, kind, tid):
        return self.dir / kind / tid

    def after(self, tid):
        return self.tasks[tid].get("after", [])

    def base_of(self, tid):
        t = self.tasks[tid]
        deps = self.after(tid)
        base = t.get("base") or (deps[0] if deps else self.base)
        if self.pr == "stack" and not t.get("base") and len(deps) > 1:
            # The dependency every other one sits below, when there is one: cutting from it
            # needs no merge, which keeps the stack linear.
            top = [d for d in deps if set(deps) - {d} <= self.lineage(d)]
            base = top[0] if top else base
        merge = [d for d in deps if d != base and d not in self.lineage(base)] + \
                [b for b in t.get("merge", []) if b not in deps]
        return base, merge

    def worktree_of(self, branch):
        res = herdr("worktree", "list", "--cwd", str(self.repo), check=False)
        for w in res.get("result", {}).get("worktrees", []):
            if w.get("branch") == branch:
                return w
        return None

    def waves(self):
        """Topological layers; raises on unknown deps or cycles."""
        remaining, placed, out = set(self.order), set(), []
        while remaining:
            layer = [t for t in self.order if t in remaining and set(self.after(t)) <= placed]
            if not layer:
                raise HerdError(f"dependency cycle among: {', '.join(sorted(remaining))}")
            out.append(layer)
            placed |= set(layer)
            remaining -= set(layer)
        return out

    def pr_base(self, tid):
        """The branch a task's PR targets: the branch it was cut from."""
        return self.base_of(tid)[0]

    def stack_errors(self):
        """GitHub merges a stack only with a fully linear history, so a layer may never merge
        a second branch in. A task that joins several dependencies is valid only when they
        already lie on one chain; it is then cut from the highest of them."""
        errors = []
        for tid in self.order:
            deps = self.after(tid)
            if self.tasks[tid].get("merge"):
                errors.append(f"{tid}: `merge` is incompatible with `pr: stack` (a stack needs linear history)")
            if len(deps) < 2:
                continue
            base = self.base_of(tid)[0]
            below = self.lineage(base)
            stray = [d for d in deps if d != base and d not in below]
            if stray:
                errors.append(
                    f"{tid}: joins {', '.join(deps)}, which are not one chain, so its layer would need a merge "
                    f"commit. Serialise them (e.g. make {stray[0]} depend on {base}) and list the top one first")
        return errors

    def lineage(self, tid):
        """Every task below `tid` along its cut-from chain."""
        out = set()
        while tid in self.tasks:
            tid = self.base_of(tid)[0]
            out.add(tid)
        return out

    def stacks(self):
        """Chains of the PR graph, bottom first. GitHub stacks are linear and a PR belongs to
        one stack, so a parent's first child continues its chain and every other child starts
        a new chain on top of the parent's branch."""
        children = {t: [c for c in self.order if self.pr_base(c) == t] for t in self.order}
        chains, placed = [], set()
        for tid in self.order:
            if tid in placed:
                continue
            chain = [tid]
            while children[chain[-1]]:
                chain.append(children[chain[-1]][0])
            placed.update(chain)
            chains.append(chain)
        return chains


# ---------------------------------------------------------------- model

def resolve_model(pattern, thinking):
    """omp fuzzy-matches `--model`, and a bare `openrouter/...` id silently picks the
    `openrouter` provider even when the model is only reachable through another one
    (a proxy that re-exports it) — the agent then boots and fails on its first turn
    with "No API key found". Resolving to the full catalog selector here avoids that."""
    p = sh("omp", "models", "--json")
    models = [m for m in json.loads(p.stdout)["models"] if m.get("kind", "chat") == "chat"]
    exact = [m for m in models if m["selector"] == pattern]
    hits = exact or [m for m in models if pattern.lower() in (m["selector"] + " " + m.get("name", "")).lower()]
    if not hits:
        raise HerdError(f"no model matches {pattern!r}; `omp models` lists what is available")
    if len(hits) > 1:
        raise HerdError(f"{pattern!r} is ambiguous: " + ", ".join(m["selector"] for m in hits))
    m = hits[0]
    if thinking and m.get("thinking") and thinking not in m["thinking"]:
        raise HerdError(f"{m['selector']} supports thinking {m['thinking']}, not {thinking!r}")
    return m["selector"]


# ---------------------------------------------------------------- check

def check(run, ping=False):
    errors = []
    if not shutil.which("herdr"):
        errors.append("herdr is not on PATH")
    if not shutil.which("omp"):
        errors.append("omp is not on PATH")
    if sh("git", "-C", str(run.repo), "rev-parse", "--git-dir", check=False).returncode != 0:
        errors.append(f"{run.repo} is not a git repository")
    elif sh("git", "-C", str(run.repo), "rev-parse", "--verify", run.base, check=False).returncode != 0:
        errors.append(f"base {run.base!r} does not resolve in {run.repo}")

    heads = sh("git", "-C", str(run.repo), "for-each-ref", "refs/heads", "--format=%(refname:short)", check=False).stdout.split()
    for tid in run.order:
        t = run.tasks[tid]
        if not BRANCH_RE.match(tid) or not AGENT_NAME_RE.match(tid):
            errors.append(f"{tid}: id must match {AGENT_NAME_RE.pattern} — it is the branch and the herdr agent name")
        if not (run.dir / t.get("prompt", f"{tid}.md")).is_file():
            errors.append(f"{tid}: prompt file {t.get('prompt', f'{tid}.md')} missing")
        if not t.get("summary"):
            errors.append(f"{tid}: `summary` missing — siblings read it to know what not to touch")
        for d in run.after(tid):
            if d not in run.tasks:
                errors.append(f"{tid}: depends on unknown task {d!r}")
        if not run.marker("started", tid).exists():
            for h in heads:
                if h == tid or tid.startswith(h + "/") or h.startswith(tid + "/"):
                    errors.append(f"{tid}: branch collides with existing branch {h!r}; rename the task")
        for key in ("model", "thinking"):
            if key in t and not t[key]:
                errors.append(f"{tid}: empty {key}")
    if run.context and not (run.dir / run.context).is_file():
        errors.append(f"context file {run.context} missing")
    try:
        waves = run.waves()
        if run.pr == "stack":
            errors += run.stack_errors()
    except HerdError as e:
        errors.append(str(e))
        waves = []

    selectors = {}
    for tid in run.order:
        key = (run.tasks[tid].get("model", run.model), run.tasks[tid].get("thinking", run.thinking))
        if key not in selectors:
            try:
                selectors[key] = resolve_model(*key)
            except HerdError as e:
                errors.append(str(e))
                selectors[key] = None

    if run.pr == "stack":
        errors += stack_prerequisites(run)

    if errors:
        raise HerdError("check failed:\n  - " + "\n  - ".join(errors))

    print(f"run {run.name}: repo {run.repo}, base {run.base}, plan mode {'on' if run.plan else 'off'}")
    for i, layer in enumerate(waves, 1):
        for tid in layer:
            base, merge = run.base_of(tid)
            model, thinking = selectors[(run.tasks[tid].get("model", run.model), run.tasks[tid].get("thinking", run.thinking))], run.tasks[tid].get("thinking", run.thinking)
            extra = f" + merge {', '.join(merge)}" if merge else ""
            print(f"  wave {i}: {tid:<24} from {base}{extra}  [{model}:{thinking}]")
    if run.pr == "stack":
        for chain in run.stacks():
            bottom = run.pr_base(chain[0])
            kind = "stack" if len(chain) > 1 else "PR"
            print(f"  {kind}: {bottom} <- " + " <- ".join(chain))

    if ping:
        for (pattern, thinking), sel in selectors.items():
            p = sh("omp", "--model", sel, "--thinking", thinking, "--no-session", "-p", "Reply with exactly: ok", check=False)
            ok = p.returncode == 0 and "ok" in p.stdout.lower()
            print(f"  ping {sel}: {'ok' if ok else 'FAILED — ' + (p.stderr or p.stdout).strip()[-300:]}")
            if not ok:
                raise HerdError(f"model {sel} did not answer")
    return selectors


# ---------------------------------------------------------------- prompts

def relation(run, tid, other):
    def ancestors(t, seen=None):
        seen = seen if seen is not None else set()
        for d in run.after(t):
            if d not in seen:
                seen.add(d)
                ancestors(d, seen)
        return seen
    if other in ancestors(tid):
        return "done before you start — its branch is in your base"
    if tid in ancestors(other):
        return "starts from your branch once you finish"
    return "runs at the same time as you, in its own worktree"


def render(run, tid, worktree="(assigned at launch)", merge_note=""):
    t = run.tasks[tid]
    base, merge = run.base_of(tid)
    values = {
        "TASK_ID": tid,
        "BRANCH": tid,
        "BASE": base + (f" + {', '.join(merge)}" if merge else ""),
        "WORKTREE": worktree,
        "SLUG": re.sub(r"[^a-z0-9]+", "_", tid.lower()),
        "RUN_DIR": str(run.dir),
        "DONE": str(run.marker("done", tid)),
    }

    def fill(text):
        return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), text)

    parts = [fill((run.dir / t.get("prompt", f"{tid}.md")).read_text().strip())]

    siblings = [o for o in run.order if o != tid]
    if siblings:
        rows = "\n".join(f"- `{o}` — {run.tasks[o]['summary']} ({relation(run, tid, o)})" for o in siblings)
        parts.append(
            "# The other agents in this run\n\n"
            f"{rows}\n\n"
            "Stay inside your own task: a change that belongs to a sibling's scope makes two branches "
            "conflict at merge time. Where your design constrains a later task, leave a seam for it; "
            "do not build its part."
        )

    mode = (
        "You start in **plan mode**. Research read-only, write the plan, propose it and wait for "
        "approval. Put genuine tradeoffs to the user as questions rather than guessing. No edits "
        "before approval."
        if t.get("plan", run.plan) else
        "Start working directly; ask the user only where a decision is genuinely theirs."
    )
    parts.append(
        "# Where you are\n\n"
        f"- Worktree `{values['WORKTREE']}`, branch `{tid}`, cut from `{values['BASE']}`. Work only here. "
        "Never merge into another branch, never touch another worktree.\n"
        f"- {mode}\n"
        f"- {pr_rules(run, tid)}"
    )
    if merge_note:
        parts.append("# Merge status\n\n" + merge_note)
    if t.get("plan", run.plan):
        parts.append(
            "# The plan must contain\n\n"
            "- The files touched and, for any state, its single owner.\n"
            "- What the change deletes or replaces, so nothing obsolete survives beside the new path.\n"
            "- The invariants that must survive, and how each one is verified.\n"
            "- The exact scenarios you will run to prove it works — commands, pages, requests."
        )
    if run.context:
        parts.append(fill((run.dir / run.context).read_text().strip()))
    parts.append(done_protocol(run, tid))
    return "\n\n---\n\n".join(parts) + "\n"


def pr_rules(run, tid):
    if run.pr != "stack":
        return "Never push and never open a PR unless the user asks."
    below = run.pr_base(tid)
    return (
        "Pull requests are managed for you as a GitHub stack: once you write your done marker, your "
        f"branch is pushed, opened as a draft PR on `{below}` and linked into its stack. Do not open, "
        "retarget or merge PRs yourself, never rebase a branch below yours, and never merge another "
        "branch into yours — a stack merges only with a linear history. When the branch below you "
        f"(`{below}`) changes, move only your own commits onto it: `git fetch origin && git rebase "
        f"--onto origin/{below} <previous {below} tip> {tid}`, then `git push --force-with-lease`."
    )


def done_protocol(run, tid):
    return (
        "# Done means\n\n"
        "Every acceptance scenario exercised for real, the project's own checks green, everything "
        f"committed on `{tid}` with a clean `git status`. Then, and only then:\n\n"
        "```\n"
        f"touch {run.marker('done', tid)}\n"
        f"herdr notification show \"{tid} done\" --body \"<one line>\" --sound done\n"
        "```\n\n"
        "The marker is what starts any agent that depends on your branch, so never create it "
        "early. Then report what changed and what is untested. This holds after plan approval "
        "and after any follow-up request: whenever the work on this branch is finished again, "
        "the marker is the last step.\n\n"
        + pr_rules(run, tid)
    )


# ---------------------------------------------------------------- PR stacks

GH_API_VERSION = "2026-03-10"


def gh(run, *args, check=True):
    # gh-stack resolves the repository from the remote URL alone and fails on an SSH host alias
    # (`git@github.com-work:…`) that `gh` itself maps; GH_REPO makes both agree.
    if not getattr(run, "slug", None):
        run.slug = sh("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner",
                      cwd=str(run.repo)).stdout.strip()
    return sh("gh", *args, cwd=str(run.repo), check=check, env={**os.environ, "GH_REPO": run.slug})


def stack_prerequisites(run):
    if not shutil.which("gh"):
        return ["`pr: stack` needs the GitHub CLI (`gh`) on PATH"]
    errors = []
    if gh(run, "stack", "--version", check=False).returncode != 0:
        errors.append("`pr: stack` needs the gh-stack extension: `gh extension install github/gh-stack`")
    p = gh(run, "api", "-H", f"X-GitHub-Api-Version: {GH_API_VERSION}",
           "repos/{owner}/{repo}/stacks?per_page=1", check=False)
    if p.returncode != 0:
        errors.append("stacked pull requests are not available on this repository "
                      f"(GET /stacks: {(p.stderr or p.stdout).strip()[-200:]}); enable them or use \"pr\": \"none\"")
    return errors


def open_pr(run, branch):
    p = gh(run, "pr", "list", "--head", branch, "--state", "open", "--json", "number,baseRefName", check=False)
    rows = json.loads(p.stdout or "[]") if p.returncode == 0 else []
    return rows[0] if rows else None


def push(run, branch):
    """Pushes a branch the agent left local. A branch origin already has at another commit is
    never forced: the agent that owns it rebased or pushed it deliberately."""
    local = sh("git", "-C", str(run.repo), "rev-parse", branch).stdout.strip()
    remote = sh("git", "-C", str(run.repo), "ls-remote", "--heads", "origin", branch).stdout.split()
    if remote and remote[0] == local:
        return
    if remote and sh("git", "-C", str(run.repo), "merge-base", "--is-ancestor", remote[0], local,
                     check=False).returncode != 0:
        raise HerdError(f"{branch}: origin/{branch} has diverged from the local branch; not forcing it")
    sh("git", "-C", str(run.repo), "push", "--quiet", "origin", f"{branch}:{branch}")


def sync_stacks(run):
    """Brings GitHub in line with the manifest for every finished task: branch pushed, a PR open
    against its `pr_base`, each chain linked as a stack bottom first. A chain grows as its layers
    finish, since a stack must be contiguous from its bottom. Idempotent."""
    numbers = {}
    for tid in run.order:
        if not run.marker("done", tid).exists():
            continue
        base = run.pr_base(tid)
        push(run, tid)
        pr = open_pr(run, tid)
        if pr is None:
            summary = run.tasks[tid]["summary"]
            gh(run, "pr", "create", "--draft", "--head", tid, "--base", base,
               "--title", summary[:1].upper() + summary[1:], "--fill-first")
            pr = open_pr(run, tid)
            run.log(f"[{tid}] opened draft PR #{pr['number']} on {base}")
        elif pr["baseRefName"] != base:
            gh(run, "pr", "edit", str(pr["number"]), "--base", base)
            run.log(f"[{tid}] PR #{pr['number']} retargeted {pr['baseRefName']} -> {base}")
        numbers[tid] = pr["number"]

    for chain in run.stacks():
        linked = []
        for tid in chain:
            if tid not in numbers:
                break
            linked.append(str(numbers[tid]))
        if len(linked) < 2:
            continue
        p = gh(run, "stack", "link", "--base", run.pr_base(chain[0]), *linked, check=False)
        if p.returncode != 0:
            raise HerdError(f"gh stack link {' '.join(linked)}: {(p.stderr or p.stdout).strip()[-300:]}")
    return numbers


def stack_view(run):
    for chain in run.stacks():
        prs = {tid: open_pr(run, tid) for tid in chain}
        rows = [f"{tid} #{pr['number']}->{pr['baseRefName']}" if pr else f"{tid} (no PR)" for tid, pr in prs.items()]
        label = "single PR" if len(chain) == 1 else "unlinked chain"
        first = prs[chain[0]]
        if first and len(chain) > 1:
            p = gh(run, "api", "-H", f"X-GitHub-Api-Version: {GH_API_VERSION}",
                   "repos/{owner}/{repo}/stacks?pull_request=" + str(first["number"]), "--jq", ".[0].number // empty", check=False)
            if p.stdout.strip():
                label = f"stack {p.stdout.strip()}"
        print(f"{label}: {run.pr_base(chain[0])} <- " + " <- ".join(rows))


# ---------------------------------------------------------------- launch

def screen(agent, lines=40):
    p = sh("herdr", "agent", "read", agent, "--source", "visible", "--lines", str(lines), check=False)
    return p.stdout


def status_line(text):
    rows = [r for r in text.splitlines() if r.strip()]
    return rows[-1] if rows else ""


def in_plan_mode(agent):
    return re.search(r"\bPlan\b", status_line(screen(agent))) is not None


def agent_status(agent):
    res = herdr("agent", "get", agent, check=False)
    return res.get("result", {}).get("agent", {}).get("agent_status")


def launch(run, tid, force=False):
    t = run.tasks[tid]
    if run.marker("started", tid).exists():
        raise HerdError(f"{tid} already launched (remove {run.marker('started', tid)} to relaunch)")
    pending = [d for d in run.after(tid) if not run.marker("done", d).exists()]
    if pending and not force:
        raise HerdError(f"{tid} waits on {', '.join(pending)}")
    base, merge = run.base_of(tid)
    model = resolve_model(t.get("model", run.model), t.get("thinking", run.thinking))
    thinking = t.get("thinking", run.thinking)

    created = herdr("worktree", "create", "--cwd", str(run.repo), "--branch", tid, "--base", base,
                    "--label", tid, "--no-focus")["result"]
    wt, pane = created["root_pane"]["cwd"], created["root_pane"]["pane_id"]
    run.marker("started", tid).write_text(json.dumps({"worktree": wt, "pane": pane, "model": model}) + "\n")
    run.log(f"[{tid}] worktree {wt} pane {pane} from {base}")

    notes = []
    for b in merge:
        p = sh("git", "-C", wt, "merge", "--no-edit", b, check=False)
        if p.returncode == 0:
            run.log(f"[{tid}] merged {b}")
        else:
            sh("git", "-C", wt, "merge", "--abort", check=False)
            notes.append(f"- `{b}` did NOT merge cleanly. Merging it and resolving the conflicts is the "
                         f"first step of your plan; read its side meanwhile with `git show {b}:<path>`.")
            run.log(f"[{tid}] merge of {b} conflicted; left to the agent")

    prompt = render(run, tid, worktree=wt, merge_note="\n".join(notes))
    (run.dir / "prompts" / f"{tid}.md").write_text(prompt)
    # Approving a plan starts a fresh session that carries only the plan, so the task prompt —
    # and the done protocol at its end — is gone for the whole execution phase. The system
    # prompt survives that handoff (verified), so the protocol is pinned there as well.
    system = run.dir / "prompts" / f"{tid}.system.md"
    system.write_text(
        f"You are the `{tid}` agent of the `{run.name}` run, working in `{wt}` on branch `{tid}`.\n\n"
        + done_protocol(run, tid) + "\n"
    )

    # A pane that was just created may not be at its prompt yet.
    for attempt in range(6):
        p = sh("herdr", "agent", "start", tid, "--kind", "omp", "--pane", pane, "--timeout", "120000",
               "--", "--model", model, "--thinking", thinking, "--append-system-prompt", str(system),
               check=False)
        if p.returncode == 0:
            break
        time.sleep(3)
    else:
        raise HerdError(f"{tid}: omp did not start in {pane}: {p.stderr.strip()}")

    if t.get("plan", run.plan) and not in_plan_mode(tid):
        # `/plan` toggles, so it is sent only when the status line says plan mode is off.
        herdr("agent", "prompt", tid, "/plan")
        time.sleep(2)
        if not in_plan_mode(tid):
            raise HerdError(f"{tid}: plan mode did not engage; the prompt was not sent")

    herdr("agent", "prompt", tid, prompt)
    deadline = time.time() + INJECT_TIMEOUT_S
    while time.time() < deadline:
        time.sleep(2)
        tail = "\n".join(screen(tid, 60).splitlines()[-20:])
        err = re.search(r"^\s*Error: .*$", tail, re.M)
        if err:
            raise HerdError(f"{tid}: omp answered the prompt with: {err.group(0).strip()}")
        if agent_status(tid) in ("working", "blocked"):
            run.log(f"[{tid}] prompt injected, agent working ({model}:{thinking}, plan={t.get('plan', run.plan)})")
            notify(f"{tid}: {'planning' if t.get('plan', run.plan) else 'working'}", f"{run.name}: agent started in {Path(wt).name}")
            return
    raise HerdError(f"{tid}: agent never started working after the prompt; inspect with `herdr agent read {tid}`")


# ---------------------------------------------------------------- scheduler

def dep_ready(run, dep):
    if not run.marker("done", dep).exists():
        return False
    w = run.worktree_of(dep)
    if w and sh("git", "-C", w["path"], "status", "--porcelain", check=False).stdout.strip():
        return None  # done but dirty
    return True


def stalled(run, tid):
    """Launched, not done, agent at rest, and its branch holds committed work on a clean tree:
    the agent most likely finished without writing its marker. Returns a reason or None."""
    if run.marker("done", tid).exists() or not run.marker("started", tid).exists():
        return None
    if agent_status(tid) not in ("idle", "done", None):
        return None
    w = run.worktree_of(tid)
    if not w:
        return None
    if sh("git", "-C", w["path"], "status", "--porcelain", check=False).stdout.strip():
        return None
    base, _ = run.base_of(tid)
    ahead = sh("git", "-C", w["path"], "rev-list", "--count", f"{base}..HEAD", check=False).stdout.strip()
    if not ahead or ahead == "0":
        return None
    return f"agent {agent_status(tid) or 'gone'}, {ahead} commit(s) on a clean tree, no done marker"


def run_loop(run):
    run.log(f"scheduler up for {run.name}")
    warned = set()
    synced = None  # the set of done markers the last stack sync saw
    while True:
        if run.pr == "stack":
            done = frozenset(t for t in run.order if run.marker("done", t).exists())
            if done != synced:
                try:
                    sync_stacks(run)
                    synced = done
                except HerdError as e:
                    if ("stack", str(e)) not in warned:
                        warned.add(("stack", str(e)))
                        run.log(f"stack sync failed, retrying next tick: {e}")
                        notify("PR stack sync failed", str(e)[:200])
        for tid in run.order:
            reason = stalled(run, tid)
            key = ("stalled", tid)
            if reason and key not in warned:
                warned.add(key)
                blocked = [t for t in run.order if tid in run.after(t)]
                run.log(f"[{tid}] looks finished but unmarked ({reason}); blocks {', '.join(blocked) or 'nothing'}")
                notify(f"{tid}: finished but unmarked?",
                       f"touch {run.marker('done', tid)} to release {', '.join(blocked) or 'nothing'}")
            elif not reason:
                warned.discard(key)
        waiting = [t for t in run.order if not run.marker("started", t).exists() and not run.marker("failed", t).exists()]
        if all(run.marker("done", t).exists() or run.marker("failed", t).exists() for t in run.order) \
                and (run.pr != "stack" or synced == frozenset(t for t in run.order if run.marker("done", t).exists())):
            run.log("every task done or failed; scheduler exits")
            return
        for tid in waiting:
            states = {d: dep_ready(run, d) for d in run.after(tid)}
            dirty = [d for d, s in states.items() if s is None]
            for d in dirty:
                if d not in warned:
                    warned.add(d)
                    run.log(f"[{tid}] {d} marked done with uncommitted changes; waiting for a clean tree")
                    notify(f"{d}: done but dirty", f"{tid} waits for {d} to commit")
            if all(s is True for s in states.values()):
                try:
                    launch(run, tid)
                except HerdError as e:
                    run.marker("failed", tid).write_text(str(e) + "\n")
                    run.log(f"[{tid}] FAILED: {e}")
                    notify(f"{tid}: launch failed", str(e)[:200])
        time.sleep(POLL_S)


def start(run):
    check(run)
    ws = os.environ.get("HERDR_WORKSPACE_ID")
    if not ws:
        raise HerdError("not inside a herdr pane (HERDR_WORKSPACE_ID unset)")
    tab = herdr("tab", "create", "--workspace", ws, "--cwd", str(run.dir), "--label", f"herd-{run.name}"[:32], "--no-focus")
    pane = tab["result"]["root_pane"]["pane_id"]
    time.sleep(2)
    cmd = f"python3 {shlex.quote(str(Path(__file__).resolve()))} run {shlex.quote(str(run.manifest))}"
    herdr("pane", "run", pane, cmd)
    print(f"scheduler running in pane {pane}; log: {run.dir / 'herd.log'}")


def status(run):
    for tid in run.order:
        if run.marker("done", tid).exists():
            state = "done"
        elif run.marker("failed", tid).exists():
            state = "failed: " + run.marker("failed", tid).read_text().strip().splitlines()[0][:100]
        elif run.marker("started", tid).exists():
            reason = stalled(run, tid)
            state = (f"STALLED: {reason} — `touch {run.marker('done', tid)}` if it is finished" if reason else
                     f"agent {agent_status(tid) or 'gone'}" + (" (plan mode)" if agent_status(tid) and in_plan_mode(tid) else ""))
        else:
            pending = [d for d in run.after(tid) if not run.marker("done", d).exists()]
            state = "waiting on " + ", ".join(pending) if pending else "ready"
        print(f"{tid:<24} {state}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["check", "render", "start", "run", "launch", "status", "stack"])
    ap.add_argument("manifest")
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--ping", action="store_true", help="check: send each model a one-line prompt")
    ap.add_argument("--force", action="store_true", help="launch: ignore unfinished dependencies")
    a = ap.parse_args()
    try:
        run = Run(a.manifest)
        if a.cmd == "check":
            check(run, ping=a.ping)
        elif a.cmd == "render":
            for tid in a.ids or run.order:
                out = run.dir / "prompts" / f"{tid}.md"
                out.write_text(render(run, tid))
                print(out)
        elif a.cmd == "start":
            start(run)
        elif a.cmd == "run":
            run_loop(run)
        elif a.cmd == "launch":
            for tid in a.ids:
                launch(run, tid, force=a.force)
        elif a.cmd == "status":
            status(run)
            if run.pr == "stack":
                stack_view(run)
        elif a.cmd == "stack":
            if run.pr != "stack":
                raise HerdError("the manifest has no `\"pr\": \"stack\"`")
            errors = stack_prerequisites(run)
            if errors:
                raise HerdError("; ".join(errors))
            sync_stacks(run)
            stack_view(run)
    except HerdError as e:
        print(f"herd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
