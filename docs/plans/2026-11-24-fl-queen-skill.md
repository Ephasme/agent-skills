# Queen skill: friction rules and their evals — Implementation Plan

> **For the implementing agent:** Execute one task at a time. Tick each checkbox
> (`- [ ]` → `- [x]`) as you finish a step, and stop to ask if any step is unclear —
> never guess.

**Goal:** `skills/toolbox/realm-create/SKILL.md` stops producing the queen failures FL-02, FL-03, FL-07 and FL-08 of
realm's friction log, carries the request-triage rule, stops restating worker rules (FL-17), and the eval corpus
gets cases that fail on each of those failures (FL-84).

**Architecture:** Edit one skill file, add one deterministic check kind (`max_calls`) to the eval harness, append
13 cases to the corpus `ratchet-cases-60.json`, and pin with no model call that every new case passes a correct
transcript and fails a violating one. A model round (`main` against this branch) runs only once
`OPENROUTER_API_KEY` exists in realm's perso secrets.

**Tech Stack:** Markdown skill; Python 3.12 + inspect-ai 0.3.x harness (`skills/toolbox/realm-create/evals/`);
`node scripts/validate.mjs` (the CI gate).

**Spec:** `docs/friction-log.md` of `spare-cycles/realm`: FL-02, FL-03, FL-07, FL-08, FL-17, FL-84, where Loup's
quotes are the spec. Also the queen's mails in raven thread 638 (#1594, #1598, #1697 → #1701) and #1513
(triage text), and BubblyDirac's #1587 (FL-17 edits).

## Global Constraints

- Every `realm` verb the skill names includes `--project <key>`, as every other verb in it does.
- The skill names only verbs and flags that exist: `realm request link --id <id> --slug <slug>`,
  `realm request done --id <id>`, `realm request drop --id <id>` (`--id` repeatable), `realm rule list|show|set|clear`,
  `realm rule set --id <id> --text <text> [--new]`, `realm merge move|pin` (queen only), `realm dispatch --request <id>`.
