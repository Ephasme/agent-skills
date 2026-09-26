#!/usr/bin/env python3
"""herd — run a DAG of coding tasks as omp agents, one herdr worktree each.

    herd.py check  <manifest>          validate, resolve the model, print the waves
    herd.py render <manifest> [id...]  write prompts/<id>.md previews (worktree path unresolved)
    herd.py start  <manifest>          check, then run the scheduler in its own herdr tab
    herd.py run    <manifest>          the scheduler loop itself (what `start` runs)
    herd.py launch <manifest> <id>     launch one task now; --force ignores unfinished deps
    herd.py status <manifest>          one line per task

A task launches when every task in its `after` list has a done marker AND a clean
worktree. Its branch is cut from its first dependency (or the manifest base) and
every other dependency is merged in; a conflicting merge is aborted and handed to
the agent as its first step. Paths in the manifest are relative to its directory.
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

def sh(*argv, cwd=None, check=True):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
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
        merge = [d for d in deps if d != base] + [b for b in t.get("merge", []) if b not in deps]
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

    if errors:
        raise HerdError("check failed:\n  - " + "\n  - ".join(errors))

    print(f"run {run.name}: repo {run.repo}, base {run.base}, plan mode {'on' if run.plan else 'off'}")
    for i, layer in enumerate(waves, 1):
        for tid in layer:
            base, merge = run.base_of(tid)
            model, thinking = selectors[(run.tasks[tid].get("model", run.model), run.tasks[tid].get("thinking", run.thinking))], run.tasks[tid].get("thinking", run.thinking)
            extra = f" + merge {', '.join(merge)}" if merge else ""
            print(f"  wave {i}: {tid:<24} from {base}{extra}  [{model}:{thinking}]")

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
        "Never push, never merge into another branch, never touch another worktree.\n"
        f"- {mode}"
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
        "the marker is the last step."
    )


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
    while True:
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
        if all(run.marker("done", t).exists() or run.marker("failed", t).exists() for t in run.order):
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
    ap.add_argument("cmd", choices=["check", "render", "start", "run", "launch", "status"])
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
    except HerdError as e:
        print(f"herd: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
