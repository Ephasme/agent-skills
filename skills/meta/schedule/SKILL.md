---
name: schedule
description: >-
  Use when a user wants a prompt sent to an agent on a recurring schedule or once at
  a later time — phrasings like "run this every hour", "check on this every 30
  minutes", "every weekday between 7 and 10pm", "remind the agent to X daily", or any
  request to schedule, automate, or repeat a prompt with a cron expression, a
  plain-English schedule, or a fixed interval (seconds/minutes/hours/days), optionally
  pushing a status notification when each run finishes.
compatibility: >-
  macOS with launchd (StartInterval/StartCalendarInterval); herdr CLI and a running
  herdr server, driven via its `agent`/`workspace` socket-API subcommands; Python 3
  with the `croniter` package (auto-installed on first cron-mode use); optional ntfy
  or ntfy-compatible server with a bearer token for status pushes.
disable-model-invocation: true
---

# schedule

**Explicit invocation only.** This creates a persistent, unattended background job
that repeatedly consumes an agent's quota and pushes notifications — never set one up
because scheduling came up in conversation, only because the user asked for it. Some
agents honour the `disable-model-invocation` key above; where that's ignored, this
paragraph is the rule.

Drives `$SKILL_DIR/scripts/schedule.py` (`$SKILL_DIR` is notation for this
skill's own directory — resolve it from wherever the skill was loaded from). Stdlib
Python plus `croniter`, installed on demand the same way the payment-qr skill
bootstraps `segno`: already-importable → `pip install` across the PEP 668 variants →
a disposable venv as a last resort. Only the `schedule` subcommand ever needs it —
a scheduled firing (`run-job`) never parses cron, so once installed a job has no
further dependency to lose.

## The four `--repeat` forms

| Value | Meaning | launchd mechanism |
|---|---|---|
| `no` | one-time: run immediately, no job is created | none |
| `90s`, `30m`, `1h`, `2d` | fixed interval, clock-unaligned | `StartInterval` |
| `"0 7-22 * * 1-5"` | standard 5-field cron (minute hour dom month dow) | `StartCalendarInterval` |
| anything else | plain English | **translate it to a cron expression yourself first** — the script has no NLU and rejects it with a clear error |

Plain English is the agent's job, not the script's: read what the user asked for
("every hour from 7am to 10pm on weekdays") and hand the script the cron form
(`"0 7-22 * * 1-5"`). Ask the user to confirm the translated expression before
scheduling if the phrasing was ambiguous (e.g. "every couple of hours").

launchd has no wildcard/range in `StartCalendarInterval` — every field combination is
enumerated into its own dict. The script does that expansion and caps it at 500
combinations; a cron expression needing more (or leaving `Minute` as `*`, i.e. "every
minute") is rejected with a pointer to use a duration repeat instead, which is what
that pattern actually means.

## Procedure

1. **Get the exact prompt text and the repeat spec from the user.** Don't guess
   either — a wrong prompt or a mistranslated schedule runs unattended for hours.
2. **Confirm ntfy is configured**: `NTFY_URL` and `NTFY_TOKEN` must be in the
   environment (a bearer-token-auth ntfy or ntfy-compatible server). Without them the
   script refuses to schedule unless `--no-ntfy` is passed explicitly — status
   notifications are the point of this skill, so missing credentials fail loudly
   rather than silently scheduling a job nobody gets told about.
3. **Run it**:
   ```bash
   python3 $SKILL_DIR/scripts/schedule.py schedule \
     --repeat="0 7-22 * * 1-5" \
     "Check the inbox for anything urgent and summarize"
   ```
   Omit `--name`/`--target` and the script derives a job name from the prompt and
   creates a **dedicated herdr pane** for it (`sched-<name>`) — new work never lands
   in a pane the user is actively using. Pass `--target <existing-agent-name>` only
   if the user explicitly wants to reuse a specific pane; two jobs sharing one target
   will contend for it.
4. **Report back** the job name, the resolved schedule, and the log path the script
   prints — don't just say "scheduled it".
5. To test a job without waiting for its real trigger:
   `python3 $SKILL_DIR/scripts/schedule.py run-job <name>`.

## Other subcommands

- `list` — every scheduled job, its repeat spec, target, and whether launchd still
  has it loaded.
- `remove <name>` — unloads the launchd job and deletes its state. It does **not**
  close the target pane (it may be shared, or the user may still want it) — close it
  separately with `herdr workspace close <id>` if it should go too.

## How a run is judged (for reading logs / explaining outcomes)

Each firing submits the prompt (`herdr agent prompt`, no `--wait` — see below), then
polls `herdr agent get` every 3s until the agent's `state_change_seq` moves and its
status lands on `idle`/`done`/`blocked`, or the job's `--timeout` (default 900s)
elapses. Outcome maps to ntfy priority: `idle`/`done` → default, `blocked` → high,
`timeout`/`error` → urgent. The notification body includes the last ~40 lines of the
pane, trimmed to 800 characters.

**Why not `herdr agent prompt --wait`:** verified live — `--wait` can report
`agent_prompt_stalled` even on a run that fully succeeds, when the state transition
completes faster than its post-submission observation window. The script submits
fire-and-forget and polls itself instead, which doesn't have that race.

## State and credentials

Job definitions: `${XDG_CONFIG_HOME:-$HOME/.config}/schedule/jobs/<name>.json`.
Logs: `.../schedule/logs/<name>.log`. launchd plists:
`~/Library/LaunchAgents/com.agent-skills.schedule.<name>.plist`. Both the
job file and the plist embed `NTFY_TOKEN` (so a scheduled firing needs no ambient
shell environment) and are written `0600`.

`NTFY_URL`/`NTFY_TOKEN` are read from the environment at `schedule` time — export
them from wherever this machine keeps credentials (never hard-code a token in a
prompt, a job name, or anything that ends up in this repo).

## Known gotcha: Cloudflare-fronted ntfy origins

A Cloudflare-fronted ntfy server can 403 (`error code: 1010`, a bot-detection rule)
on Python's default `Python-urllib/x.y` User-Agent even with a fully valid bearer
token — confirmed live: identical request succeeds with `curl` and fails with bare
`urllib`. The script already sends a generic `User-Agent` to avoid this; if ntfy
delivery still 403s, check for other edge rules in front of that origin before
suspecting the token.