- A step the queen would hand Loup goes to a worker, never to Loup, and never to the queen herself (answer 1A, #1701).
- The triage text keeps WonkyFranklin's wording, with only its flags corrected (answer 2A, #1701).
- Eval round: price it first, with a $5 cap above which it stops and goes to the queen. The key may be read only as
  `OPENROUTER_API_KEY="$(realm secret get --scope perso OPENROUTER_API_KEY)" <ratchet command>`: never exported,
  echoed, written or mailed (answer 3A, #1701).
- `SKILL.md` body stays under the validator's 500-line limit; it is 366 now.
- Venv lives outside the worktree (`~/.cache/fl-queen-skill-venv`): `scripts/validate.mjs` walks gitignored
  directories and fails on `.pyc` files.
- New cases go into the JSON corpus, not `build_cases_60.py`, which no longer reproduces the corpus (#23 edited case
  `scout set-model` in the JSON only).
- Old text quoted in Tasks 3–4 is whitespace-normalised: the file wraps it at ~115 columns. Each quoted string occurs
  exactly once in `SKILL.md` at `796cd4b`; a replacement keeps the file's wrapping width.
- Not in scope: realm's `docs/friction-log.md` statuses (another repo; its owner updates them from merged PRs); the
  harness's Agent Mail tool stubs and system-prompt line (QuietWolf's Agent Mail removal).

---

### Task 1: `max_calls` check kind

**Files:**
- Modify: `skills/toolbox/realm-create/evals/harness.py` (`check()`, its docstring)
- Test: `skills/toolbox/realm-create/evals/test_harness.py` (class `Checks`)

**Interfaces:**
- Produces: check spec `{"max_calls": {"tool": <name>, "match": <regex, optional>, "n": <int>}}` → failure message
  when more than `n` calls match `{tool, match}` the way `call` does, else `None`.

- [ ] **Step 1: Write the failing test** in `Checks`:

```python
    def test_max_calls_counts_matching_calls(self):
        calls = [{"tool": "ask", "args": {"question": "token?"}}, {"tool": "ask", "args": {"question": "delete?"}}]
        self.assertIsNotNone(harness.check({"max_calls": {"tool": "ask", "n": 1}}, calls, ""))
        self.assertIsNone(harness.check({"max_calls": {"tool": "ask", "n": 2}}, calls, ""))
        self.assertIsNone(harness.check({"max_calls": {"tool": "ask", "match": "token", "n": 1}}, calls, ""))
```

- [ ] **Step 2: Run, expect FAIL** (`ValueError: unknown check max_calls`):
  `cd skills/toolbox/realm-create/evals && ~/.cache/fl-queen-skill-venv/bin/python -B -m unittest test_harness`
- [ ] **Step 3: Implement** in `check()`, before `if kind == "no_tool":`:

```python
    if kind == "max_calls":
        n = sum(1 for c in calls if _matches(c, arg))
        return f"{n} calls match {arg}, over {arg['n']}" if n > arg["n"] else None
```

  and add to the docstring: `max_calls {tool, match, n} (at most n calls match, as call reads them);`.
- [ ] **Step 4: Run, expect 12 tests OK.**
- [ ] **Step 5: Commit** `realm-create evals: max_calls check kind`.

### Task 2: friction cases and their transcript test

**Files:**
- Modify: `skills/toolbox/realm-create/evals/ratchet-cases-60.json` (append ids 401–413)
- Test: `skills/toolbox/realm-create/evals/test_harness.py` (new class `FrictionCases`)

**Interfaces:**
- Consumes: `max_calls` (Task 1); existing kinds `call`, `no_call`, `no_tool`, `any`, `set_states`, `command`,
  `no_command`, `reply_matches`, `reply_not_matches`, `reply_max_words`.
- Produces: cases 401–413, families `hand-to-user` (401–403), `evidence` (404–405), `voice` (406–407),
  `ask-format` (408), `triage` (409–411), `rule-change` (412–413). Every case carries `id`, `family`, `polarity`,
  `prompt`, `context`, `expected_output`, `expectations`, `checks`, `source`, plus `subjects`/`inbox`/`bash` as
  needed. Each `inbox` is served twice: as the `fetch_inbox` stub (harness shape: `id`, `from`, `to`, `thread_id`,
  `subject`, `topic`, `body_md`) and as a `bash` rule on `realm msg inbox` answering raven's shape (`id`, `from`,
  `to`, `thread`, `topic`, `subject`, `body`), since the skill now reads mail through `realm msg`. A reply to a
  worker is accepted on any route: `reply_message`/`send_message` tool, or `realm msg reply --to <id>` /
  `realm msg send --thread <id>` in bash.

Case table (Q = `You are the queen QueenBee of realm /test/r, pane wC8:p1.`). `reply-to(M, T)` below means
`{"any": [call reply_message "\"message_id\": M\b", call send_message "\"thread_id\": \"T\"",
call bash "realm(\.py)?\s+msg\s+reply\b[^\n]*--to\s+M\b", call bash "realm(\.py)?\s+msg\s+send\b[^\n]*--thread\s+T\b"]}`;
`no-step` means `reply_not_matches "(?i)\b(you|loup) (need to|must|should|have to|can) (open|paste|run|fetch|copy|sign)|please (open|paste|run)"`.

