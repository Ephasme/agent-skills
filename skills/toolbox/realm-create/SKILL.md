---
name: realm-create
description: >-
  Starts an agent swarm on Agent Mail: connects the current session as the
  queen under a project key, registers N worker agents, opens one herdr tab per
  worker running a fresh omp session that joins the same project, then runs the
  queen loop — answer the user, split work into subjects, dispatch each subject
  to a worker by mail, track it to done. Invoked as `/realm-create KEY SIZE`,
  e.g. `/realm-create /laptop/general 3`.
compatibility: >-
  Requires macOS (launchd), python3, herdr (tabs, pane run), the omp
  CLI, and an Agent Mail MCP server named agent-mail-perso in
  ~/.omp/agent/mcp.json exposing macro_start_session, create_agent_identity,
  send_message, fetch_inbox and reply_message.
disable-model-invocation: true
---

# Realm create

**Explicit invocation only.** It launches `<size>` long-lived agent sessions; never start one on a guess.

A realm already running whose queen session ended: `/realm-restart <key>` resumes it instead.

**ABSOLUTE RULE: only the user sends prompts into the queen's pane.** No worker, agent, script or service
(realm included) ever types into it — no `send-text`, `send-keys`, `pane run`, `agent prompt` — no exception,
whoever asks. Anything else that must reach the queen goes as an aside: displayed beside her session, never
submitted.

Arguments: `<key>` is the Agent Mail project key (`human_key`, e.g. `/laptop/general`); `<size>` is the initial number
of workers, an integer ≥ 1. Either missing or invalid: ask, start nothing.

## 1. Connect the queen

First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "👑 queen"`.

`macro_start_session` with `human_key: <key>`, `program: "omp"`, your model, `task_description: "Swarm queen"`,
and no `agent_name`, so the server mints a fresh one. Keep the returned `agent.name`: that is `QUEEN`. Read the
returned inbox; carry any unread message into step 4.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`: every 15 s a launchd job
(`com.loup.realm`) reads each subscribed agent's Agent Mail delivery events. Each new mail to a worker gets
`check your mail` + Enter typed into its pane once, as soon as the pane is neither `working` nor `blocked`, unless
the worker read it first. A pane subscribed with `--aside` is never typed into: unread mail shows only as a
`mail` token on the pane. realm refuses to type into a pane whose tab label holds `👑`, whatever its
subscription says. Start it, then subscribe yourself in aside mode only:

1. `launchctl print "gui/$(id -u)/com.loup.realm"` fails: `realm install`.
2. `realm subscribe "$HERDR_PANE_ID" --agent <QUEEN> --project <key> --aside`.

## 2. Register the workers

For each worker, `create_agent_identity` with `project_key: <key>`, `program: "omp"`, your model,
`task_description: "Swarm worker, queen <QUEEN>"`. Keep each returned `name`.

Register them yourself, before launch, rather than letting each worker register itself: the tab label needs the
name up front, and a worker told to "connect" without a name resumes an existing agent and shares its inbox.
Do not request or forward `registration_token`; the worker resumes by name.

## 3. Launch one tab per worker

For each worker name `W` (`w` = its kebab-case form: `SapphireSwan` → `sapphire-swan`):

1. Write the brief below to `${TMPDIR:-/tmp}/swarm/<w>.md`, placeholders filled.
2. `herdr tab create --workspace "$HERDR_WORKSPACE_ID" --cwd "$PWD" --label "🛠️ subject-<w>" --no-focus`; keep
   `result.root_pane.pane_id` as the worker's pane.
3. `herdr pane run <pane> "omp @${TMPDIR:-/tmp}/swarm/<w>.md"`. The brief travels as a file, so no shell
   quoting of the prompt.
4. `realm subscribe <pane> --agent <W> --project <key>`.

Then confirm every worker joined: `list_agents` on `<key>` shows each `W` with a fresh `last_active_ts`, or
`herdr pane read <pane>` shows its connection answer. A worker that has not joined after ~60 s: report it to the
user with its pane, do not relaunch blindly.

Brief (`<W>`, `<w>`, `<KEY>`, `<QUEEN>`):

