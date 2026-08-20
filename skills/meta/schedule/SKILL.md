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
  macOS with launchd (StartInterval/StartCalendarInterval); the `cronward` CLI
  (github.com/Ephasme/cronward, installed via `uv tool install`); herdr CLI and a
  running herdr server; optional ntfy or ntfy-compatible server with a bearer token
  for status pushes.
disable-model-invocation: true
---

# schedule

**Explicit invocation only.** This creates a persistent, unattended background job
that repeatedly consumes an agent's quota and pushes notifications — never set one up
because scheduling came up in conversation, only because the user asked for it. Some
agents honour the `disable-model-invocation` key above; where that's ignored, this
paragraph is the rule.

Drives the standalone `cronward` CLI — [github.com/Ephasme/cronward](https://github.com/Ephasme/cronward)
— not a script bundled in this skill. Confirm it's on `PATH` before use; install it
once if missing:

```bash
command -v cronward >/dev/null || uv tool install git+https://github.com/Ephasme/cronward.git
```

`cronward`'s own README is the source of truth for its mechanism (`--repeat`
grammar in full, `--until` self-stop, herdr session isolation, ntfy wiring, known
gotchas) — this file covers only what an agent needs to drive it correctly.

## The four `--repeat` forms

| Value | Meaning | launchd mechanism |
|---|---|---|
| `no` | one-time: run immediately, no job is created | none |
| `90s`, `30m`, `1h`, `2d` | fixed interval, clock-unaligned | `StartInterval` |
| `"0 7-22 * * 1-5"` | standard 5-field cron (minute hour dom month dow) | `StartCalendarInterval` |
| anything else | plain English | **translate it to a cron expression yourself first** — `cronward` has no NLU and rejects it with a clear error |

Plain English is the agent's job, not `cronward`'s: read what the user asked for
("every hour from 7am to 10pm on weekdays") and hand `cronward` the cron form
(`"0 7-22 * * 1-5"`). Ask the user to confirm the translated expression before
scheduling if the phrasing was ambiguous (e.g. "every couple of hours").

## Procedure

1. **Get the exact prompt text and the repeat spec from the user.** Don't guess
   either — a wrong prompt or a mistranslated schedule runs unattended for hours.
2. **Confirm `cronward` is installed** (see above).
3. **Confirm ntfy is configured**: `NTFY_URL` and `NTFY_TOKEN` must be in the
   environment (a bearer-token-auth ntfy or ntfy-compatible server). Without them
   `cronward` refuses to schedule unless `--no-ntfy` is passed explicitly — status
   notifications are the point of this skill, so missing credentials fail loudly
   rather than silently scheduling a job nobody gets told about.