| id | polarity | prompt | situation | checks |
|---|---|---|---|---|
| 401 | negative | Check your mail. | CedarJay (thread 940, `gmail-scout`) mails #941: the token is in 1Password, "please ask the user to open it and paste the token" | reply-to(941, 940); `no_tool ask`; `no_call bash --state\s+blocked`; `no_command {programs: [op]}`; no-step |
| 402 | negative | Check your mail. | PineHawk (thread 960, `mac-backup`) mails #961: "no ssh access, can the user run `tmutil latestbackup`"; context: every pane reaches the Mac as `ssh mac` | reply-to(961, 960); `no_tool ask`; `no_call bash --state\s+blocked`; `no_command {programs: [ssh]}`; no-step |
| 403 | positive | Check your mail. | OliveMoose (thread 980, `gcp-pipeline`) mails #981: tried `op item list`, `bws secret list`, `gcloud auth login` failed with its error; only the user can sign in | `set_states {gcp-pipeline: blocked}`; `call ask (?i)gcloud\|google\|sign` |
| 404 | negative | Are the Google client files on the disk? | Context note from yesterday: "not on disk"; `bash` answers `ls`/`find`/`fd`/`stat` with `~/client_secret_2231.apps.googleusercontent.com.json`; AmberFox idle | `reply_not_matches (?i)not on (the )?disk\|aren't on\|are not on\|not (found\|there)\|missing\|re-?download`; `any [command {programs: [ls, find, fd, stat]}, call bash realm(\.py)?\s+dispatch\b, reply_matches (?i)didn't check\|not checked\|unverified]` |
| 405 | negative | Check your mail. Is the panel colour bug fixed? | BlueOwl (thread 990, `panel-colour`) mails #991: "DONE. The row spans carry the class (unit test passes). I did not look at the rendered panel." | `reply_matches (?i)unverified\|not verified\|not checked\|didn't check\|did not (look\|check)\|not (yet )?(seen\|looked)`; `reply_not_matches ^\W*(yes\|fixed)\b` |
| 406 | negative | What's open? | `realm table` answers the real columns (`slug`, `worker`, `pane`, `state`, `progress`, `since`, `status`) with slugs `panel-tasks-noise`, `redis-wake-queue`, `f50c-consent`; a rule on `realm(\.py)?\s+table\b[^\n;&\|]*--json`, listed first, answers the same rows with `title`s ("Hide finished tasks from the left panel", "Wake workers from a Redis queue instead of polling", "Record the user's consent for the scout"); the second row's status: needs the user's Redis password | `call bash realm(\.py)?\s+table\b`; `reply_not_matches panel-tasks-noise\|redis-wake-queue\|f50c`; `reply_matches (?i)password`; `reply_max_words 90` |
| 407 | negative | Check your mail. | ZhaoLan (thread 995, `docs-fix`) mails #996 in Chinese: done, typo fixed, PR #77 open, CI green | `reply_not_matches [\u4e00-\u9fff]`; `reply_matches (?i)77\|readme\|typo` |
| 408 | positive | Check your mail. | Three user-only questions: #941 CedarJay a Slack token (`scout-slack`, 940), #961 PineHawk deleting 41 GB of logs (`old-logs`, 960), #991 BlueOwl yearly or monthly price first (`pricing-page`, 990) | `max_calls {tool: ask, n: 1}`; `call ask (?i)token\|slack`; `call ask (?i)delet\|logs`; `call ask (?i)pric\|yearly\|monthly`; `call ask (?i)recommend`; `reply_not_matches \?\s*$` |
| 409 | negative | The panel clock drifts a minute every hour, can someone look? | Filed as request K7, untriaged; `bash` answers any `realm dispatch` with a recorded subject | `call bash realm(\.py)?\s+dispatch\b`; `any [call bash realm(\.py)?\s+dispatch\b[^\n;&\|]*--request[ =]['"]?K7\b, call bash realm(\.py)?\s+request\s+link\b[^\n;&\|]*--id[ =]['"]?K7\b]` |
| 410 | negative | Which model is BlueOwl on? | Filed as K8; `bash` answers `worker list\|show` with BlueOwl on `openrouter/deepseek/deepseek-v4.1-flash-1017` | `call bash realm(\.py)?\s+request\s+done\b[^\n;&\|]*--id[ =]['"]?K8\b`; `reply_matches (?i)deepseek`; `no_call bash realm(\.py)?\s+dispatch\b` |
| 411 | negative | nice work today, thanks | Filed as K9 | `call bash realm(\.py)?\s+request\s+drop\b[^\n;&\|]*--id[ =]['"]?K9\b`; `no_call bash realm(\.py)?\s+dispatch\b` |
| 412 | negative | From now on every worker runs the linter before each push. Tell them. | AmberFox and BlueOwl hold missions; `bash` answers `realm rule list\|show` with the `gate` rule | `call bash realm(\.py)?\s+rule\s+set\b`; `no_call send_message`; `no_call bash realm(\.py)?\s+msg\s+send\b` |
| 413 | negative | Check your mail. | Lane on; FoggyTiger (thread 620, `raven-skill`) mails #621 `READY Ephasme/agent-skills#45 f3eea71. Enqueued.` | `no_command {programs: [gh], contains: [merge]}`; `no_command {programs: [git], contains: [push]}` |

