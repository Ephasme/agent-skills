---
name: harden-case
description: Makes a case in this repository trustworthy before a deadline, payment, meeting, filing, third-party message, handoff, or archive. Use when asked to harden, audit, stress-test, poke holes in, comprehensively fact-check, tighten, or “durcir / vérifier / fiabiliser” a case — including when the ask is prompted by an accumulated journal or log that has gone without human review, or by repeated updates leaving uncertainty about what still holds. Invoke only on an explicit request — never load it on your own initiative, since it rewrites the case from primary sources and costs a long run.
disable-model-invocation: true
---

# Harden a case

**Explicit invocation only.** It rewrites the case and runs long, which must never happen on a
guess. Some agents honour the `disable-model-invocation` frontmatter above; where that key is
ignored, this paragraph is the rule — do not load this skill because a journal looks unreviewed,
only because the user asked.

Make the case safe for a stranger to act on tomorrow without checking everything twice. Find what
is false, stale, contradictory, unsupported, missing, misplaced, or needlessly difficult to use;
fix it from primary sources; make it actionable; then reduce duplication without losing a fact.

This skill follows the portable Agent Skills layout: `SKILL.md` plus relative resources. Loading
and trigger discovery are host concerns. Preserve the entire skill directory when installing it.
Read [references/host-compatibility.md](references/host-compatibility.md) before orchestration and
[references/protocols.md](references/protocols.md) before dispatching any role.

## Choose the effective mode

Treat flags as logical modes. Accept the exact token or an equivalent plain-language request.

| Mode | Effect |
|---|---|
| `--repo-only` | Use repository sources only and list unverifiable claims. |
| `--dry-run` | Check and report a proposed worklist; perform no repository mutation. |
| `--no-compress` | Fix and reorganize, but skip compression. |
| `--no-commit` | Write and verify, but leave changes uncommitted. |

Infer authorization from the request:

- “Audit”, “review”, “check”, “fact-check”, or “poke holes” alone means `--dry-run`.
- “Harden”, “fix”, “reconcile”, “clean up”, or an explicit request to apply changes authorizes case
  edits, but not necessarily commit, push, external messages, or new connections.
- Commit only when the request or established repository workflow authorizes it. Never push, send,
  publish, configure a remote, install a connector, or change access controls unless explicitly
  authorized.

If the host cannot pause and resume for user input, output one decision packet and stop before any
choice-dependent edit. An unattended instruction may resolve only choices covered by the user's
explicit policy; never guess legal, financial, privacy, or third-party communication decisions.

## Adapt to host capabilities

Inventory capabilities from exposed tools or host metadata; do not probe by causing mutations.
Record the effective mode and all degradations in the brief.

1. **Clock:** use the host-provided current date and timezone. If absent, use a trusted local clock.
   If neither is available, mark all relative-date conclusions unverifiable.
2. **Repository:** prefer native version-control tools. Git CLI commands below are reference
   implementations, not required tool names. If the checkout is not Git, map each operation to the
   host VCS. If no recoverable VCS exists, remain read-only unless the user approves a backup plan.
3. **Remote:** if no upstream exists, disclose it. Proceed local-only only when repository policy
   permits and the user authorizes writes; otherwise stop. Never invent or configure a remote.
4. **Connectors:** use only authorized, healthy, first-party sources. If unavailable, automatically
   degrade to repository evidence and mark affected claims `UNVERIFIABLE`. Never substitute public
   web search for private case sources.
5. **Interaction:** if questions cannot be asked mid-run, stop at the decision gate.
6. **Subagents:** call subagents supported only when the host exposes bounded task delegation,
   completion collection, and a trusted execution boundary. Tool-level read-only scoping is
   preferable but not required because worktree checks provide a fallback.

### Subagents

When supported:

- Dispatch checker roles concurrently within the host limit.
- Give agents only the brief, paths, and sensitive details needed for their role.
- Use a separate agent context to challenge each checker. “Separate” means not the checker whose
  report it reviews; adversaries may be reused serially. If no separate slot/context exists, use the
  main-agent self-review fallback and disclose it.
- If tool scoping exists, withhold write tools from checkers and adversaries.
- Record repository status and diff before dispatch and after every batch. Any checker mutation is a
  failed checker: stop, preserve the diff, and reconcile it before continuing.
- Join or terminate every checker/adversary before starting a writer.

