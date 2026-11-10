---
name: rename-herdr-workspaces
description: >-
  Gives every herdr worktree workspace a label that says what the work in it is
  about, then lines the branch up with it. Use when the user asks to rename,
  relabel or retitle herdr workspaces, complains that labels are unreadable
  placeholders like "worktree-lucky-valley-75fc", or wants the sidebar to show
  what each agent is actually doing, e.g. "rename my workspaces so I can tell
  them apart", "name the worktrees after their task", or in French "renomme les
  workspaces", "donne un nom lisible à chaque worktree". Reads the recent
  commits, the dirty files and the agent's own session title and TODO, names
  each workspace from that, and moves the branch too when no PR and no remote
  ref stand in the way. Explicit invocation only: applying a plan can push and
  delete a remote branch.
compatibility: Requires herdr (terminal workspace manager) with HERDR_ENV=1, git, gh, Python 3.9+.
disable-model-invocation: true
---

# Rename herdr workspaces

**Explicit invocation only.** Applying a plan creates an upstream and deletes the old remote branch;
no single command undoes it. Where `disable-model-invocation` is ignored, this paragraph is the rule.

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this `SKILL.md`.

## 1. Survey

```bash
"$SKILL_DIR/scripts/survey.py"
```

One pass, read-only. For every linked-worktree workspace it prints the branch, upstream, ahead/behind,
dirty count, the last 8 commits, and per pane: the agent, its session title, its current TODO, the
lines it marked and its last lines. It writes the same facts to `herdr-survey.json`, and lists the
workspaces it skipped — primary checkouts, non-git workspaces — with the reason: report those as
skipped and leave them alone. Without `HERDR_ENV=1` it stops and says so; stop with it.

## 2. Name

Decide the labels yourself. The scripts never propose one: a name has to come from understanding the
work, and no heuristic reads intent.

- Kebab-case, two to four words, domain terms from the repo: `wallet-replaces-columns`,
  `invoicing-microservice`.
- From the recent commits and the agent's current task. Not the branch name — for a placeholder that
  is circular — and not the first task, which is usually already done.
- A label that is still accurate stays. `sherpas-api: verify hook` says what the workspace is for:
  changing it would cost the user a hand that already works.
- `scripts/labels.py <label>...` reports every rule a label breaks; nothing generic survives it.

Write the plan as workspace id to label, then apply:

```json
{"wGZ": "nidi-search-trgm"}
```

## 3. Apply

```bash
"$SKILL_DIR/scripts/apply.py plan.json            # dry run: every decision, nothing changed
"$SKILL_DIR/scripts/apply.py plan.json --apply
```

The script renames the workspace, then weighs the branch:

| Branch state | What happens |
|---|---|
| a chosen name (`deploy`, `feat/x`) | kept |
| `worktree/<label>` exists locally or on origin | kept |
| no upstream at all | `git branch -m worktree/<label>` |
| upstream, a PR exists in any state | kept — the PR is the name on record |
| upstream, no PR, behind `@{u}` after fetch | kept — the local branch is not what is being published |
| upstream, no PR, not behind | `branch -m`, `push -u origin`, `push origin --delete <old>` |

Those guards exist because the branch name is what CI, GitHub and other people resolve, and because
the directory must never move: `git worktree move` would break a running agent and herdr's handle on
the path. Unpushed commits already on the branch stay on it either way.

Read the dry-run table before `--apply`. `--no-notify` skips step 4.

## 4. Tell the agent

Automatic. When the remote branch moved and its agent is running, `apply.py` sends the pane one line —
old and new branch, upstream, commit, the old remote deleted, and the instruction to broadcast it to
every subagent (`write agent://all`) and never push the old name — presses Enter, then reads the pane
until the broadcast appears, reporting `confirmed` or `unconfirmed` per pane. An `unconfirmed` pane is
one a human has to look at: name it in the report. Send nothing else; an agent mid-task does not want
company.

## 5. Verify and report

```bash
"$SKILL_DIR/scripts/verify.py"
```

Exits 1 on a remaining placeholder label or a duplicate. Then report `apply.py`'s table:

| ID | old | new | branch old → new | evidence |

Below it: skipped workspaces with their reason, branches kept and why, panes left `unconfirmed`, and
every failure with its error.