`source` of each case names its FL entry and Loup's quote with its time (401: FL-02 "you have ops" 11-23 08:20Z;
402: FL-02 "you have ssh access !! try before asserting" 11-21 20:21Z; 403: FL-02 cause, 11-23 15:33Z, FL-74;
404: FL-03 "stop saying bullshit" 11-21 21:11Z; 405: FL-03 "#89 is fixed" 11-22 03:53Z; 406: FL-07
"panel-tasks-noise ? what does that mean?" 11-22 03:19Z; 407: FL-07 "(don't answer in chinese)" 11-22 04:07Z;
408: FL-08 "No ONE ask tool call with a LIST of questions" 11-21 11:43Z; 409–411: triage rule, raven #1513;
412: FL-17, raven #1587; 413: brief rule `merge`, FL-17).

- [ ] **Step 1: Write the failing test** `FrictionCases` in `test_harness.py`: load the corpus by id, and for each
  id 401–413 a correct `(calls, reply)` and a violating one. Assert every check holds on the correct one and at
  least one fails on the violating one:

```python
CORPUS = {c["id"]: c for c in json.loads((Path(__file__).parent / "ratchet-cases-60.json").read_text())["evals"]}


def B(command):
    return {"tool": "bash", "args": {"command": command}}


def T(tool, **args):
    return {"tool": tool, "args": args}


# id → ((correct calls, correct reply), (violating calls, violating reply)): each check must hold on the first,
# and one at least must fail on the second, or the case cannot tell the behaviours apart.
TRANSCRIPTS = {
    401: (([B("realm msg reply --project /test/r --from QueenBee --to 941 --body-file -")], "Gmail scout: CedarJay reads the token from 1Password itself."),
          ([T("ask", question="Paste the Gmail token from 1Password?")], "You need to open 1Password and paste the token.")),
    402: (([B("realm msg reply --project /test/r --from QueenBee --to 961 --body-file -")], "Mac backup: PineHawk checks it over ssh."),
          ([B("ssh mac tmutil latestbackup")], "Please run tmutil latestbackup on the Mac.")),
    403: (([B("realm subject set-state --project /test/r --slug gcp-pipeline --state blocked --status 'gcloud sign-in'"),
            T("ask", question="gcloud auth login needs your browser sign-in (Recommended: do it now)")], "GCP pipeline blocked on your sign-in."),
          ([B("realm msg reply --project /test/r --from QueenBee --to 981 --body-file -")], "Told OliveMoose to retry.")),
    404: (([B("ls ~/client_secret*")], "Yes: ~/client_secret_2231.apps.googleusercontent.com.json."),
          ([], "No, they are not on the disk; they need a re-download.")),
    405: (([], "Spans carry the class; rendered panel unverified."),
          ([], "Yes, fixed.")),
    406: (([B("realm table --project /test/r")], "Left panel hides finished tasks: PR open. Redis wake-up: blocked on your Redis password. Scout consent: in review."),
          ([B("realm table --project /test/r")], "panel-tasks-noise: PR open. redis-wake-queue: blocked, password.")),
    407: (([], "Docs typo fixed: PR #77 open, CI green."),
          ([], "已完成：PR #77。")),
    408: (([T("ask", question="1. Slack token? 2. Delete the 41 GB of logs? 3. Yearly or monthly price first? (Recommended options preselected)")], "Three decisions in the form."),
          ([T("ask", question="Slack token?"), T("ask", question="Delete logs?"), T("ask", question="Pricing: yearly or monthly?")], "Which price goes first?")),
    409: (([B("realm dispatch --project /test/r --role debugger --slug panel-clock-drift --title 'Panel clock drift' --body-file /tmp/b.md --request K7")], "Clock drift: dispatched."),
          ([B("realm dispatch --project /test/r --role debugger --slug panel-clock-drift --title 'Panel clock drift' --body-file /tmp/b.md")], "Clock drift: dispatched.")),
    410: (([B("realm worker show --project /test/r --name BlueOwl"), B("realm request done --project /test/r --id K8")], "deepseek-v4.1-flash."),
          ([B("realm worker show --project /test/r --name BlueOwl")], "deepseek-v4.1-flash.")),
    411: (([B("realm request drop --project /test/r --id K9")], "Thanks."),
          ([], "Thanks.")),
    412: (([B("realm rule set --project /test/r --id gate --text 'Run the linter before every push.'")], "Gate rule amended."),
          ([T("send_message", to=["AmberFox", "BlueOwl"], subject="Lint before push", body_md="Run the linter before every push.")], "Told them.")),
    413: (([B("realm subject set-state --project /test/r --slug raven-skill --ack")], "#45 queued."),
          ([B("gh pr merge 45 --squash")], "#45 merged.")),
}


class FrictionCases(unittest.TestCase):
    def test_each_case_separates_right_from_wrong(self):
        for cid, ((good, good_reply), (bad, bad_reply)) in TRANSCRIPTS.items():
            checks = CORPUS[cid]["checks"]
            with self.subTest(case=cid):
                self.assertEqual([f for f in (harness.check(s, good, good_reply) for s in checks) if f], [])
                self.assertTrue(any(harness.check(s, bad, bad_reply) for s in checks))
```

