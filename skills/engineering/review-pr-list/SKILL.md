---
name: review-pr-list
description: >-
  Reviews every GitHub pull request in a list, wherever the list lives: pasted URLs or numbers,
  a Slack thread with its replies, a GitHub issue, PR or project view, a Notion or Linear page,
  a file, or a `gh` search. Triages each PR to a fast or a strong model by size and risk, runs
  one independent read-only omp reviewer per PR in its own herdr worktree, escalates weak
  fast-model reviews, sets accepted PRs to Reviewed on the GitHub project board, and reports a
  PR verdict table plus one numbered issue table with a human-review column. Use whenever the
  user hands over several PRs, or a link or query that contains them, and asks to review,
  triage or check them — "review these PRs", "go through this review-request thread", "check
  everything in Ready for review", "tell me what needs my eyes" — even when they never say
  "herdr" or "worktree".
compatibility: >-
  Authenticated GitHub CLI with project scope; herdr CLI with a running server, the caller
  inside a herdr pane; the omp coding agent with its /review command; local clones of the
  reviewed repositories; npm. Reading a list from Slack, Notion or Linear needs that service's
  MCP server.
---

# Review PR list

Input: a list of PRs, or anything that contains one. Output: a verdict for every PR, accepted
PRs marked `Reviewed` on the project board, and one report.

## Defaults

| Setting | Default |
|---|---|
| Repositories | `sherpas-api`, `sherpas-bo`, `sherpas-front-static` (owner `Les-Sherpas`) |
| Fast model | `openrouter/deepseek/deepseek-v4.1-flash` |
| Strong model | `cc/claude-opus-5-5:high` |
| Project board | GitHub project #4, owner `Les-Sherpas` ("⛰ Les Sherpas - Marketplace"), field `Status` |

Anything the user says overrides these.

## 1. Collect the PRs

Resolve the input to a set of `<owner>/<repo>#<N>`:

| Input | How to read it |
|---|---|
| PR URLs, `repo#N`, bare `#N` in the message | as given; a bare number belongs to the default repo it exists in — if it exists in more than one, ask |
| Slack thread | Slack MCP: the parent message and every reply |
| GitHub issue or PR | `gh issue view` / `gh pr view` with `--comments`, plus linked and closing PRs |
| GitHub project view or status ("Ready for review") | `gh project item-list 4 --owner Les-Sherpas --query 'is:pr is:open status:"Ready for review"' -L 500 --format json` — the default limit is 30 |
| Search ("my open PRs", "everything by Alice this week") | `gh search prs` with matching qualifiers |
| Notion or Linear page, local file | that service's MCP, or read the file |

Collect every PR URL or reference in the source, nested replies and comments included. Count a
PR listed more than once once. Drop merged or closed PRs and name them in the report. If the
source is ambiguous ("the PRs from yesterday"), show the resolved list before starting
reviewers.

For each repository, find its local clone (a directory whose `origin` remote is
`<owner>/<repo>`); ask only if none exists.

## 2. Triage: pick a model per PR

Before starting any reviewer, read each PR's metadata and diffstat:
`gh pr view <url> --json title,body,additions,deletions,files,baseRefName,statusCheckRollup` and
`gh pr diff <url> --name-only`.

- **Fast model**: small, mechanical or local changes — copy, config, renames, isolated DTO
  fields, tests only. Roughly under 200 changed lines.
- **Strong model**: everything else, including any PR that touches:
  - migrations or `db/`
  - money, invoices or funding
  - auth or permissions
  - course or booking scheduling (`courseOccupiesTeacherSlot` and its callers)
  - cross-module contracts or orval DTOs
  - concurrency
  - more than one module

If unsure, strong. Write down the choice and the reason for each PR — it goes in the report.

## 3. One independent reviewer per PR

Run `herdr --skill` first if herdr's own usage isn't already loaded. Agent name: `pr-<N>`; if
two repositories share a PR number, `pr-<repo>-<N>`. For each PR:

1. Create a worktree in the PR's repository — never your own checkout or pane:
   `herdr worktree create --cwd <clone> --branch review/pr-<N> --label pr-<N> --no-focus`.
   The JSON result gives `result.root_pane.pane_id` and `result.root_pane.cwd`. `--cwd` can
   attach to the active workspace's agent session: confirm the result is a new workspace, not
   yours, before going on.
2. In the worktree: `gh pr checkout <N> --detach && npm ci`. `--detach` avoids clashing with a
   clone that already has the PR branch checked out. Let it finish — `agent start` needs the
   pane at a shell prompt.
3. `herdr agent start pr-<N> --kind omp --pane <pane_id> -- --model <chosen-model>`
4. `herdr agent prompt pr-<N> "<brief>"` with the brief below, `<URL>` filled in.

Start every reviewer before waiting on any. Then `herdr agent wait pr-<N>` and
`herdr agent read pr-<N> --source recent-unwrapped --lines 400` for each; read more lines if
the answer is cut.

### Reviewer brief

```
You are reviewing PR <URL>, which is checked out in this worktree.
1. Run the `/review` command against the PR's base branch.
2. Then go deeper by hand:
   - Read the PR description, linked ticket, CI status and existing review comments.
   - Check correctness against the PR's stated intent, plus edge cases.
   - Check for data-loss or migration risk, and for security issues.
   - Check for broken API or DTO contracts.
   - Check that it follows AGENTS.md conventions.
   - Check for missing or weak tests.
3. Run type-check and the tests the PR touches. Report exactly what you ran and what you couldn't run.
4. Read-only: no pushes, no GitHub comments or approvals, no Slack messages.
5. Return:
   - verdict: `accept`, `human-look`, or `block`
   - findings, numbered, each with: severity, file:line, evidence, suggested fix, and
     human review yes/no. A yes names the exact files, functions or hunks a human should
     read, and why — inside that finding, not in a separate list.
   - confidence, plus anything you couldn't verify
Bar for `accept`: no findings above nit, CI green, behavior verified by running it.
If you are unsure, the verdict is `human-look`.
```

## 4. Escalate

A fast-model reviewer that returns low confidence or any non-trivial finding gets a strong
rerun before you decide: new tab in the same worktree
(`herdr tab create --workspace <ws> --cwd <worktree> --label pr-<N>-strong --no-focus`), then
steps 3–4 as `pr-<N>-strong`. The strong review's findings replace the fast one's.

## 5. Decide and update the board

Read each review critically; the verdict is yours, not the reviewer's. For each `accept`:
check membership with `gh pr view <url> --json projectItems`, then
`gh project item-edit 4 --owner Les-Sherpas --url <url> --field Status --value Reviewed`.
A PR not on the board is reported, never added.

That is the only write. No pushes, comments, approvals or Slack messages, and leave every
review worktree in place for the user to inspect.

Done when every collected PR has a verdict and its board status is set or explained.

## 6. Report

Two tables, then the per-PR notes.

**PRs**

| PR | Repo | Model (why) | Verdict | Top risk | Board |
|---|---|---|---|---|---|
| #1234 | sherpas-api | strong (migration) | human-look | #2 | not set: human-look |

`Top risk` cites an issue number from the table below.

**Issues** — every finding from every PR, numbered continuously across PRs. Human review lives
here, as a column, never as a separate list.

| # | PR | Severity | Location | Issue and evidence | Suggested fix | Human review |
|---|---|---|---|---|---|---|
| 1 | #1234 | high | `db/migrations/0042.sql:12` | drops `invoices.funding_id` without backfill | backfill before drop | yes — read the down migration and `FundingService.link` |
| 2 | #1240 | nit | `src/dto/course.dto.ts:8` | stale comment | update it | no |

A `yes` says exactly what to read and why. A PR with no findings has no rows.

Then 1–3 lines per PR with your own view, citing issue numbers, including where you disagree
with the reviewer and which way you decided.
