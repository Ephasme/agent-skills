---
name: spec-to-pr
disable-model-invocation: true
description: >-
  Drive one specification or ticket all the way to a reviewed pull request: understand it,
  brainstorm the approach when it's open, plan it, harden the plan against the codebase,
  implement it task by task through a subagent build loop, verify, open the PR, and fix
  findings until it is clean. Use when the user hands over a unit of work to take to
  completion — a raw spec (pasted or a file path), a Notion page/ID, a GitHub Issue or
  Project item, or a Linear issue — and asks to take it to a PR, ship it, implement it end
  to end, or drive it from spec to merge. It commits, pushes, and opens PRs, pausing to
  confirm those unless you pre-authorize hands-off completion.
---

# spec-to-pr — from specification to a reviewed PR

Take one specification and carry it the whole distance: read and ground it, plan it,
harden the plan, implement it, prove it works, open a PR, get it reviewed, and fix findings
until the PR is clean — then hand it back with a summary. The value is in the *gates between
phases*: each step refuses to advance on a shaky foundation, so a misread requirement or a red
test never silently rides through to a merged PR.

This skill **owns** the phases at the heart of the pipeline — planning (Phase 2), the per-task
build loop (Phase 4), and verification (Phase 5) are procedures it carries inline. The two it
delegates go to its own siblings in this plugin: **`engineering-perso:plan-hardening`** hardens
the plan (Phase 3) and **`engineering-perso:two-axis-review`** reviews the finished branch
(Phase 7). Both are hard requirements, not preferences — see the operating rules. Nothing here
depends on a third-party skill, and nothing here runs a dynamic multi-agent workflow runtime —
the fan-out that remains is plain parallel agent dispatch, where the work is genuinely parallel.
It runs only when you invoke it explicitly — it pushes branches and opens PRs, which must never
happen on a guess.

## RULE ZERO — no code before Phase 4 (absolute, overrides everything below)

**No agent — the orchestrator included — writes a line of product code before Phase 4
(IMPLEMENT).** Phases 0–3 are a **code freeze**; it lifts at Phase 4 and stays lifted for 4–8.

It outranks every other instruction in this skill, and every mode: plan mode or not,
auto-accept-edits, a hands-off pre-authorization, a subagent that "was only exploring", a fix
that is one obvious line. Nothing licenses an early edit.

Why it is absolute: this pipeline's whole value is that the plan gets attacked (Phase 3)
*before* anything is built. Code written earlier skipped that — it belongs to no task, so no
implementer owns it, no reviewer reviews it, and it rides into the PR as unreviewed work
everyone downstream assumes was vetted. A change you are certain of in Phase 3 costs one
paragraph in the plan file; the same change smuggled into the tree costs the pipeline its
guarantees.

**Enforcing it, every run:**

- **Paste the canonical rule block from [`references/rule-zero-no-code.md`](references/rule-zero-no-code.md)
  verbatim into every subagent you dispatch in Phases 0–3**, whatever its job. Assume no agent
  knows this rule unless you tell it.
- **Prefer read-only agents** (`Explore`) for exploration — a tool the agent doesn't have is a
  rule it cannot break.
- **If an agent broke the freeze**, revert the edit, say so, and re-enter the change as a plan
  amendment. It never reaches Phase 4's base commit.
- **Check the tree before Phase 4 launches** — `git status --porcelain` shows nothing but the
  plan file.

That reference is the single source for what counts as code, the two things you *may* write, and
what to do when you think you need an exception.

## At a glance

