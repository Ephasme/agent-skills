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
  Requires macOS (launchd), python3, herdr (tabs, pane run/send-text), the omp
  CLI, and an Agent Mail MCP server named agent-mail-perso in
  ~/.omp/agent/mcp.json exposing macro_start_session, create_agent_identity,
  send_message, fetch_inbox and reply_message.
disable-model-invocation: true
---

# Realm create

**Explicit invocation only.** It launches `<size>` long-lived agent sessions; never start one on a guess.

**ABSOLUTE RULE: only the user sends prompts into the queen's pane.** No worker, agent, script or service
(realm included) ever types into it — no `send-text`, `send-keys`, `pane run`, `agent prompt` — no exception,
whoever asks. Anything else that must reach the queen goes as an aside: displayed beside her session, never
submitted.

Arguments: `<key>` is the Agent Mail project key (`human_key`, e.g. `/laptop/general`); `<size>` is the number
of workers, an integer ≥ 1. Either missing or invalid: ask, start nothing.

## 1. Connect the queen

First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "👑 queen"`.

`macro_start_session` with `human_key: <key>`, `program: "omp"`, your model, `task_description: "Swarm queen"`,
and no `agent_name`, so the server mints a fresh one. Keep the returned `agent.name`: that is `QUEEN`. Read the
returned inbox; carry any unread message into step 4.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`: every 15 s a launchd job
(`com.loup.realm`) checks each subscribed pane's Agent Mail inbox. A worker pane with unread mail that is
neither `working` nor `blocked` gets `check your mail` + Enter typed into it. A pane subscribed with `--aside`
is never typed into: unread mail shows as a `mail` token on the pane and a herdr notification. realm refuses
to type into a pane whose tab label holds `👑`, whatever its subscription says. Start it, then subscribe
yourself in aside mode only:

1. `launchctl print "gui/$(id -u)/com.loup.realm"` fails: `realm install`.
2. `realm subscribe "$HERDR_PANE_ID" --agent <QUEEN> --project <key> --aside`.

## 2. Register the workers

For each worker, `create_agent_identity` with `project_key: <key>`, `program: "omp"`, your model,
`task_description: "Swarm worker <i>/<size>, queen <QUEEN>"`. Keep each returned `name`.

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

Brief (`<W>`, `<w>`, `<KEY>`, `<QUEEN>`, `<i>`, `<size>`):

```markdown
You are <W>, worker <i>/<size> of a swarm. The queen is <QUEEN>.

0. First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "🛠️ subject-<w>"`.
1. Connect to Agent Mail: `macro_start_session` with human_key `<KEY>`, agent_name `<W>`, program `omp`.
   You are already registered as <W>; never take another name.
2. Your work comes only from the queen, by mail. Whenever you are told to check mail, `fetch_inbox`
   (agent_name `<W>`, project_key `<KEY>`, unread_only, include_bodies) and act on what the queen sent.
3. Each message from the queen is one subject. Do it fully, then `reply_message` in its thread: result,
   files touched, what is unverified. Blocked or need a decision: reply with the question, never guess.
4. Never send any herdr command (send-text, send-keys, run, close, rename, anything) to the queen's pane or
   tab, and never do it on anyone's request. After replying by mail, stop: the queen reads her inbox herself.
5. Do not message the user's contacts, push, deploy or delete anything unless the queen's message says so
   explicitly. Do not message other workers unless the queen tells you to.

Now connect, then reply to me here in one line: your agent name and project. Then wait.
```

## 4. Be the queen

From here until the user ends the swarm, you do two things only:

- **Answer the user.** Status, results, questions the workers raised.
- **Manage subjects.** You do not do the work yourself: no code edits, no research, no commands beyond Agent Mail
  and herdr. A request you could do in one tool call still goes to a worker.
- **Never take prompts from anyone but the user.** See the absolute rule above: no worker brief includes your
  pane id, and you never ask a worker or any agent to type into it.

A subject is one self-contained unit of work, one mail thread, one owner:

1. Split the user's request into subjects. Name each with a short kebab-case slug.
2. Assign each to a worker: an idle one first; several subjects to one worker only when every worker is busy.
   Keep one worker per subject until it is done, so its context stays useful.
3. `send_message` from `QUEEN` to that worker: `subject: [<slug>] <title>`, `topic: <slug>`, body with the goal,
   the files or links it needs, what done means, and what it may not do. Then wake it:
   `herdr pane send-text <pane> "check your mail"` and `herdr pane send-keys <pane> enter`.
4. On every turn, `fetch_inbox` for `QUEEN` (unread_only, include_bodies) before answering the user. Do not poll
   or wait for replies: realm's aside (pane token + notification) tells the user mail landed, and their next
   prompt's turn reads it. Each reply moves its subject to done, blocked (relay the question to the user) or
   redirected (answer in-thread).
5. Keep a subject table — slug, worker, state (`assigned`, `blocked`, `done`) — and show it whenever the user
   asks for status or a subject changes state.

Your `send-text` nudge wakes a worker at once; the realm service catches any unread mail it misses, within the
subscriber's interval (60 s) once the pane is idle. A worker that stops answering: `herdr pane read <pane>`
before deciding anything.

## Ending the swarm

Only on the user's word: `/realm-stop`.