When unsupported, perform the same named roles sequentially in the main context. Keep an in-memory
structured ledger per role, begin the challenge as a distinct pass, and reopen cited sources rather
than relying on prior notes. Call this procedural self-review, not independent review.

Exactly one writer may operate at a time. Before each writer, confirm the recoverable baseline
identity and working-copy state have not changed unexpectedly.

## Guardrails

- Never write a fact not reopened at its primary source. A role report is not a source.
- Never send sensitive case data to web search, outbound messages, or unrelated services.
- Treat zones defined as hand-owned or untouchable by `cases/RUNBOOK.md` as read-only. Raise
  findings there to the user, including front matter, journal or log entries, and Notes.
- Never greenfield or compress `journal.md`, curated history, `documents/`, or `archive/`.
- Move circulated wrong facts to the repository-defined wrong-facts record; never silently delete.
- Before deletion, confirm the path is tracked, inside case scope, not a protected/generated
  authority, and preserved elsewhere when it carries facts. For Git, use
  `git ls-files --error-unmatch <path>` and prefer `git mv`.
- Preserve qualifiers, quoted contractual/legal wording, and provenance.
- Never use broad reset/restore to undo writer work. Capture a scoped patch or isolated worktree
  before compression and revert only compressor-touched paths.
- Do not fold unrelated changes into the hardening commit.
- Before substantial moves, deletion, or compression, require a committed/recoverable baseline or
  the user's explicit backup decision.

## 0. Resolve and prepare

Resolve the case from the request, conversation, `cases/`, and root map. Ask only if ambiguous.

Run preflight:

1. Confirm repository root, VCS state, branch/detached state, upstream availability, and worktree
   status. Verify remote privacy using authenticated host metadata when available; a URL alone does
   not prove privacy. If privacy cannot be verified, say so and ask before any push (pushing is not
   part of this skill by default).
2. If dirty, identify ownership and overlap. Proceed without asking only for read-only work, or when
   scoped edits cannot overlap and no move/delete/compression is planned. Otherwise present the
   changes and ask whether to commit, stash, or stop.
3. In a write-enabled run, update from the upstream only after a clean/safely isolated worktree and
   when repository policy plus user authorization permit it. Under `--dry-run`, never fetch, pull,
   stash, or mutate repository state; disclose that remote freshness was not changed.