```
                      ┌──────────────── CODE FREEZE (Rule Zero) ─────────────────┐
0  IDENTIFY INPUT     │ which ticket/spec, from where                            │
1  UNDERSTAND         │ read + ground in code; restate; GATE: ask if unclear     │
1.5 BRAINSTORM        │ if the design space is open: brainstorm (else skip)      │
2  PLAN               │ write the plan (plan mode): header, tasks, contracts     │
3  HARDEN             │ plan-hardening --fix — claims, collateral damage, and    │
                      │ its closing structural sweep, loop-until-clean           │
                      └───────────────────────────────────────────────────────────┘
4  IMPLEMENT      ← ─ the freeze LIFTS here, and only here ─ ─
                      owned per-task loop: fresh implementer per plan task, two
                      parallel reviewers (spec ‖ quality) after each
5  VERIFY             → full build/test/lint must pass, with evidence
6  PR                 → GATE: confirm before push & PR; link the ticket
7  REVIEW             → two-axis-review: Standards ‖ Spec, in parallel
8  FIX FINDINGS       → address all, push, re-review, loop-until-clean
9  HANDOFF            → summary, PR link, leftovers → back to the human
```

## Before you begin — the phase ledger (mandatory)

This pipeline only works if every phase actually runs, in order, with its gate honoured. To
make that auditable instead of best-effort, **do these two things — they are not optional:**

1. **Open the ledger first.** Before Phase 0, call **TodoWrite** with all the phases
   (0–9, including the conditional Phase 1.5) as separate items, in order. This is the first action the skill takes — before
   reading the ticket, before any tool call. The ledger stays in front of you for the whole
   run so a phase can't quietly fall off.

2. **Advance one phase at a time, and only on a receipt.** Exactly one phase is
   `in_progress` at any moment. You may mark a phase `completed` **only after** you have
   printed its **exit receipt** (see the operating rule below) — the receipt *is* the
   completion criterion. Then move the next phase to `in_progress`. Do not batch-complete,
   do not skip ahead, and do not mark a phase done because it "probably would have passed".

The only sanctioned deviations from strict 0→9 order are the ones the phases themselves
document: **Phase 1.5** is conditional and may be skipped (say so, with the receipt noting
*why*), and a failed gate
sends you **back** to an earlier phase — **Phase 4** (a task the implementer can't complete
because the plan is wrong) back to Phase 2, **Phase 5** (red build) back to Phase 4, **Phase 8**
(review findings) back to Phase 4 and then 5. When you go back, **re-open that todo**; don't
leave it falsely complete. Any other skip is a bug in your execution, not a shortcut.

## Operating rules (apply to every phase)

These behaviours recur throughout; internalize them once so each phase stays short. **Rule Zero,
above, outranks every one of them.**

- **Print an exit receipt before advancing.** Every phase ends with one line of the form
  `✅ Phase N (<NAME>) — <which path ran> — <evidence>`, e.g.
  `✅ Phase 5 (VERIFY) — ran pnpm test+lint+build — 142 passed, 0 failed (output above)`, or
  `✅ Phase 3 (HARDEN) — engineering-perso:plan-hardening --fix — 2 rounds, closing sweep clean`, or
  `✅ Phase 4 (IMPLEMENT) — owned per-task loop, 7 tasks, both reviewers clean on each`.
  The receipt names the skill that ran and points at the concrete evidence that the phase's
  stated **Exit** condition is met. No receipt → the phase isn't done → you may not move on.
  This is what makes a skipped step impossible to hide.

- **Loop-until-clean — converge, don't count.** Whenever a phase says "fix all issues", it
  means: fix every **critical/major** finding, then re-run the reviewer; repeat until a clean
  pass (no critical/major). Watch for **diminishing returns** — if a round stops reducing the
  serious findings, or the same ones keep resurfacing, you're plateauing: **stop and surface
  what's left to the human** with what you tried, rather than grinding. Convergence (or a clear
  plateau), not a fixed number of rounds, is the stop signal — and it's what keeps "clean"
  meaning clean. Minor/nice-to-have findings don't block; carry them to the handoff.

- **A missing sibling skill stops the run — it is not a cue to improvise.** The only skills this
  pipeline invokes are its siblings in this plugin: `engineering-perso:plan-hardening` (Phase 3)
  and `engineering-perso:two-axis-review` (Phase 7). If one is not in this session's skill list,
  that is a broken install (a plugin left out of the dotfiles, or a profile symlink never
  created — `agents-doctor` diagnoses it), **not** a degraded environment to work around.
  **Stop, name the missing skill, and say the run can't be trusted without it.** An inline
  substitute would produce a receipt that claims a phase ran when the rigorous version didn't,
  which is the one failure this pipeline exists to prevent. Every receipt names the skill that
  ran.