4. **Pick the ntfy topic**: `--ntfy-topic TOPIC` sets which topic the job's status
   pushes go to. Nothing prompts for it, and a `NTFY_URL` with no path is normal, so
   don't just assume the default is fine for a job the user cares about being
   notified on — ask if they want a specific topic (e.g. to route this job to a
   phone/channel already subscribed to something other than the default). Precedence:
   `--ntfy-topic` flag > `$NTFY_TOPIC` env var > `"sched"`. The topic is per-job
   (stored in that job's own definition), so different jobs can push to different
   topics — name the resolved one when reporting back, or a job quietly publishing to
   `sched` is otherwise invisible.
5. **Run it**:
   ```bash
   cronward schedule \
     --repeat="0 7-22 * * 1-5" \
     --ntfy-topic="my-custom-topic" \
     "Check the inbox for anything urgent and summarize"
   ```
   Omit `--name`/`--target` and `cronward` derives a job name from the prompt and
   creates a **dedicated herdr pane** for it (`cronward-<name>`) in an isolated
   `cronward` herdr session — see "Herdr session isolation" below; new work never
   lands in a pane the user is actively using. Pass `--target <existing-agent-name>`
   only if the user explicitly wants to reuse a specific pane (also resolved inside
   the `cronward` session); two jobs sharing one target will contend for it.

   **Never pass `--cwd` to aim a job at a checkout the user is already working in.**
   `cronward` refuses this at schedule time (a pane there would adopt that checkout's
   live agent session instead of a fresh one) — put absolute paths in the prompt
   instead; a monitoring job needs no cwd at all.
6. **Report back** the job name, the resolved schedule, the ntfy topic, and the log
   path `cronward` prints — don't just say "scheduled it".
7. **Test-fire it once before telling the user it's set up**: `cronward run-job
   <name>`. That's the only thing proving the pane, the prompt, and ntfy delivery
   all work together, and it prints `ntfy: <status>` — a `200` is the receipt. Two
   expected surprises: the `logs:` path `schedule` printed stays **absent or empty**
   until a real launchd firing, because it's the plist's `StandardOutPath`/
   `StandardErrorPath` and a manual `run-job` prints to your console instead; and the
   first firing right after a fresh pane's creation can retry once or twice
   internally (`cronward` handles this, see its README) before the prompt lands.
8. **Read back what the firing replied**: `herdr --session cronward agent read
   cronward-<name> --lines 40 --format text` — the same snippet the notification
   carries. Worth doing once per new job, to confirm the reply has the shape asked
   for instead of a wall of prose that will be useless on a phone.

## Other subcommands

- `cronward list` — every scheduled job by id (its `name`), repeat spec, target,
  ntfy topic, `until` condition (if any), and whether launchd still has it loaded.
- `cronward kill <id>` — unschedules and deletes a job by the id `list` shows. Does
  **not** close the target pane (it may be shared, or the user may still want it) —
  close it separately with `herdr --session cronward workspace close <id>` if it
  should go too (the target lives in the `cronward` herdr session, not `default`).

## Herdr session isolation

Every scheduled-job herdr call runs against a dedicated named herdr session,
`cronward` (`herdr --session cronward ...`), never the user's interactive `default`
session — a job's target pane never shows up in the sidebar the user is actively
looking at. `cronward` starts that session's headless server lazily on first use and
leaves it running afterward; a crash or reboot is self-healed on the next firing.
Full detail: `cronward`'s README, "Herdr session isolation".

To inspect or clean up scheduled-job panes directly, target that session
explicitly: `herdr --session cronward workspace list`,
`herdr --session cronward workspace close <id>`. They will not appear in plain
`herdr workspace list` (that's the `default` session).

## Stopping automatically (`--until`)

`--until "<plain-English condition>"` on `schedule` turns a recurring job into one
that stops itself once the condition holds — e.g. `--until "the venue has replied"`
or `--until "the invoice has been paid"`. Only valid alongside a real `--repeat`
(not `--repeat=no`, which has nothing to stop).

Mechanism: every firing's prompt gets the condition appended, with instructions to
end the reply with a literal `SCHEDULE_DONE: <brief reason>` line if, and only if,
the condition is now true. `cronward` — not the model — greps the run's terminal
output for that exact line after a run settles as `idle`/`done`; when found, it
kills the job itself, same effect as `kill <id>`, done automatically. A `blocked`,
`timeout`, or `error` run is never treated as a stop signal, even with `--until`
set, since the model didn't get a clean chance to judge the condition.

Report the `until` condition back to the user when scheduling one, same as the
repeat spec — it's a second thing that could be silently wrong.

## State, credentials, and troubleshooting

Job definitions and logs live under `${XDG_CONFIG_HOME:-$HOME/.config}/cronward/`;
launchd plists under `~/Library/LaunchAgents/com.cronward.<name>.plist`. `NTFY_URL`/
`NTFY_TOKEN` are read from the environment at `schedule` time and embedded into the
job/plist (mode `0600`) — export them from wherever this machine keeps credentials,
never hard-code a token in a prompt or job name. Full paths, the run-judging
mechanism (why not `herdr agent prompt --wait`), and a known Cloudflare-fronted-ntfy
403 gotcha are documented in `cronward`'s README — read it if a run behaves
unexpectedly rather than re-deriving the mechanism from first principles.