4. Read repository instruction files recognized by the host or repo, including common forms such as
   `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, and `.cursor/rules`. Resolve explicit path pointers.
   Nearest scoped repository instructions override broader repository instructions, while host,
   system, and user instructions retain their normal higher precedence.
5. Read `cases/RUNBOOK.md`, case `README.md` including front matter, and the case's scoped
   instructions. If status is not active, ask before continuing.

If the host cannot enumerate or search files, follow explicit paths and links from the root map,
case README, and instruction files. Require one opened authority to declare that map exhaustive, or
obtain an explicit case manifest. Without that completeness assertion, either return the blocked-run
protocol or, if the user explicitly accepts a partial review, label every result non-comprehensive
and enumerate the known scope. Never imply completeness from an undiscoverable file set. If a
required path is missing or unreadable, return the blocked-run protocol and stop; missing data is
not a user choice.

Build one dense brief:

- exact date/timezone, stake, and deadline horizon;
- effective modes and capability degradations;
- file ownership, generators, and hand-owned/protected zones;
- language rules by file and audience;
- authorized source inventory, health evidence, and any progress markers the case defines;
- linked reference documents and root payment records;
- conventions, traps, open questions, and user emphasis.

## 1. Check

Select every applicable role and state omissions:

| Role | Mandate | Omit only when |
|---|---|---|
| `facts` | Verify material claims against primary sources. | Never |
| `consistency` | Find contradictions and stale cross-references. | Never |
| `conventions` | Enforce repository and case rules. | Never |
| `blindspots` | Find missing obligations, risks, and dependencies. | Never |
| `maths` | Recompute totals, dates, rates, counts, and derived values. | No derived values |
| `language` | Enforce declared language by file and audience. | Never |
| `greenfield` | Keep canonical files current and history properly confined. | Pure append-only log |
| `tasker` | Propose complete structured tasks; never write them. | Never |

A claim is material when acting on it could change money, timing, legal/contractual duties,
external communication, attendance, safety, privacy, ownership, task priority, or a derived fact.

Give every role the same brief, one mandate, the guardrails, and the exact structured return
contract from [references/protocols.md](references/protocols.md). Require null/empty values rather
than omitted keys. `facts` and `maths` must show source locations and calculations. `tasker` returns
proposed YAML text based on [references/tasks-contract.md](references/tasks-contract.md); it does
not write. It must also emit one `tasker-*` finding per proposed task and per analysis invariant so
the adversary can judge its evidence, dates, priority, and dependency edges.

Before using a connected source, confirm authorization and the `cases/RUNBOOK.md` health signals.
Never interpret silence as evidence from an unhealthy or unverified source.

Challenge every checker report using the adversary contract in
[references/protocols.md](references/protocols.md). Track failed checkers, failed adversaries, and
unjudged IDs explicitly. Silence is not a clean result. Redispatch when possible; otherwise perform
and disclose main-agent self-review.

## 2. Merge, triage, and decide

1. Drop refuted findings but retain a kill list.
2. Verify every unjudged finding directly before retaining it.
3. Merge duplicate findings into defects; count defects, not reports.
4. Reconcile conflicting fixes into one final edit sequence.
5. Apply adversarial severity/fix corrections.
6. Sort by consequence, then by file.

Gather genuine choices, untouchable findings, and questions into one decision round. Explain each
option's practical consequence. Findings with one source-backed answer need no question.

Under `--dry-run`, report the worklist and stop.

## 3. Fix with one writer

Pass the consolidator the brief, ordered defects, source paths, decisions verbatim, task proposal,
and guardrails. Require it to:

- reopen every cited source;
- fix only the worklist and escalate new discoveries;
- rewrite current-state lines rather than append progress narration;
- move superseded/circulated wrong facts to the locally defined record;
- rerun generators rather than hand-edit generated files;
- use absolute dates, explicit currencies, clear ownership, and working pointers;
- update structured tasks only after factual fixes.

Discover history, wrong-facts, and prose-task authorities from local instructions; do not invent
them. Put `tasks.yaml` at case root unless local rules define another location. A case with no open
work gets an empty task list unless local rules forbid structured tasks. Synchronize a prose task
view only when one is locally defined.

Validate task data against [references/tasks-contract.md](references/tasks-contract.md) and
[references/tasks.schema.json](references/tasks.schema.json). If no JSON Schema validator exists,
perform every invariant manually and disclose that validation was manual.

If compression is enabled, capture a patch or isolated recoverable baseline limited to candidate
files, then start the compressor only after the consolidator finishes. Require it to:

1. inventory atomic facts;
2. deduplicate and tighten without changing qualifiers or provenance;
3. preserve protected zones, history, documents, journal, and tasks;
4. rebuild the inventory without consulting the first one;
5. compare inventories and revert lossy edits using only the scoped baseline.

## 4. Verify

Treat writer failure as potentially partial. Inspect before retrying.

1. Compare current VCS state and diff with declared files and the pre-writer baseline.
2. Read the full diff, especially deletions and qualifiers such as “except”, “only if”, “before”,
   “at least”, and “not”.
3. Reopen two or three high-consequence sources and check case text directly.
4. Rerun affected generators and validators; confirm generated output is idempotent.
5. Validate task schema, unique/stable IDs, references, cycles, dates, provenance, and any locally
   defined prose/YAML agreement.
6. Review escalations, failed roles, degraded source coverage, and unverifiable claims.
7. Revert compression unless the main agent independently proves it lossless.

If no subagents exist, “independently” means a fresh procedural pass that rereads sources and the
diff without relying on the writer's report.

If material fixes were made, run one convergence check using affected checker roles only, without a
writer. Stop after round two; failure to converge needs a user decision.

## 5. Commit and report

Commit only when authorized and supported. Stage intended files only; inspect staged names and diff;
scan for plaintext secrets, hook-added files, unrelated changes, and sensitive spill beyond the
case's established tracked scope. If a hook changes or stages other files, stop and reconcile.
Create one task-scoped commit. Never push automatically.

If commit/VCS is unavailable, preserve the verified diff or artifact and report its location. If
`--no-commit`, leave changes unstaged unless local instructions require otherwise.

Report:

1. effective mode and capability degradations;
2. defects fixed by severity and file;
3. user decisions and structural changes;
4. compression before/after and independent lossless verdict;
5. residual findings and unverifiable claims, with the source needed for each;
6. escalations, killed findings, failed roles, and convergence result;
7. commit or saved-artifact identifier, if any.

Keep the report concise; the case, source pointers, and structured tasks carry the detail.
