"""Bind files: which realm agent each omp session speaks for, read by the `realm-wake` omp extension.

One file per herdr pane, `<state dir>/bind/<pane id>.json`: {agent, project, id, cursor}. The extension in that pane
follows the agent's `fetch_inbox_events` from `cursor` and wakes its session on each delivery; with no file it does
nothing. `cursor` is the delivery tail taken before the session can join, so a subject sent between its connect and
the extension's first poll is still a delivery after it. `id` changes on every bind, so the extension drops a cursor
it saved for an earlier binding of the same pane.
"""

import json
import os
import secrets

from . import state


def bind_dir():
    return state.STATE_DIR / "bind"


def path(pane_id):
    if not pane_id or "/" in pane_id or pane_id.startswith("."):
        raise ValueError(f"not a herdr pane id: {pane_id!r}")
    return bind_dir() / f"{pane_id}.json"


def write(pane_id, agent, project, cursor):
    """Bind pane_id to agent in project, starting after cursor. Atomic: the extension never reads half a file."""
    target = path(pane_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.{os.getpid()}")
    tmp.write_text(json.dumps({"agent": agent, "project": project, "id": secrets.token_hex(8), "cursor": cursor}))
    tmp.replace(target)


def read(pane_id):
    try:
        return json.loads(path(pane_id).read_text())
    except FileNotFoundError:
        return None


def remove(pane_ids):
    """Unbind panes, with the cursor the extension saved beside each binding."""
    for p in pane_ids:
        if p:
            path(p).unlink(missing_ok=True)
            path(p).with_suffix(".cursor").unlink(missing_ok=True)
