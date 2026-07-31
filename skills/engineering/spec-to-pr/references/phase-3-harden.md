# Phase 3 — HARDEN

The plan is a set of claims about a codebase you only partly read. Hardening checks those claims
against the code and hunts for the collateral damage the plan doesn't mention. This is the phase
that catches "add a column to `users`" when six services read that table.

It also closes with a structural sweep — the pass that hunts what claim verification cannot see:
latent ambiguity, missing contracts, unstated invariants, unreachable states. Both halves live in
one sibling skill, so this phase is one call.

## The call

Run `/engineering-perso:plan-hardening --fix <plan-file>` — with **`--fix`**, naming the plan
file explicitly, and **without `--fast`**.

- **`--fix`** — without it the skill reports and stops, which is the wrong shape here: this
  phase's job is to leave a *corrected* plan behind, and the loop that re-verifies after each
  round of fixes is where a plan actually converges.
- **no `--fast`** — that flag suppresses the skill's Step 5, its closing structural sweep. That
  sweep is the pass that hunts what claim verification can't see: latent ambiguity, missing
  contracts, unstated invariants, unreachable states. This pipeline used to run it as a separate
  phase of its own; it doesn't any more, so suppressing it here would drop it entirely.
- **the plan file, by path** — the skill can discover a plan from conversation, but you know
  exactly which file you wrote in Phase 2. Name it.

**There is no fallback.** `plan-hardening` is a sibling skill in this plugin; if it isn't in this
session's skill list, the install is broken (`agents-doctor` diagnoses it) — stop and say so. Do
not substitute an inline pass: it would produce a receipt claiming this phase ran when the
rigorous version didn't.

## The freeze still holds

This is where Rule Zero ([`rule-zero-no-code.md`](rule-zero-no-code.md)) is most tempting to
break: hardening's whole job is finding real defects, and a found defect *feels* like something to
go fix. It isn't — not yet. **"Fix" in this phase means amend the plan, never touch the code.** A
change you make here belongs to no task, so no implementer owns it and no reviewer reviews it.
Write the paragraph; **Phase 4** writes the code.

`plan-hardening` is read-only on the codebase by its own guardrail, and its fixes land in the plan
file. That matches the freeze exactly — but if you dispatch any subagent of your own around this
phase, paste the canonical rule block into its prompt.

## Loop until clean

The loop lives *inside* `plan-hardening` now: it fixes every critical/major finding, re-runs, and
stops when a round produces no fixes — then sweeps, and re-converges if the sweep changed
anything. Your job is to read its convergence report, not to run your own rounds on top.

Watch for a **plateau** in what it reports back: if round after round keeps surfacing the same
serious findings, stop and surface what's left rather than grinding — a plan that won't converge
is telling you something the next round won't fix.

Minor/nice-to-have findings don't block; carry them to the Phase-9 handoff.

**Exit:** a hardening pass with no critical/major findings, including a clean closing sweep (or a
plateau reached and the remainder surfaced).

**Exit receipt example:**
`✅ Phase 3 (HARDEN) — engineering-perso:plan-hardening --fix — 3 rounds: 5 major → 2 major → 0, closing sweep clean; plan amended (migration back-fill, cache invalidation)`
