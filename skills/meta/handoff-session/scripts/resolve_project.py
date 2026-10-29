#!/usr/bin/env python3
"""Resolve the absolute path of <project> on <target>.

Uses a local cache (~/.handoff/projects.tsv) so the handoff skill's --move
option doesn't re-search the remote filesystem on every run.

Usage:
    resolve_project.py <target> <project>

Exit codes:
  0   resolved -- the path is printed to stdout. Either a cache hit that
      was verified to still exist on the remote, or the single match found
      by a fresh remote search (which also gets cached).
  1   not found -- <target> is unreachable, or has no directory named
      exactly <project>.
  2   ambiguous -- multiple candidates were found; each is printed to
      stdout, one per line. The caller must ask the user to pick one, then
      cache the choice with record_project.py before continuing.
  64  usage error (bad arguments, or --help) -- distinct from the 0/1/2
      contract above so a caller can't mistake a usage error for a result.
"""
import argparse
import shlex
import subprocess
import sys
from pathlib import Path

import record_project

CACHE_PATH = Path.home() / ".handoff" / "projects.tsv"
SSH_OPTS = ["-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]

# ssh's own reserved exit code for a connection-level failure (as opposed
# to the remote command's exit status, which ssh otherwise passes through
# unchanged -- see ssh(1)).
SSH_CONNECTION_FAILED = 255


def validate_target(target):
    if target.startswith("-"):
        print(f"resolve_project.py: refusing target that looks like an option (starts with '-'): {target!r}", file=sys.stderr)
        return False
    return True


def cached_path(target, project, cache_path=CACHE_PATH):
    if not cache_path.exists():
        return None
    for line in cache_path.read_text().splitlines():
        fields = line.split("\t")
        if len(fields) >= 3 and fields[0] == target and fields[1] == project:
            return fields[2]
    return None


def remote_dir_exists(target, path):
    result = subprocess.run(
        ["ssh", *SSH_OPTS, "--", target, f"test -d {shlex.quote(path)}"],
        capture_output=True,
    )
    return result.returncode == 0


# Path segments that mean "this is not a project checkout". A bare
# `find -name <project>` over $HOME matches package installs, build caches
# and the source package inside the checkout itself -- resolving `minutier`
# on one machine returned five directories, of which one was the project and
# four were a uv tool install, two uv/app caches, and `<checkout>/src/minutier`.
# Asking the user to disambiguate four obvious non-answers is noise, and
# picking one of them unpacks a handoff into a cache directory.
NOISE_SEGMENTS = (
    "/.cache/", "/.local/share/", "/.local/lib/", "/.local/pipx/",
    "/site-packages/", "/dist-packages/", "/node_modules/", "/bower_components/",
    "/.venv/", "/venv/", "/.tox/", "/.nox/", "/__pycache__/",
    "/Library/Caches/", "/Library/Application Support/", "/Library/Containers/",
    "/.npm/", "/.yarn/", "/.pnpm-store/", "/.cargo/registry/", "/.rustup/",
    "/.gradle/", "/.m2/repository/", "/go/pkg/mod/",
    "/.Trash/", "/.git/",
)


def _is_noise(path):
    return any(segment in path + "/" for segment in NOISE_SEGMENTS)


def _nested_in_another(path, others):
    """True when `path` sits inside another candidate -- e.g. the Python
    package at `<checkout>/src/<project>` inside the checkout itself. The
    outer directory is the project; the inner one is part of it."""
    return any(other != path and path.startswith(other.rstrip("/") + "/") for other in others)


def narrow(annotated):
    """Reduce `[(path, is_repo)]` to the candidates worth offering.

    Three passes, each of which is skipped when it would eliminate every
    remaining candidate -- an over-eager filter that reports "not found" for
    a project that IS there is worse than asking the user to choose.
    """
    paths = [path for path, _ in annotated]
    repo = dict(annotated)

    kept = [p for p in paths if not _is_noise(p)] or paths
    kept = [p for p in kept if not _nested_in_another(p, kept)] or kept
    # A directory holding `.git` is a checkout; anything else named the same
    # is at best a copy. Only decisive when some candidate has one.
    return [p for p in kept if repo.get(p)] or kept


def search_remote(target, project):
    """Returns (matches, error). matches is always a list; error is set
    only when ssh itself couldn't reach the target (exit 255) -- any other
    nonzero exit (e.g. `find` hitting a permission-denied subdirectory)
    still yields whatever matches were found on stdout.

    Each match is annotated with whether it holds a `.git` in the SAME
    round trip, rather than one `ssh test -e` per candidate afterwards.
    """
    quoted = shlex.quote(project)
    find_cmd = (
        f'find "$HOME" -maxdepth 6 -type d -name {quoted} '
        f"-not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null | "
        f'while IFS= read -r d; do '
        f'if [ -e "$d/.git" ]; then printf "%s\\tgit\\n" "$d"; '
        f'else printf "%s\\t-\\n" "$d"; fi; done'
    )
    result = subprocess.run(
        ["ssh", *SSH_OPTS, "--", target, find_cmd], capture_output=True, text=True,
    )
    annotated = []
    for line in result.stdout.split("\n"):
        if not line.strip():
            continue
        path, _, flag = line.rpartition("\t")
        # A path containing a literal tab would split wrong; treat the whole
        # line as a path with no marker rather than truncating it.
        annotated.append((path, flag == "git") if path else (line, False))
    if annotated:
        return narrow(annotated), None
    if result.returncode == SSH_CONNECTION_FAILED:
        detail = result.stderr.strip()
        return [], f"resolve_project.py: couldn't reach {target}" + (f": {detail}" if detail else "")
    return [], None


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target")
    parser.add_argument("project")
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 64

    if not validate_target(args.target):
        return 1

    path = cached_path(args.target, args.project)
    if path and remote_dir_exists(args.target, path):
        print(path)
        return 0

    matches, error = search_remote(args.target, args.project)
    if error:
        print(error, file=sys.stderr)
        return 1

    if len(matches) == 0:
        print(
            f"resolve_project.py: no directory named '{args.project}' "
            f"found on {args.target}",
            file=sys.stderr,
        )
        return 1
    if len(matches) == 1:
        try:
            record_project.upsert(args.target, args.project, matches[0])
        except Exception as e:
            print(f"resolve_project.py: warning: couldn't cache result: {e}", file=sys.stderr)
        print(matches[0])
        return 0

    for m in matches:
        print(m)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
