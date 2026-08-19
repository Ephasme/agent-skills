#!/usr/bin/env python3
"""Schedule, list, remove, and run recurring or one-time prompts against a
herdr-managed agent pane, with an ntfy status push on each run.

Stdlib plus `croniter` for cron-field parsing (auto-installed on first cron use,
mirroring the payment-qr skill's segno bootstrap). macOS/launchd only (see SKILL.md `compatibility`).

Subcommands:
  schedule --repeat=<VALUE> [--target NAME] [--name NAME] [--ntfy-topic TOPIC]
           [--timeout SECONDS] [--no-ntfy] [--cwd PATH] "<prompt text>"
  list
  remove <name>
  run-job <name>      (invoked by launchd; also runnable manually to test a job)

--repeat grammar (exactly one form):
  no                      one-time: submit the prompt immediately, no job created
  <N><s|m|h|d>            fixed interval (e.g. "90s", "30m", "1h", "2d") -> launchd StartInterval
  "<5-field cron>"        minute hour dom month dow -> launchd StartCalendarInterval
  anything else           rejected; plain English must be translated to one of the
                          above (by the caller) before invoking this script
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import plistlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

SKILL_NAME = "herdr-schedule-prompt"
LABEL_PREFIX = "com.agent-skills.herdr-schedule-prompt"
DEFAULT_NTFY_TOPIC = "herdr-scheduled-prompts"
DEFAULT_RUN_TIMEOUT = 900  # seconds a single run may take before it's reported as a timeout
POLL_INTERVAL = 3  # seconds between agent-status polls in run-job
MAX_CRON_COMBINATIONS = 500  # guard against accidental "every minute all day" cron jobs
READ_SNIPPET_LINES = 40
NTFY_SNIPPET_CHARS = 800

CRON_FIELDS = [("Minute", 0, 59), ("Hour", 0, 23), ("Day", 1, 31), ("Month", 1, 12), ("Weekday", 0, 7)]

DURATION_RE = re.compile(
    r"^(\d+)\s*(s|sec|secs|second|seconds|m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days)$",
    re.IGNORECASE,
)
UNIT_SECONDS = {
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
    "d": 86400, "day": 86400, "days": 86400,
}


# --------------------------------------------------------------------------
# Paths. $HOME-relative only -- no absolute home path is hard-coded, and none
# of this is committed to the skill's own repo (that's the point of keeping
# it under XDG state, separate from $SKILL_DIR which holds only the script).
# --------------------------------------------------------------------------

def state_dir() -> Path:
    base = Path(os.environ.get("XDG_CONFIG_HOME") or (Path.home() / ".config"))
    d = base / SKILL_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def jobs_dir() -> Path:
    d = state_dir() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def logs_dir() -> Path:
    d = state_dir() / "logs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def job_path(name: str) -> Path:
    return jobs_dir() / f"{name}.json"


def log_path(name: str) -> Path:
    return logs_dir() / f"{name}.log"


def launchd_label(name: str) -> str:
    return f"{LABEL_PREFIX}.{name}"


def plist_path(name: str) -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{launchd_label(name)}.plist"


def log(msg: str) -> None:
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", file=sys.stderr, flush=True)


# --------------------------------------------------------------------------
# herdr driving. Absolute binary path resolved once at schedule time and
# stored in the job, so a launchd job never depends on PATH being populated.
# --------------------------------------------------------------------------

def resolve_herdr() -> str:
    path = shutil.which("herdr")
    if not path:
        raise SystemExit("herdr not found on PATH -- install it or add it to PATH first")
    return path


def herdr_json(bin_path: str, *args: str) -> dict:
    proc = subprocess.run([bin_path, *args], capture_output=True, text=True, timeout=30)
    out = proc.stdout.strip()
    if proc.returncode != 0 and not out:
        raise RuntimeError(f"herdr {' '.join(args)} failed (exit {proc.returncode}): {proc.stderr.strip()}")
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        raise RuntimeError(f"herdr {' '.join(args)} did not return JSON: {out[:200]!r}")
    if isinstance(data, dict) and "error" in data:
        raise RuntimeError(f"herdr {' '.join(args)}: {data['error'].get('message', data['error'])}")
    return data


def herdr_agent_get(bin_path: str, target: str) -> dict | None:
    try:
        data = herdr_json(bin_path, "agent", "get", target)
    except RuntimeError:
        return None
    return data.get("result", {}).get("agent")


def herdr_read(bin_path: str, target: str, lines: int = READ_SNIPPET_LINES) -> str:
    proc = subprocess.run(
        [bin_path, "agent", "read", target, "--lines", str(lines), "--format", "text"],
        capture_output=True, text=True, timeout=30,
    )
    return proc.stdout


def ensure_target(bin_path: str, target: str, cwd: str) -> bool:
    """Return True if `target` already had a live agent, False if one was just created."""
    if herdr_agent_get(bin_path, target) is not None:
        return True
    result = herdr_json(bin_path, "workspace", "create", "--cwd", cwd, "--label", target, "--no-focus")
    pane_id = result["result"]["root_pane"]["pane_id"]
    herdr_json(bin_path, "agent", "start", target, "--kind", "omp", "--pane", pane_id, "--timeout", "60000")
    return False


# --------------------------------------------------------------------------
# --repeat parsing
# --------------------------------------------------------------------------

def _ensure_croniter():
    """Import `croniter`, installing it on demand. Mirrors the payment-qr skill's
    segno bootstrap: already-importable -> pip in the current interpreter across the
    PEP 668 variants -> a disposable isolated venv. Only `schedule` needs this --
    `run-job` never parses cron, so a scheduled firing never depends on it."""
    try:
        import croniter
        return croniter
    except ImportError:
        pass
    for flags in ([], ["--user"], ["--break-system-packages"], ["--user", "--break-system-packages"]):
        r = subprocess.run([sys.executable, "-m", "pip", "install", "--quiet", *flags, "croniter"],
                            capture_output=True, text=True)
        if r.returncode == 0:
            importlib.invalidate_caches()
            try:
                import croniter
                return croniter
            except ImportError:
                continue
    try:
        import tempfile
        import venv
        vdir = tempfile.mkdtemp(prefix="herdr-schedule-venv-")
        venv.create(vdir, with_pip=True)
        bindir = "Scripts" if os.name == "nt" else "bin"
        vpy = os.path.join(vdir, bindir, "python.exe" if os.name == "nt" else "python")
        r = subprocess.run([vpy, "-m", "pip", "install", "--quiet", "croniter"], capture_output=True, text=True)
        if r.returncode == 0:
            site_packages = next(Path(vdir).glob("lib/python*/site-packages"))
            sys.path.insert(0, str(site_packages))
            import croniter
            return croniter
    except Exception:
        pass
    raise SystemExit(
        "croniter is required to parse cron-style --repeat values and could not be imported "
        "or installed (no network, or a locked environment) -- `pip install croniter` "
        "manually, or use a duration repeat ('30m', '1h') instead"
    )


def classify_repeat(value: str):
    """Returns ("once", None) | ("interval", seconds) | ("cron", [field-values...])."""
    v = value.strip()
    if v.lower() == "no":
        return ("once", None)

    m = DURATION_RE.match(v)
    if m:
        n, unit = m.groups()
        seconds = int(n) * UNIT_SECONDS[unit.lower()]
        if seconds < 1:
            raise ValueError("duration must be at least 1 second")
        return ("interval", seconds)

    fields = v.split()
    if len(fields) == 5:
        cron = _ensure_croniter()
        try:
            raw_fields, nth_dow = cron.croniter.expand(v)
        except cron.CroniterError as e:
            raise ValueError(f"looks like a cron expression but is invalid: {e}") from e
        if nth_dow:
            raise ValueError("nth-weekday-of-month cron syntax (e.g. '1#2') isn't supported by launchd")
        expanded = [None if f == ["*"] else list(f) for f in raw_fields]
        if expanded[4] is not None:  # croniter already folds weekday 7 into 0; belt and suspenders
            expanded[4] = sorted({0 if x == 7 else x for x in expanded[4]})
        return ("cron", expanded)

    raise ValueError(
        "could not parse --repeat as 'no', a duration ('90s', '30m', '1h', '2d'), or a "
        "5-field cron expression ('minute hour dom month dow'). Plain English must be "
        "translated into one of those forms first -- this script does not do NLU."
    )


def calendar_dicts(expanded: list[list[int] | None]) -> list[dict[str, int]]:
    if expanded[0] is None:  # Minute == "*"
        raise ValueError(
            "cron mode needs an exact minute (not '*') -- an unconstrained minute means "
            "'every minute', which a duration repeat ('60s') expresses directly and safely"
        )
    constrained = [(name, vals) for (name, _, _), vals in zip(CRON_FIELDS, expanded) if vals is not None]
    if not constrained:
        raise ValueError("cron expression matches every minute of every day -- use a duration repeat instead")
    total = 1
    for _, vals in constrained:
        total *= len(vals)
    if total > MAX_CRON_COMBINATIONS:
        raise ValueError(
            f"cron expression expands to {total} exact minute/hour/weekday combinations "
            f"(launchd has no range/wildcard, only exact matches) -- narrow the schedule, "
            f"or use a duration repeat for anything this frequent"
        )
    dicts: list[dict[str, int]] = [{}]
    for name, vals in constrained:
        dicts = [dict(d, **{name: v}) for d in dicts for v in vals]
    return dicts


def describe_repeat(kind: str, payload) -> str:
    if kind == "once":
        return "one-time"
    if kind == "interval":
        return f"every {payload}s"
    return f"cron ({len(calendar_dicts(payload))} launchd calendar entries)"


# --------------------------------------------------------------------------
# launchd
# --------------------------------------------------------------------------

def gui_domain() -> str:
    return f"gui/{os.getuid()}"


def install_launchd(name: str, kind: str, payload, herdr_bin: str, ntfy_env: dict[str, str]) -> None:
    script_path = str(Path(__file__).resolve())
    python_bin = sys.executable
    plist: dict = {
        "Label": launchd_label(name),
        "ProgramArguments": [python_bin, script_path, "run-job", name],
        "StandardOutPath": str(log_path(name)),
        "StandardErrorPath": str(log_path(name)),
        "RunAtLoad": False,
        "EnvironmentVariables": {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"),
            **ntfy_env,
        },
    }
    if kind == "interval":
        plist["StartInterval"] = payload
    else:
        plist["StartCalendarInterval"] = calendar_dicts(payload)

    path = plist_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as fp:
        plistlib.dump(plist, fp)
    path.chmod(0o600)  # embeds NTFY_TOKEN

    label = launchd_label(name)
    subprocess.run(["launchctl", "bootout", f"{gui_domain()}/{label}"], capture_output=True)
    subprocess.run(["launchctl", "bootstrap", gui_domain(), str(path)], check=True, capture_output=True, text=True)
    subprocess.run(["launchctl", "enable", f"{gui_domain()}/{label}"], capture_output=True)


def remove_launchd(name: str) -> None:
    label = launchd_label(name)
    subprocess.run(["launchctl", "bootout", f"{gui_domain()}/{label}"], capture_output=True)
    plist_path(name).unlink(missing_ok=True)


def is_loaded(name: str) -> bool:
    proc = subprocess.run(["launchctl", "print", f"{gui_domain()}/{launchd_label(name)}"], capture_output=True)
    return proc.returncode == 0


# --------------------------------------------------------------------------
# ntfy
# --------------------------------------------------------------------------

def send_ntfy(url: str, token: str, topic: str, title: str, message: str, priority: str, tags: str) -> None:
    if not url or not token:
        log("ntfy not configured (NTFY_URL/NTFY_TOKEN missing) -- skipping notification")
        return
    endpoint = url.rstrip("/") + "/" + topic
    req = urllib.request.Request(endpoint, data=message.encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Title", title)
    req.add_header("Priority", priority)
    req.add_header("Tags", tags)
    # Python's default "Python-urllib/x.y" UA trips bot rules on Cloudflare-fronted
    # origins (observed: a valid-token request 403s with Cloudflare error code 1010)
    # even with a fully valid token. A generic UA is enough; nothing about the request
    # is scripted in any way the origin actually cares about.
    req.add_header("User-Agent", "curl/8.7.1")
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            log(f"ntfy: {resp.status}")
    except urllib.error.URLError as e:
        log(f"ntfy send failed: {e}")


# --------------------------------------------------------------------------
# Job execution shared by `run-job` (scheduled) and `schedule --repeat=no`
# (immediate, one-shot).
# --------------------------------------------------------------------------

def execute_once(job: dict, herdr_bin: str) -> None:
    name, target, prompt = job["name"], job["target"], job["prompt"]
    timeout = job.get("timeout", DEFAULT_RUN_TIMEOUT)
    try:
        existed = ensure_target(herdr_bin, target, job.get("cwd", str(Path.home())))
        log(f"target {target} {'reused' if existed else 'created'}")
        before = herdr_agent_get(herdr_bin, target)
        baseline_seq = before["state_change_seq"] if before else -1
        herdr_json(herdr_bin, "agent", "prompt", target, prompt)
        log("prompt submitted, polling for settle")

        status = "timeout"
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            cur = herdr_agent_get(herdr_bin, target)
            if cur and cur["state_change_seq"] != baseline_seq and cur["agent_status"] in ("idle", "done", "blocked"):
                status = cur["agent_status"]
                break
        snippet = herdr_read(herdr_bin, target).strip()[-NTFY_SNIPPET_CHARS:]
    except Exception as e:  # noqa: BLE001 -- report every failure via ntfy, never crash silently
        log(f"run failed: {e}")
        status, snippet = "error", str(e)

    outcome = {
        "idle": ("default", "white_check_mark", "done"),
        "done": ("default", "white_check_mark", "done"),
        "blocked": ("high", "warning", "blocked"),
        "timeout": ("urgent", "rotating_light", "timed out"),
        "error": ("urgent", "rotating_light", "errored"),
    }[status]
    priority, tags, verb = outcome
    log(f"outcome: {status}")

    ntfy = job.get("ntfy", {})
    send_ntfy(
        url=os.environ.get("NTFY_URL", ntfy.get("url", "")),
        token=os.environ.get("NTFY_TOKEN", ntfy.get("token", "")),
        topic=ntfy.get("topic", DEFAULT_NTFY_TOPIC),
        title=f"{name}: {verb}",
        message=f"Prompt: {prompt}\n\n{snippet}" if snippet else f"Prompt: {prompt}",
        priority=priority,
        tags=tags,
    )


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------

def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (slug[:40] or "prompt").strip("-")


def cmd_schedule(args: argparse.Namespace) -> None:
    herdr_bin = resolve_herdr()
    prompt = " ".join(args.prompt).strip()
    if not prompt:
        raise SystemExit("prompt text is required")

    kind, payload = classify_repeat(args.repeat)
    name = args.name or slugify(prompt)
    target = args.target or f"sched-{name}"
    cwd = args.cwd or str(Path.home())

    ntfy_url = os.environ.get("NTFY_URL", "")
    ntfy_token = os.environ.get("NTFY_TOKEN", "")
    if not args.no_ntfy and (not ntfy_url or not ntfy_token):
        raise SystemExit(
            "NTFY_URL and NTFY_TOKEN must be set in the environment (or pass --no-ntfy to opt out "
            "of status notifications for this job)"
        )

    job = {
        "name": name,
        "target": target,
        "prompt": prompt,
        "cwd": cwd,
        "repeat": args.repeat,
        "timeout": args.timeout,
        "ntfy": {} if args.no_ntfy else {"url": ntfy_url, "token": ntfy_token, "topic": args.ntfy_topic},
    }

    if kind == "once":
        print(f"running once against {target}...")
        execute_once(job, herdr_bin)
        print("done -- see the target pane and ntfy for the result")
        return

    if job_path(name).exists():
        raise SystemExit(f"job {name!r} already exists -- pick --name explicitly or `remove {name}` first")

    job_path(name).write_text(json.dumps(job, indent=2))
    job_path(name).chmod(0o600)  # embeds NTFY_TOKEN
    ntfy_env = {} if args.no_ntfy else {"NTFY_URL": ntfy_url, "NTFY_TOKEN": ntfy_token}
    install_launchd(name, kind, payload, herdr_bin, ntfy_env)
    print(f"scheduled {name!r}: {describe_repeat(kind, payload)}, target={target}")
    print(f"logs: {log_path(name)}")


def cmd_list(_args: argparse.Namespace) -> None:
    paths = sorted(jobs_dir().glob("*.json"))
    if not paths:
        print("no scheduled jobs")
        return
    for p in paths:
        job = json.loads(p.read_text())
        loaded = "loaded" if is_loaded(job["name"]) else "NOT LOADED"
        print(f"{job['name']:24} repeat={job['repeat']!r:28} target={job['target']:20} [{loaded}]")
        print(f"    prompt: {job['prompt'][:100]}")


def cmd_remove(args: argparse.Namespace) -> None:
    if not job_path(args.name).exists():
        raise SystemExit(f"no such job: {args.name}")
    remove_launchd(args.name)
    job_path(args.name).unlink(missing_ok=True)
    print(f"removed {args.name!r}")


def cmd_run_job(args: argparse.Namespace) -> None:
    herdr_bin = resolve_herdr()
    if not job_path(args.name).exists():
        raise SystemExit(f"no such job: {args.name}")
    job = json.loads(job_path(args.name).read_text())
    execute_once(job, herdr_bin)


def main() -> None:
    parser = argparse.ArgumentParser(prog="herdr_schedule.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sched = sub.add_parser("schedule", help="schedule (or immediately run) a prompt")
    p_sched.add_argument("--repeat", required=True)
    p_sched.add_argument("--target", help="existing herdr agent name/pane; default sched-<name>")
    p_sched.add_argument("--name", help="job name; default derived from the prompt")
    p_sched.add_argument("--cwd", help="cwd for an auto-created target pane; default $HOME")
    p_sched.add_argument("--ntfy-topic", default=os.environ.get("NTFY_TOPIC", DEFAULT_NTFY_TOPIC))
    p_sched.add_argument("--timeout", type=int, default=DEFAULT_RUN_TIMEOUT, help="seconds to wait for a run to settle")
    p_sched.add_argument("--no-ntfy", action="store_true")
    p_sched.add_argument("prompt", nargs="+")
    p_sched.set_defaults(func=cmd_schedule)

    p_list = sub.add_parser("list", help="list scheduled jobs")
    p_list.set_defaults(func=cmd_list)

    p_remove = sub.add_parser("remove", help="unschedule and delete a job")
    p_remove.add_argument("name")
    p_remove.set_defaults(func=cmd_remove)

    p_run = sub.add_parser("run-job", help="run one job immediately (used by launchd, and for manual testing)")
    p_run.add_argument("name")
    p_run.set_defaults(func=cmd_run_job)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
