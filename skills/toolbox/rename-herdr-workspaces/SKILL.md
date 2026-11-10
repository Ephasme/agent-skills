# Rename herdr workspaces

**Explicit invocation only.** Applying a plan creates an upstream and deletes the old remote branch;
no single command undoes it. Where `disable-model-invocation` is ignored, this paragraph is the rule.

`$SKILL_DIR` is notation, not a set variable: this skill's directory, the one holding this `SKILL.md`.
Three commands total: survey, plan, apply. Never a fourth.

## 1. Survey

```bash
"$SKILL_DIR/scripts/survey.py"          # --rounds N --workspace ID
```

One pass, read-only, under a second. For every linked-worktree workspace: branch, upstream,
ahead/behind, dirty files, the last 4 commits, and per pane its agent, title, and the last 25 turns
of its conversation (prompts, answers, tool calls — thinking dropped). It writes the same facts to
`herdr-survey.json` and lists the workspaces it skipped — primary checkouts, non-git workspaces — with
the reason: report those as skipped and leave them alone. Without `HERDR_ENV=1` it stops and says so.

Do not re-read panes or PRs afterwards: the brief is the naming material.

## 2. Name

Decide the labels yourself. The scripts never propose one: a name has to come from understanding the
work, and no heuristic reads intent.

- Kebab-case, two to four words, domain terms from the repo: `wallet-replaces-columns`,
  `invoicing-microservice`.
- From the conversation rounds and the recent commits. Not the branch name — for a placeholder that
  is circular — and not the first task, which is usually already done.
- A label that is still accurate stays. `sherpas-api: verify hook` says what the workspace is for:
  changing it would cost the user a hand that already works.
- `"$SKILL_DIR/scripts/labels.py" <label>...` reports every rule a label breaks; nothing generic survives it.

## 3. Apply

One command does the rest — rename, branch move, message to the agent, verification, report. Pass the
plan inline; `--apply` is the only decision left:

```bash
"$SKILL_DIR/scripts/apply.py" '{"wGZ": "nidi-search-trgm"}' --apply
```

Drop `--apply` for a dry run when a workspace's state is uncertain. Workspaces run in parallel; the
script re-reads each branch live and refuses one that moved since the survey.

|Branch state|What happens|
|---|---|
|a chosen name (`deploy`, `feat/x`)|kept|
|`worktree/<label>` exists locally or on origin|kept|
|no upstream at all|`git branch -m worktree/<label>`|
|upstream, a PR exists in any state|kept — the PR is the name on record|
|upstream, no PR, behind `@{u}` after fetch|kept — the local branch is not what is being published|
|upstream, no PR, not behind|`branch -m`, `push -u origin`, `push origin --delete <old>`|

Those guards exist because the branch name is what CI, GitHub and other people resolve, and because
the directory must never move: `git worktree move` would break a running agent and herdr's handle on
the path. Unpushed commits already on the branch stay on it either way.

When the remote branch moved and its agent is running, the pane gets one line — old and new branch,
upstream, commit, the old remote deleted, and the instruction to broadcast it to every subagent
(`write agent://all`) and never push the old name — then the pane is read until the broadcast appears:
`confirmed` or `unconfirmed` per pane. `unconfirmed` is for a human to look at; name it in the report.
`--no-notify` skips the message.

## 4. Report

The table `apply.py` printed, plus its verification block:

|ID|old|new|branch old → new|evidence|

Below it: skipped workspaces with their reason, branches kept and why, panes left `unconfirmed`, and
every failure with its error. Exit 1 means a placeholder label or a duplicate survived.
