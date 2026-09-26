---
name: dispatch-worktree-agents
description: >-
  Turns a list of coding tasks into a dependency-ordered fleet of independent agents: decides
  which tasks depend on which and which run in parallel, writes each agent a researched,
  self-contained prompt, and launches every task as its own omp session in its own herdr git
  worktree — plan mode and a fast model by default — with later tasks starting automatically
  from their dependencies' branches once those finish. Use whenever the user hands over several
  tasks, features or fixes and asks to start agents, one agent per task, a worktree each, run
  them in parallel or in order, fan the work out, or "spin up herdr agents" — even when they
  number the list loosely or never say "dependency".
compatibility: >-
  herdr CLI with a running herdr server, the caller inside a herdr pane; the omp coding agent;
  git; python3. The target repository must be a git repository herdr can create worktrees in.
---

# Dispatch worktree agents

The user gives a list of tasks. You turn it into a small DAG, write one prompt per task, and
launch each task as an **omp** agent in its own **herdr worktree**, in dependency order. The
agents do the work; you design the split and the prompts, and hand the running fleet over.

`$SKILL_DIR` below is notation for this skill's directory (the one holding this `SKILL.md`),
not a variable already set. `scripts/herd.py` does all the mechanical work — worktrees, model
resolution, plan mode, injection, scheduling — so never re-derive it by hand.

## Defaults

| Setting | Default | Override |
|---|---|---|
| Model | `deepseek-v4.1-flash`, resolved to its full catalog selector | `model` in the manifest or per task |
| Thinking | `high` | `thinking` |
| Mode | plan mode: the agent researches, proposes a plan, waits for approval | `"plan": false` |
| Base | the repository's current branch | `base` |

Honour whatever the user says over these ("use GLM", "skip plan mode", "base on develop").

## 1. Decide the order

Read the list and the codebase before deciding — dependencies are facts about the code, not the
wording. Numbering is a hint: the user's "1, then 2 in parallel, then 3" is a direct order;
duplicated numbers ("2. … 2. …") usually mean "these run together".

A task **depends** on another when it edits what the other creates or rewrites, or needs its
data model or API to exist. Two tasks **run in parallel** when they touch disjoint files, or
the same files in separable ways a merge will resolve. When two siblings will certainly touch
the same lines, either order them or tell each one precisely which part is its own — the
prompts below do this.

Look for work already in flight before splitting: `herdr agent list`, `herdr worktree list
--cwd <repo>`, and unmerged branches (`git branch --no-merged <base>`). A live agent or an
open branch rewriting the files a task touches is a dependency or a conflict the user must
hear about — gate the task on it, fence it off in the prompt, or ask.

Split a task that bundles independent work; merge two that cannot be done apart. Keep the
number of simultaneous agents modest (≤ 4 by default): they share the machine, its ports and
its databases.

Show the user the waves in a short table (task, depends on, base branch) together with the
manifest, then launch without waiting for a reply unless something is genuinely theirs to
decide — every agent starts in plan mode, so the user gets a review gate per task anyway.

## 2. Research, then write the prompts

A weaker model in a fresh session reads only its prompt. The prompt is the whole difference
between a plan the user approves and one they rewrite, so spend the effort here: locate the
files, symbols, schemas and existing conventions each task touches, and name them. Read
[references/writing-prompts.md](references/writing-prompts.md) before writing — it has the
section layout, what to include, and the mistakes that cost a relaunch.

Write the run into a directory the user can find again — default
`${XDG_STATE_HOME:-$HOME/.local/state}/dispatch-worktree-agents/<run-name>/`:

```
<run>/herd.json      the manifest
<run>/<id>.md        one prompt body per task (the task itself only)
<run>/context.md     optional: shared, repo-specific rules for every agent
```

`herd.py` appends, per task: the list of sibling agents with their `summary` and whether each
runs before, after or alongside it; the worktree, branch and mode; what a plan must contain; the
shared context; and the done protocol. Don't repeat those in `<id>.md`. Placeholders
`{{TASK_ID}}`, `{{BRANCH}}`, `{{BASE}}`, `{{WORKTREE}}`, `{{SLUG}}` (id as `[a-z0-9_]`, handy
for per-agent database names) and `{{RUN_DIR}}` are filled in the task and context files.

