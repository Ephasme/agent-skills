"""Inspect task for realm-stop. Run from this directory: `inspect eval tasks.py --model openrouter/deepseek/deepseek-v4.1-flash-1017 -T ref=<commit>`; without ref the working tree is tested."""

import sys
from pathlib import Path

from inspect_ai import task

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parents[1] / "realm-create/evals"))

from harness import task as build  # noqa: E402


@task
def realm_stop(epochs: int = 3, grader: str | None = None, ref: str | None = None):
    return build("realm-stop", HERE / "evals.json", grader, epochs, ref)