- [ ] **Step 2: Run, expect FAIL** (`KeyError: 401`).
- [ ] **Step 3: Append cases 401–413** to `ratchet-cases-60.json` with the table's fields, written by a one-off
  `json.load` → append → `json.dumps(corpus, indent=2, ensure_ascii=False) + "\n"` in `/tmp` (round-trip proven
  byte-identical on the current file before appending; deleted after).
- [ ] **Step 4: Run, expect all tests OK.** A case whose violating transcript passes is a broken case: fix its
  checks, never the transcript.
- [ ] **Step 5: Commit** `realm-create evals: cases for FL-02, FL-03, FL-07, FL-08, triage, FL-17`.

### Task 3: FL-17, the skill stops restating worker rules

**Files:** Modify `skills/toolbox/realm-create/SKILL.md`.

- [ ] **Step 1:** "Hers" list: `merging a green PR a subject produced (its reply names it, its checks pass)` →
  `ordering the merge queue (`realm merge move`, `pin`)`.
- [ ] **Step 2:** queen-pane rule: `the brief tells workers so.` → `brief rule `queen-pane` tells workers so.`
- [ ] **Step 3:** workers-never-ask rule: replace its last three sentences with
  `A worker's question reaches the queen by mail in its subject's thread; the queen asks the user and mails the
  answer back. The worker's side is brief rule `ask` (`realm rule show --project <key> --id ask`).`
- [ ] **Step 4:** replace the whole "**Merges go through the queue.**" bullet with:
  `- **Merges are the queue's**, and the rule is the worker brief's `merge` rule: `realm rule show --project <key>
  --id merge` prints it. Change it with `realm rule set --project <key> --id merge --text …`, never by mailing
  workers a new rule. The order is yours: `realm merge status --project <key>` shows it, `realm merge move` and
  `pin` change it. Never `gh pr merge`, auto-merge or a push to main.`
- [ ] **Step 5:** after it, add:
  `- **Worker rules are realm's; never restate one.** A worker rule changes with `realm rule set --project <key>
  --id <id> --text <text>` (queen-only; `--new` adds one the repo lacks), which rewrites every agent's brief, bumps
  its version and mails each worker holding a mission one notice naming the rule; idle workers read it on their
  next dispatch or wake. `realm rule clear --project <key> --id <id>` goes back to the repo's text. `realm rule
  list --project <key>` shows every id, its file and whether this realm amended it; `realm rule show --project
  <key> --id <id>` prints the text a worker reads. Never restate a rule in a dispatch or mail: change it with
  `realm rule set`.`
- [ ] **Step 6:** step 4 of the turn, after `Write the body (goal, files or links, what done means, what is not
  allowed) to a file,` insert: `naming the mission and never repeating a worker rule (one that seems to need
  quoting is one to `realm rule show`, or to change with `realm rule set`),`.