Manifest:

```json
{
  "name": "lists",
  "repo": "/abs/path/to/repo",
  "context": "context.md",
  "tasks": [
    { "id": "tanstack-table", "summary": "migrate list screens to TanStack Table" },
    { "id": "column-reorder", "summary": "drag to reorder columns", "after": ["tanstack-table"] },
    { "id": "column-resize",  "summary": "resizable, shrink-to-fit columns", "after": ["tanstack-table"] },
    { "id": "view-permalinks", "summary": "short permalinks for list views",
      "after": ["column-reorder", "column-resize"] }
  ]
}
```

The task `id` is the branch name and the herdr agent name, so it must match
`[a-z][a-z0-9_-]{0,31}` and not collide with an existing branch (`lists` blocks `lists/x`).
A task's branch is cut from its **first** `after` entry and every other entry is merged in;
set `base` on a task to choose differently.

## 3. Launch

```sh
python3 "$SKILL_DIR/scripts/herd.py" check <run>/herd.json --ping   # validate, show waves, test the model
python3 "$SKILL_DIR/scripts/herd.py" render <run>/herd.json          # optional: <run>/prompts/*.md previews
python3 "$SKILL_DIR/scripts/herd.py" start <run>/herd.json           # scheduler in its own herdr tab
```

`check` fails loudly on a cycle, an unknown dependency, a missing prompt, a branch collision or
a model that does not resolve; `--ping` sends the model one line and refuses to continue if it
cannot answer — a model that does not answer only shows up after the agent boots, as
`Error: No API key found`. Fix and re-run until it passes.

`start` opens a `herd-<name>` tab in the caller's workspace running the scheduler, which
survives this session. Every 20 s it launches each task whose dependencies are all done: it
creates the worktree, merges extra dependencies (a conflict is aborted and handed to the agent
as its first step), starts omp with the resolved model, switches it to plan mode, injects the
prompt and confirms the agent is working. A task that fails to launch gets a `failed/<id>`
marker, a herdr notification, and no retry.

A task is done when its agent runs `touch <run>/done/<id>`, which it is told to do only after
committing. Approving a plan hands execution to a fresh session that carries only the plan, so
the task prompt is gone by then; `herd.py` therefore also pins the done protocol in the agent's
system prompt (`prompts/<id>.system.md`), which survives the handoff and any follow-up request.
The scheduler waits for a clean worktree before building on a task, and keeps running until
every task is done or failed. The user can `touch` a marker by hand to release the next wave
early, and `herd.py launch <manifest> <id> --force` starts one task regardless.

Then confirm with `herd.py status <run>/herd.json` — every wave-1 task should read
`agent working (plan mode)` — before reporting.

## 4. Report

Keep it short: the waves table, where each agent runs (worktree path, herdr workspace), the run
directory, that each agent is waiting for plan approval, and anything the user has to decide.
Name the risks you saw while splitting: siblings likely to conflict, shared ports or databases,
a task whose plan needs a product decision.

## When something goes wrong

- **Agent shows `Error: …` after the prompt** — the launch marks it failed. Fix the cause (usually
  the model), then in its pane exit omp (`herdr agent send-keys <id> ctrl+c ctrl+c`), delete
  `<run>/started/<id>` and `<run>/failed/<id>`, remove the worktree with `herdr worktree remove
  --workspace <ws>` and `git branch -D <id>`, and let the scheduler relaunch it.
- **Worktree create fails** — nearly always a branch-name collision; rename the task id.
- **Nothing launches** — `herd.py status` names what each task waits on; `herd.log` in the run
  directory has every launch step. A task reading `STALLED` has an idle agent, commits on a
  clean branch and no marker — usually finished work the agent never marked (the scheduler
  also notifies). Read its pane; if the work is complete, `touch` the marker it names.
- Never close herdr workspaces or panes this skill did not create, and never kill a process an
  agent started.