- **Fan-out cost guard — more than ~20 agents, confirm first.** Phase 4 is where the agents go:
  an implementer plus **two parallel reviewers** (spec ‖ quality) per plan task — budget `3T` at
  the floor and `~4T` in practice for `T` tasks, fix rounds included. Phase 7 adds exactly two.
  Invoking this skill opts you into multi-agent work in general, but a big fan-out costs real
  tokens: if a run would spawn **more than ~20 agents**, say the number and **confirm with the
  human before launching**. (The runtime also caps concurrency and total agents, but that's a
  backstop, not a substitute for the heads-up.)

- **Always set a subagent's model *and* effort — where you're the one dispatching.** An
  omitted `model` inherits the orchestrator's (Opus 4.8); an omitted `effort` inherits the
  session's (`xhigh`). This binds Phase 4's per-task loop — an implementer and two reviewers per
  task, all dispatched by you — so pick each one's model per Phase 4's Model Selection section
  (mechanical tasks cheap, judgment tasks standard), and Phase 7's two axes. Set it explicitly
  every time; the default is the most expensive model.

- **Confirm before anything irreversible or outward-facing.** Pushing a branch, opening a
  PR, and posting review comments leave your fingerprints on shared infrastructure. Pause
  for explicit go-ahead before those, unless the human pre-authorized hands-off completion
  ("just take it all the way", "don't stop to ask"). Local work (reading, planning,
  editing, committing locally) needs no such pause — Phase 4's implementers commit locally
  without asking.

- **Evidence before assertions.** Never say a build passed, tests are green, or review is
  clean without showing the command and its output. "Tests pass" is a claim; the pasted
  test summary is evidence. If something failed or you skipped a step, say so plainly.

---

## Phase 0 — IDENTIFY INPUT

Determine *what* to work on and *where it lives* before anything else. Accept any of: a
**Notion** page (URL or ID), a **GitHub** Issue or Project item, a **Linear** issue, or a
**raw spec** (pasted or a file path). Detect the source from what was given — URL shape, ID
pattern, or "here's the spec" — and read it through the right channel. If the user gave
nothing to work from, **ask** which ticket or spec to drive; don't pick one.

- **IF the source's MCP is connected** → read the ticket through it.
  **ELSE** → use the CLI (`gh`) where one exists, otherwise ask the user to paste the ticket.

**Exit:** the ticket id/key, its full requirement text, and its linked context are in front
of you. → [`references/phase-0-identify-input.md`](references/phase-0-identify-input.md)

## Phase 1 — UNDERSTAND

Read the ticket **in full**, then ground it in reality: explore the affected code, folders,
and docs so your understanding is anchored in how the system actually works, not how the
ticket imagines it. Then restate the goal, scope (in *and* out), acceptance criteria,
affected components, and open questions.

**GATE:** if anything is unclear or under-specified — fuzzy acceptance criteria, an undefined
term, a decision the ticket leaves open — **stop and ask the human targeted questions.** Do
not invent requirements to fill the gap; a confidently wrong assumption here is the most
expensive error in the pipeline, because every later phase compounds it.

**Exit:** a written restatement, with open questions resolved.
→ [`references/phase-1-understand.md`](references/phase-1-understand.md)

## Phase 1.5 — BRAINSTORM (conditional)

Phase 1 pins down *what* the ticket wants. This step is where you work out *how* — but only when
that's genuinely open. Explore the candidate approaches, weigh their trade-offs, and settle on a
direction **before** Phase 2 freezes it into a task list, so the plan commits to a considered
design rather than the first one that came to mind.