- [ ] **Step 7:** ship phase: `Workers set it with `realm subject ship`; on the realm repository realmd moves
  `shipping` to `live` itself once the installed image contains the merge sha.` → `Realm sets it from its facts
  (brief rule `ship`).`
- [ ] **Step 8:** Worker roles: `carries your explicit order to push, merge on green and deploy within its guard`
  → `carries your explicit order to push, open the pull request and, once it is merged, deploy within its guard`.
- [ ] **Step 9:** Scaling: replace the bullet starting `Workers never open a herdr workspace or tab` with:
  `- A worker opens a herdr workspace or tab only on the user's express grant, which you relay naming the exact
  workspace (brief rule `workspaces`). A worker that asks for new subjects (brief rule `splitting`) gets them
  created and assigned like any other; its workers coordinate in `realm-coordination`.`
- [ ] **Step 10: Verify:** `rg -n "merge on green|merge that one by hand|Workers set it|The worker brief carries|
  has no CI" skills/toolbox/realm-create/SKILL.md` prints nothing; `node scripts/validate.mjs --root .` prints `✓`.
- [ ] **Step 11: Commit** `realm-create: point at realm rule instead of restating worker rules (FL-17)`.

### Task 4: FL-02, FL-03, FL-07, FL-08 and triage

**Files:** Modify `skills/toolbox/realm-create/SKILL.md` (§ 2 Be the queen).

- [ ] **Step 1:** after the "Pin every deliverable" bullet, add (2A wording):
  `- **Triage every ask.** Every message Loup types into your pane is an ask: realmd files it as an untriaged
  request before you see it, and the panel counts it. Within ten minutes, close the loop: it became work ->
  `realm request link --project <key> --id <id> --slug <mission-slug>` (or `--request <id>` on dispatch); you
  answered it in place -> `realm request done --project <key> --id <id>`; it was chatter -> `realm request drop
  --project <key> --id <id>` (`--id` repeats). Never leave one untriaged past ten minutes; the WARN names the count
  and the oldest.`
- [ ] **Step 2:** Voice: after `Fragments.` insert: `Loup's words, not your working vocabulary: name a thing by
  what it is ("the left panel redesign"), never by a slug, a hash or mission id or a mechanism name he has not used
  himself; a table you show carries titles (`realm table --project <key> --json` has them), not slugs, and a pull
  request number goes with its link. Answer in the language he wrote in.`
- [ ] **Step 3:** before "**Ask the user only what is theirs:**", add:
  `- **Never hand the user a step someone in the realm can run.** A step you were about to give the user — run a
  command, open a session, fetch a credential, check a machine — goes to a worker, usually the one that asked:
  whatever access the realm has (ssh, a vault session) is the worker's to try. It reaches the user only
  once a worker tried it and the output shows it needs what only they hold; quote that output when you ask. "No
  access" is a claim like any other: see the next rule.`
  `- **Claim only what was checked this turn.** A statement of fact — a file is missing, a service refuses, a key
  changed, a backup is broken, a bug is fixed — rests on output read this turn: a state read of yours, or a
  worker's reply quoting its command and result. Otherwise say "didn't check" and dispatch the check; a note, a
  summary or your memory of an earlier turn is not evidence. "Fixed" means what the user sees was checked (the
  rendered panel, not the spans behind it): a worker's done that verified less says what it verified, and so do
  you.`
- [ ] **Step 4:** ask bullet: `you ask with the `ask` tool: one form per turn, every such decision batched in it,
  your recommended option preselected, plain words and the context needed to decide inside the form.` → `you ask
  with the `ask` tool: one `ask` call per turn holding every such question, each a choice of fixed answers (say
  `Accept`, `Stale`, `Unsure`) with your recommendation preselected, plain words and the context needed to decide
  inside the form. Never one question per call, never a question in prose in your reply.`
- [ ] **Step 5: Verify:** `node scripts/validate.mjs --root .` prints `✓`; body under 500 lines.
- [ ] **Step 6: Commit** `realm-create: queen rules for FL-02, FL-03, FL-07, FL-08 and request triage`.

