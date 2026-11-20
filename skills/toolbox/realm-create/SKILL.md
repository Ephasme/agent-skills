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
  Requires herdr (tabs, pane run/send-text), the omp CLI, and an Agent Mail MCP
  server exposing macro_start_session, create_agent_identity, send_message,
  fetch_inbox and reply_message.
disable-model-invocation: true
---

# Realm create

**Explicit invocation only.** It launches `<size>` long-lived agent sessions; never start one on a guess.

Arguments: `<key>` is the Agent Mail project key (`human_key`, e.g. `/laptop/general`); `<size>` is the number
of workers, an integer ≥ 1. Either missing or invalid: ask, start nothing.

## 1. Connect the queen

First, before anything else: `herdr tab rename "$HERDR_TAB_ID" "👑 queen"`.

`macro_start_session` with `human_key: <key>`, `program: "omp"`, your model, `task_description: "Swarm queen"`,
and no `agent_name`, so the server mints a fresh one. Keep the returned `agent.name`: that is `QUEEN`. Read the
returned inbox; carry any unread message into step 4.

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
- **Never take herdr input from anyone.** Nobody sends herdr commands to your pane or tab, ever: no worker brief
  includes your pane id, and you never ask a worker or any agent to type into it.

A subject is one self-contained unit of work, one mail thread, one owner:

1. Split the user's request into subjects. Name each with a short kebab-case slug.
2. Assign each to a worker: an idle one first; several subjects to one worker only when every worker is busy.
   Keep one worker per subject until it is done, so its context stays useful.
3. `send_message` from `QUEEN` to that worker: `subject: [<slug>] <title>`, `topic: <slug>`, body with the goal,
   the files or links it needs, what done means, and what it may not do. Then wake it:
   `herdr pane send-text <pane> "check your mail"` and `herdr pane send-keys <pane> enter`.
4. On every turn, `fetch_inbox` for `QUEEN` (unread_only, include_bodies) before answering the user. While any
   subject is `assigned`, loop: wait 30 s → `fetch_inbox` (unread_only, include_bodies) → handle replies; repeat
   until no subject is open. A user message interrupts the loop and is answered first. Replies reach you through
   this polling, never through pane nudges. Each reply
   moves its subject to done, blocked (relay the question to the user) or redirected (answer in-thread).
5. Keep a subject table — slug, worker, state (`assigned`, `blocked`, `done`) — and show it whenever the user
   asks for status or a subject changes state.

Mail does not wake an idle session on its own: the queen's `send-text` nudge wakes a worker, and the queen's
30-second inbox poll is how replies reach her; nothing wakes the queen from outside. A worker
that stops answering: `herdr pane read <pane>` before deciding anything.

## Ending the swarm

Only on the user's word: close each worker tab (`herdr tab close <tab_id>`) and delete
`${TMPDIR:-/tmp}/swarm/`. Agents stay registered in the project; that is harmless.