**You decide whether it runs — that judgement is the point of making it conditional.** It earns
its place when the ticket fixes an *outcome* but leaves the *approach* open: several viable
designs with real trade-offs, a data-model or API-shape choice that will ripple through every
task, a "extend X or introduce Y?" fork the plan would otherwise resolve by accident. **Skip it**
when the ticket is already prescriptive, the change is small and well-bounded, or there's one
obvious way to build it — and say you skipped it and why. When you're unsure, lean toward a short
brainstorm: it's cheap insurance against planning the wrong thing well, which is the failure mode
the rest of this pipeline is *worst* at catching (Phase 3 hardens the plan you have, not the
one you didn't consider).

Lay out 2–3 candidate approaches, name the trade-offs and the risk each carries, and choose one
with a stated reason.

Still inside the code freeze (Rule Zero): brainstorming is discussion, not construction. Its
output is a **chosen direction that feeds Phase 2's plan** — never code, never an edit to the
tree, not even a "quick spike". If it surfaces a new open question about the *requirement* rather
than the design, that's a signal to loop back to Phase 1's gate and ask the human before planning
on a guess.

**Exit:** a chosen approach with its rationale, ready to plan against — or an explicit, justified
skip. → [`references/phase-1.5-brainstorm.md`](references/phase-1.5-brainstorm.md)

## Phase 2 — PLAN

Turn the understanding — and the approach chosen in Phase 1.5, if it ran — into a concrete,
ordered implementation plan: numbered tasks, the files each touches, the tests, and the risks.

Write it yourself in plan mode (Rule Zero — no code), to the structure Phase 4 reads directly: a
header with a **Global Constraints** block, numbered `### Task N` sections carrying per-task files,
named contracts, and TDD steps, with no placeholders. The Global Constraints block is load-bearing —
Phase 4 hands it to both task reviewers verbatim.

**Exit:** a written plan file exists, with the header, Global Constraints, and `### Task N` sections.
→ [`references/phase-2-plan.md`](references/phase-2-plan.md)

## Phase 3 — HARDEN

Verify the plan's claims against the codebase, surface the collateral damage it doesn't handle,
and close with a structural sweep for the ambiguity and missing contracts that would let two
engineers build incompatible things. **"Fix" here means amend the plan file — never the code**
(Rule Zero); a real defect found in this phase is exactly the success case, and it gets written
down, not patched.

Run **`engineering-perso:plan-hardening` with `--fix`** on the plan file, and **without
`--fast`** — `--fix` makes it apply fixes and loop until a round finds nothing instead of stopping
at a report, and omitting `--fast` keeps its closing structural sweep, which this pipeline no
longer duplicates in a phase of its own. A missing sibling stops the run (Operating rules).

**Exit:** a hardening pass with no critical/major findings, including a clean closing sweep (or a
plateau reached and the remainder surfaced).
→ [`references/phase-3-harden.md`](references/phase-3-harden.md)

## Phase 4 — IMPLEMENT  *(the code freeze lifts here — and only here)*

Run the plan through this skill's **owned per-task loop**: a fresh implementer per plan task, two
independent reviewers in parallel after each — one for spec compliance, one for code quality — a
fix loop until that task is clean, then the next. One task in flight at a time; no
worktree-per-task swarm, no task graph, no wave gates. **Stop once the last task's review comes
back clean** — no whole-branch review and no merge/PR/discard menu here; Phases 5–9 of *this*
skill own verification, the PR, the whole-branch review, and the handoff.

- **Primary** → dispatch the loop via the **Agent** tool, one task at a time in plan order, using
  the bundled implementer and task-reviewer prompt templates and the `task-brief` /
  `review-package` scripts. The reference file carries the full procedure.
- **Fallback (no subagent dispatch at all)** → implement the plan yourself, task by task, and say
  so — a self-reviewed implementation is materially weaker evidence.

Before dispatching anything: verify the freeze held (`git status --porcelain` shows only the
plan file), create the feature branch (never build on the default branch — this is content-free,
so it's allowed before the freeze lifts), and run the **pre-flight gate** — count the plan's
tasks, project the agent count (`3T` floor), and pause for go-ahead unless hands-off
pre-authorized (subject to the **fan-out cost guard**, Operating rules).

**Exit:** every task in the plan implemented and reviewed clean (spec + quality), committed on
the feature branch — nothing pushed or opened yet.
→ [`references/phase-4-implement.md`](references/phase-4-implement.md)

## Phase 5 — VERIFY

Run the project's **full build, tests, and lint** — the whole suite, not just what Phase 4's
task-scoped reviews touched — and confirm they pass **before claiming anything**. Evidence
before assertions (Operating rules).

Run the project's own build/test/lint (discover them from `package.json` / `Makefile` / `justfile` /
CI config) and read the output. The iron law: **no completion claim without fresh evidence from a
command run in this message** — "should pass" and a linter that's green are not evidence.

**GATE:** if anything is red, go **back to Phase 4** and fix it — do **not** proceed to a PR on
a broken build. If it can't be made green (environmental, flaky, out of scope), stop and tell
the human exactly what's failing rather than papering over it.

**Exit:** build/test/lint green, with the output shown.
→ [`references/phase-5-verify.md`](references/phase-5-verify.md)

## Phase 6 — PR

The branch and its commits already exist — Phase 4's implementers commit as they go — so this
phase tidies the history if it needs it, **pushes**, and opens a PR whose description links the
ticket, summarizes the change, and carries the Phase-5 verification evidence.

**GATE — confirm before push and PR** unless the human pre-authorized hands-off completion.
Pushing and opening a PR are outward-facing (Operating rules); the local branch and commits
were not.

**Exit:** an open PR, correctly titled and linked, with verification evidence in its body; its
URL captured for the handoff. → [`references/phase-6-pr.md`](references/phase-6-pr.md)

## Phase 7 — REVIEW

Get the whole assembled change reviewed by reviewers that are not you, along two axes that run in
parallel and are reported separately: **Standards** (does it follow this repo's documented
standards, plus the code-smell baseline?) and **Spec** (does it faithfully implement what was
asked — nothing missing, nothing extra, nothing built wrong?).

Run **`engineering-perso:two-axis-review`**, handing it the fixed point (the feature branch's
merge-base) and the spec (the hardened plan, backed by the ticket's acceptance criteria) so it
skips its own discovery. Hand it the Minor findings deferred from Phase 4's task reviews as well,
for re-triage now that they can be seen together.

**Exit:** two reports, findings enumerated and triaged by severity.
→ [`references/phase-7-review.md`](references/phase-7-review.md)

## Phase 8 — FIX REVIEW FINDINGS

Address **every** finding, push the fixes, and **re-review until clean** (loop-until-clean).
Re-run Phase 5's verification after each fix round so you don't trade a review nit for a broken
build. Posting review-comment replies is outward-facing — confirm first unless pre-authorized.

**GATE:** critical/major findings block; minor/nice-to-have go to the handoff notes. A fix that
touches real behaviour goes back through **Phase 4 → 5**, not straight to a push.

**Exit:** a review pass with no critical/major findings (or a plateau reached + surfaced).
→ [`references/phase-8-fix-findings.md`](references/phase-8-fix-findings.md)

## Phase 9 — HANDOFF

Close the loop with the human: **what was built** (tied back to the acceptance criteria), **the
PR** (link + current state: checks green? review clean?), and **leftovers** (deferred decisions,
follow-up tickets worth filing, anything consciously left out of scope, any findings surfaced at
a plateau). Then hand it back.

**Exit:** the summary is delivered. Done.
→ [`references/phase-9-handoff.md`](references/phase-9-handoff.md)

---

## If a phase can't proceed

Honesty beats a clean-looking result. If a gate can't be satisfied — the spec stays ambiguous
after questions, a review loop plateaus without converging, a task fails and the plan is wrong,
the build won't go green, an MCP/skill you need is absent with no workable fallback — **stop at
that phase and report** where you are, what's blocking, and the options, rather than forcing
past it. A pipeline that stops at a real obstacle is more useful than one that produces a
confidently broken PR.
