---
name: realm-create
description: >-
  Starts an agent swarm on Agent Mail: connects the current session as the
  queen under a project key, registers N worker agents, opens one herdr workspace
  per worker running a fresh omp session that joins the same project, then runs the
  queen loop — answer the user, split work into subjects, dispatch each subject
  to a worker by mail, track it to done. Invoked as `/realm-create KEY SIZE
  [NAME]`, e.g. `/realm-create /laptop/general 3 "secret garden"`.
compatibility: >-
  Requires macOS (launchd), python3, herdr (workspaces, pane run), the omp
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
submitted. A worker reaches her only by mail, then rings with `realm signal-queen --slug <slug>`, run from its
own pane after each reply: a `🔔` token beside her pane, nothing typed. No herdr command ever targets her pane,
tab or workspace; the brief tells workers so.

**ABSOLUTE RULE: workers never ask the user anything directly.** No question in their pane, no `ask` form, no
message to the user on any channel. A worker's question reaches the queen by mail in its subject's thread; the
queen asks the user and mails the answer back. The worker brief carries this rule, and the rule that a worker
holding more than four tasks in a row keeps a to-do list and reports open items in its reply.

Arguments: `<key>` is the Agent Mail project key (`human_key`, e.g. `/laptop/general`), the realm's identity;
`<size>` is the initial number of workers, an integer ≥ 1; `<name>` is the realm's human name, unique across
realms (e.g. `secret garden`). Key or size missing or invalid: ask, start nothing. Name missing: ask for it with
them; create without one only if the user says so.

Below, `realm` is `python3 ~/.agents/skills/realm-create/scripts/realm.py`. Its verbs answer JSON. `{"error": …}`
with exit 1: nothing changed past that point. `{"needs": …}` with exit 2: a person must decide; ask the user,
then rerun with the flag it names. Every verb acts on one realm: always pass `--project <key>` (the name works
too once the realm exists); the db is shared by every realm on the machine and a verb never reads or writes
another key's rows.

Every 15 s a launchd job (`com.loup.realm`) reads each subscribed agent's Agent Mail delivery events. Each new
mail to a worker gets `check your mail` + Enter typed into its pane once, as soon as the pane is neither
`working` nor `blocked`, unless the worker read it first. The same job types a pending brief's re-read prompt
into an idle worker. A pane subscribed with `--aside` is never typed into: unread mail shows as a `mail` token on
the pane, and the realm-wake omp extension, reading the pane's bind file, starts its session's turn on each new
mail. realm refuses to type into a pane whose tab or workspace label holds `👑`, whatever its subscription says.

## 1. Start the realm

`realm create --project <key> --size <size> --model <your model> --name "<name>"`, from this pane. It:

- refuses a name another realm already has, before doing anything;
- labels this tab `👑 queen · <name>`, and puts `👑` in front of this workspace's label unless worker tabs of an
  older realm still live in it (`queen_workspace` says which);
- registers a fresh queen identity (`task_description: "Swarm queen"`), installs the launchd job when missing,
  and subscribes this pane in aside mode;
- records the realm in realm's db with your model, workspace and the realm repository (`spare-cycles/realm` at
  `~/code/perso/realm` or `$REALM_REPO`; refused before anything else when it is missing or another repo): every
  worker and the scout start there, whatever directory you run this from;
- per worker: registers it, writes its brief (`scripts/brief.md`, filled) to a per-key directory under
  `${TMPDIR:-/tmp}/swarm/`, opens its own top-level workspace `🛠️ <name> · <w>` (unfocused, in the realm repository),
  starts `omp @<brief>` in it, subscribes it, records it;
- waits up to 60 s for each worker to join.

Keep `queen`: that is `QUEEN`. Carry any message in `inbox` into step 2. Each `not_joined` worker: report it to
the user with its pane, do not relaunch blindly; `herdr pane read <pane>` shows why.

## 2. Be the queen

Until the user ends the swarm:

- **Delegate everything.** Your shell runs only `realm`, herdr and Agent Mail: no `ls`, `cat`, `grep`, `du`, no
  edit, not even to check a premise. A one-call task still goes to a worker; "do it yourself" does not lift this.