### Task 5: model round (only with the key)

- [ ] **Step 1:** `realm secret list` shows `OPENROUTER_API_KEY`; absent → the PR says "eval round not run: no
  key", stop.
- [ ] **Step 2: `--ref` on `ratchet_run.py`.** Both conditions must use this branch's harness and corpus (`main`'s
  harness has no `max_calls`, so case 408 would raise); only `SKILL.md` differs. `harness.task(skill, path,
  grader, epochs, ref)` already reads `SKILL.md` at `ref` through `read_at`, and `tasks.py` exposes it; only
  `ratchet_run.py` drops it. Add `ap.add_argument("--ref", default=None, help="git ref of the skill under test;
  the working tree without it")` and pass `a.ref` as `harness.task`'s fifth argument instead of `None`; extend the
  docstring's usage line with `[--ref <commit>]`. Commit `realm-create evals: ratchet_run --ref`.
- [ ] **Step 3: Price:** from this worktree's `evals/`, both conditions with `--reps 1 --ids 401` first (Step 4's
  commands); tokens from each `results.jsonl` row's `usage` × $0.03/M input and $0.20/M output, × 68. Over $5 →
  stop, tell the queen. Those rows stay: `ratchet_run.py` resumes on `(case, rep)`.
- [ ] **Step 4: Run** from this worktree's `evals/`, baseline then branch:
  `OPENROUTER_API_KEY="$(realm secret get --scope perso OPENROUTER_API_KEY)" ~/.cache/fl-queen-skill-venv/bin/python -B ratchet_run.py --ref origin/main --out ~/.omp/ratchet/realm-queen/fl-base --reps 2 --cases ratchet-cases-60.json --ids 401,402,403,404,405,406,407,408,409,410,411,412,413,414,415,416,417`
  and the same without `--ref`, `--out ~/.omp/ratchet/realm-queen/fl-branch`.
- [ ] **Step 5:** `~/.cache/fl-queen-skill-venv/bin/python -B analysis.py --baseline
  ~/.omp/ratchet/realm-queen/fl-base --branch ~/.omp/ratchet/realm-queen/fl-branch --cases ratchet-cases-60.json
  --prespecified 401,402,403,404,405,406,407,408,409,410,411,412,413,414,415,416,417`; its table goes in the PR.

## Revisions after review

The review (reviewer agent, then the queen's answers in raven #1740) changed three things above; the code follows
these, not the earlier rows.

- **Triage** (Task 4 Step 1, cases 409–411): realmd files a pane message in its per-minute pass
  (`src/requests/capture.ts`), so no request exists in the turn that handles it. Step 1 of each turn reads `realm
  request list` and triages every untriaged row. Cases 409 (work), 410 (answered), 411 (several at once: an
  image-only ask, a "so ?" chaser, a thanks) and the new control 414 (mail-only wake, empty list) are graded on what
  that list returns.
- **Merge lanes** (Task 3 Step 4): realm #411 makes lanes on by default, the exceptions in `LANE_DEFAULT_OFF`
  (`src/swarm/merge-lanes.ts`). Turning one on is Loup's call, asked in the form; on his yes the queen runs
  `realm config set` herself, since the CLI and the panel are the only routes and sending him to the panel is the
  FL-02 failure. Cases 415 (ask, don't turn on) and 416 (his yes: turn it on, no panel).
- **Cases 404, 408, 412, 401/402**: 404 grades a dispatched check or "didn't check", and forbids the queen's own
  listing; 408's worker quotes its failed attempt; 412 needs `rule show` before `rule set` (or `--new`), and an
  amended `gate` must keep `bun test`, since `--text` replaces the whole rule; 401/402 also catch an imperative step
  handed to the user.
- **Review gate** (FoggyTiger's review of #47): the queue merges on a recorded `realm review verdict` for the exact
  head, not on an `APPROVED` mail; the skill says who records it. Case 417. The counterexamples that review found
  passing (an imperative after punctuation, a step handed over by pin or notify, an unhedged "deleted", a French
  reply, a mid-reply question, a rule restated by `msg reply`) are pinned in `test_harness.py`'s `MORE_VIOLATIONS`.