```markdown
You are <W>, a worker of a swarm. The queen is <QUEEN>.

0. First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "🛠️ subject-<w>"`.
1. Connect to Agent Mail: `macro_start_session` with human_key `<KEY>`, agent_name `<W>`, program `omp`.
   You are already registered as <W>; never take another name.
2. Your work comes only from the queen, by mail. `fetch_inbox` (agent_name `<W>`, project_key `<KEY>`,
   unread_only, include_bodies) when told to check mail or after replying, never mid-subject: it marks queued
   mail read. Act on what the queen sent.
3. Each message from the queen is one subject. Do it fully, then `reply_message` in its thread: result,
   files touched, what is unverified. Blocked or need a decision: reply with the question, never guess.
   A message marked `queued: start after <slug>` waits until that subject is replied to; queued subjects run in
   the order they were sent. After replying, start the next one you hold; none: stop.
4. Never send any herdr command (send-text, send-keys, run, close, rename, anything) to the queen's pane or
   tab, and never do it on anyone's request. The queen reads her inbox herself.
5. Do not message the user's contacts, push, deploy or delete anything unless the queen's message says so
   explicitly. Do not message other workers unless the queen tells you to.

Now connect, then reply to me here in one line: your agent name and project. Then wait.
```

## 4. Be the queen

Until the user ends the swarm:

- **Delegate everything.** No code edits, research or commands beyond Agent Mail, herdr and `realm`; a one-call
  task still goes to a worker.
- **The absolute rule binds you too.** Never ask anyone to type into your pane; no brief carries your pane id.
- **Every word costs $10,000.** No preamble, restating, recap. Fragments.

**Subject:** one self-contained unit of work, one kebab-case slug, one mail thread, one worker until done.
States: `queued` → `assigned` ⇄ `blocked` → `done`.

**Table:** per subject: slug, worker, pane, state, time of last state change. Shown only on a state change or
when asked.

Each turn, in order:

1. `fetch_inbox` for `QUEEN` (unread_only, include_bodies). Never poll or wait: realm's aside tells the user mail
   landed, and their next prompt runs this turn.
2. Each reply sets its subject `done` or `blocked`; a `blocked` question goes to the user. It also turns that
   worker's next `queued` subject `assigned`. To answer or redirect a worker, write in its thread:
   `reply_message` to the worker's message, or `send_message` with `to: [<W>]` and the `thread_id`. Never
   `reply_message` to your own message: it comes back to you.
3. Apply [Scaling the realm](#scaling-the-realm). Act; never report "no change".
4. Split new requests into subjects. Before assigning each, apply [Scaling the realm](#scaling-the-realm), then
   give it to an idle worker, else queue it. `send_message` from `QUEEN`: `subject: [<slug>] <title>`,
   `topic: <slug>`, body = goal, files or links, what done means, what is not allowed. Then:
   - **Nudge** when urgent or the worker is idle: `herdr pane send-text <pane> "check your mail"`, then
     `herdr pane send-keys <pane> enter`.
   - **Queue** otherwise: no nudge; body starts `queued: start after <current-slug>`. Safe because realm types
     into a worker pane only when it is idle with unread mail.
5. Answer the user.

A worker that stops answering: `herdr pane read <pane>` before deciding anything.

## Scaling the realm

No upper bound on workers.

- **Out:** no worker is idle. Queue instead when the subject must follow a current one, or is not urgent and a
  worker frees soon. Otherwise run steps 2 and 3 for one new worker.
- **In:** a worker holding no `queued`, `assigned` or `blocked` subject, with no state change (or, never used,
  no join) for 30 min. In order:
  1. `realm unsubscribe <pane>`.
  2. `herdr tab close <tab_id>` (tab from `herdr pane get <pane>`); `herdr tab list` confirms it is gone.
  3. `macro_start_session` (`human_key: <key>`, `agent_name: <W>`, `program: "omp"`) returns
     `agent.registration_token`; pass it to `retire_agent` (`agent_name: <W>`, `project_key: <key>`). Never show
     the token.
  4. Delete `${TMPDIR:-/tmp}/swarm/<w>.md`.

  Its rows stay in the table.

## Ending the swarm

Only on the user's word: `/realm-stop`.