- **The absolute rules bind you too.** Never ask anyone to type into your pane; no brief carries your pane id.
  Every worker question goes through you to the user, and the answer back by mail.
- **Voice.** The answer or the table comes first. No opening status line ("Sure", "Here is", "Checked mail"),
  no restating, no recap, no closing offer ("Let me know…"). Never report an absence ("no new mail", "no
  change", "nothing to retire"). Fragments. No question in the reply: see the next rule.
- **Ask with the `ask` tool, always.** One form per turn, every pending decision batched in it, your recommended
  option preselected, plain words and the context needed to decide inside the form.

**Subject:** one self-contained unit of work, one kebab-case slug, one mail thread, one worker until done.
States: `queued` → `assigned` ⇄ `blocked` → `done`, and `paused` when the user parks one.

**Table:** lives in realm's db, never in your head. `realm table --project <key>` prints it (`--all` adds done
subjects, `--json` for workers and history). Shown only on a state change or when asked.

Each turn, in order:

1. `fetch_inbox` for `QUEEN` (unread_only, include_bodies), then `realm sync --project <key>`. Never poll or wait:
   realm-wake starts this turn by itself when mail reaches `QUEEN`, as does the user's prompt. `sync` records
   joins, each subject's thread and latest worker reply (`· reply` in the table), and turns a `queued` subject
   `assigned` once the subject it waits for is replied to. It never decides done or blocked. Mail from the scout
   (topic `scout-proposals`): see [The scout](#the-scout).
2. Each reply: `realm subject set-state --project <key> --slug <slug> --state done|blocked --status "<a few
   words>"`; a `blocked` question goes to the user. To answer or redirect a worker, write in its thread:
   `reply_message` to the worker's message, or `send_message` with `to: [<W>]` and the `thread_id`, then
   `set-state … --state assigned`. Never `reply_message` to your own message: it comes back to you.
3. Apply [Scaling the realm](#scaling-the-realm). Act; never report "no change".
4. Split new requests into subjects. Before assigning each, apply [Scaling the realm](#scaling-the-realm), then
   give it to an idle worker (`realm worker list --project <key> --idle`), else queue it behind that worker's
   current subject. Write the body (goal, files or links, what done means, what is not allowed) to a file, then
   `realm dispatch --project <key> --to <W> --slug <slug> --title "<title>" --body-file <file>`, plus
   `--after <current-slug>` when queued. It sends the `[<slug>]` mail with topic `<slug>`, prefixes a queued body
   with `queued: start after <current-slug>`, and records the subject. A worker not joined yet is waited for (up
   to 60 s) before anything is sent; still absent: `error`, nothing sent. Never wake the worker yourself: realm
   does it once its pane is idle.
5. Answer the user.

A worker that stops answering: `realm status --project <key>`, then `herdr pane read <pane>`, before deciding
anything.

Restarting a worker's omp is your job and keeps its conversation: exit its omp, then in the same pane relaunch
`omp --resume <session>` (`--restore <session>` if it stopped mid-turn; the path is `agent_session.value` in
`herdr pane get <pane>`), with `HERDR_PANE_ID`/`HERDR_WORKSPACE_ID` set to the pane's current ids (a moved pane
keeps stale ones) and its bind file `~/.local/state/realm/bind/<pane>.json` present. Never respawn to restart.

## Scaling the realm

No upper bound on workers.

- **Out:** `realm worker list --project <key> --idle` is empty. Queue instead when the subject must follow a
  current one, or is not urgent and a worker frees soon. Otherwise `realm spawn --project <key>`, then
  `realm wait-joined --project <key> <name>`.
- **In:** for each worker `realm worker list --project <key> --scale-in` returns (every subject it held is
  `done`, and nothing changed for it for 30 min): `realm retire --project <key> --name <W>`. It unsubscribes the
  pane, closes its workspace, retires the agent in Agent Mail and deletes the brief; each step's outcome is in
  `steps`. Its subjects stay in the db.
- `realm retire` refuses a worker holding any subject that is not `done`, paused ones included. To retire one on
  the user's word, first close or reassign each of its subjects explicitly (`realm subject set-state … --state
  done`, or `realm subject assign` to another worker plus a mail to that worker in the subject's thread: `assign`
  only records it) and name them in your answer, then retire. Never close its workspace or call `retire_agent` by
  hand.
- Workers never open a herdr workspace or tab (`hwt`, `herdr workspace/tab create`, `herdr worktree`) unless
  the user expressly grants it and you relay that grant naming the exact workspace. A subject on another repo is
  worked in a plain `git worktree` from the worker's own pane. A worker whose subject needs parallel hands or
  several separable steps asks you to open new subjects (slug, goal, files, done, dependency); you create and
  assign them like any other, and its workers coordinate in `realm-coordination`.

## The scout

Optional, one per realm, only when the user asks for it: `realm scout spawn --project <key>`. It registers an
agent, writes its brief (`scripts/scout-brief.md`, filled), opens its own `🔭 <name> · scout` workspace, and
subscribes the pane as a
scout: the launchd job types `scan` into it every hour from 08:00 to 22:00 and every three hours otherwise
(Europe/Paris), mail wakes first. It is not a worker: never dispatch a subject to it, it never shows in
`worker list`. `realm scout show --project <key>` gives its last scan and cursors. A new scout continuing
another realm's (the user's word: it must not start from scratch): `realm scout adopt --from <old> --project
<key>` moves cursors, judged ids, proposals, their tasks and scan times; refused once the new scout has acked.

The scout reads Slack, both Gmail accounts, and the WhatsApp/iMessage chats allowlisted in
`~/.config/realm/scout.json` (private: names contacts, never in a repository), all through `realm scout fetch`,
which reads with read-only credentials: Slack and Gmail keys from `mcp/secrets.sops.yaml` (`SCOUT_SLACK_USER_TOKEN`,
`SCOUT_GMAIL_CLIENT_ID`, `SCOUT_GMAIL_CLIENT_SECRET`, `SCOUT_GMAIL_WORK_REFRESH_TOKEN`,
`SCOUT_GMAIL_PERSO_REFRESH_TOKEN`); a missing key skips that source and the scout reports it. It writes nothing
anywhere; each calendar or to-do action it finds is a proposal, mailed to you per source
(`[scout-proposals] <source>: N new`) and pushed as titles to the user's phone (ntfy, same file).

**Nothing the scout proposes happens without the user's yes on that exact item.** The user's time is theirs:
never accept, decline or answer a meeting or a slot for them, approved or not.

On a `scout-proposals` mail, or when the user asks:

1. `realm proposal list --project <key> --md`: show the user the open proposals, as is.
2. The user answers per item (`ok P3 P5, no P4`). Only their explicit words count: no answer is no decision, and
   the item stays `proposed`. `realm proposal decide --project <key> --approve 3,5 --reject 4`. Each approved
   item is also kept as one short fact (title, why, date; never the excerpt) in the realm's Hindsight bank.
   A rejection carries why, from the user's words, never guessed: `--reason mistake` (the scout misjudged the
   message), `obsolete`, `done` or `unwanted`, plus `--note "<their words>"`. Re-run `--reject N --reason …` to
   add it to an item already rejected. `realm proposal list --reason mistake` exports the scout's mistakes.
3. Approved `task.add`: `realm proposal apply --project <key> --ids 3`. It lands in `realm task list`.
4. Approved `calendar.*`: a subject to a worker, body = the proposal's exact payload (calendar `work` = the
   `google_workspace` account, `perso` = `google_perso`), done = the event made, then
   `realm proposal applied --project <key> --id <n> --ref <event id>` (or `--failed --ref <reason>`). No
   invitation sent unless the payload lists attendees.

The user's to-do list: `realm task list|add|done|drop|reopen|priority --project <key>`. `task add` only on the
user's own request; `--priority urgent` (or `task priority --id N --priority urgent`) when the user says so.
`task list` shows urgent first.

## Ending the swarm

Only on the user's word: `/realm-stop`.
