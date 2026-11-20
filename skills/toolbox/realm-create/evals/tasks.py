"""Inspect tasks for realm-create: the queen skill and the worker brief.

Run from this directory: `inspect eval tasks.py --model openai-api/omniroute/work/main -T ref=<commit>`; without ref the working tree is tested.
"""

from pathlib import Path

from inspect_ai import task

from harness import task as build

HERE = Path(__file__).parent


@task
def realm_create(epochs: int = 3, grader: str | None = None, ref: str | None = None):
    return build("realm-create", HERE / "evals.json", grader, epochs, ref)


@task
def realm_worker_brief(epochs: int = 3, grader: str | None = None, ref: str | None = None):
    return build("realm-create", HERE / "brief-evals.json", grader, epochs, ref)
