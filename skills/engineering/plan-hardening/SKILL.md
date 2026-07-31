---
name: plan-hardening
description: >-
  Hardens an engineering plan against reality — verifies every claim it makes against the
  codebase and the docs, surfaces the collateral damage it doesn't handle, and closes with
  a structural sweep for the ambiguity, missing contracts, and unstated invariants that claim
  verification cannot catch. Reports by default and changes nothing; pass --fix to also
  apply fixes and re-review until a round finds nothing. Use when the user hands over a
  plan, design doc, RFC, ADR, refactor proposal, or migration document and asks anything
  skeptical of it — harden, stress test, poke holes in, sanity check — even without the
  word "plan". Also covers the near-final structural read before handoff — "final pass",
  "last round before implementation", "anything still ambiguous in here", "what would break
  if I gave this to an engineer tomorrow" — which the closing structural sweep (Step 5) is
  built for. Also when another skill needs a plan verified against code before
  implementation. Pass --fast to skip the closing structural sweep.
---

# Plan Hardening

Run the plan through rounds of review and fixes until it holds up to reality. Each round verifies claims, surfaces findings, gathers any needed clarifications, applies fixes, and re-reviews — and stops when a round produces no fixes. Once that loop converges, a final closing structural sweep (Step 5) looks for the out-of-the-box defects that survive claim verification.

## Modes

| Invocation | Behaviour |
|---|---|
| *(bare)* | **REPORT** — the default. One pass: verify claims, assess collateral damage, triage by severity, run the closing structural sweep, then **stop and report**. Never edits the plan, never asks a question, never loops. |
| `--fix` | **FIX** — verify, ask about genuine judgement calls, apply fixes, and re-review until a round produces no fixes; then the closing sweep, re-looping if the sweep changed anything. |
| `--fast` | Orthogonal to both: skip Step 5, the closing structural sweep. |

All four combinations are legal. **REPORT is read-only on the plan file itself**, not just on the codebase — the deliverable is a findings report the caller acts on, which is what makes the mode safe to run on a plan you don't own.

Say which mode ran, in the first line of the output.

**Invocation:** `plan-hardening [--fix] [--fast] [<plan-file>]`, however this agent invokes skills. A path argument names the plan directly and skips Step 0's discovery — which is how another skill should call this one, since a caller always knows its own plan file and shouldn't make this skill guess from conversational context.

## Guardrails

- **Read-only.** Verification means reading: open files, grep, fetch docs, run read-only queries — never write or execute code to settle a claim. A claim that needs more than a read-only lookup is beyond this skill's reach: flag it unverified and route it to Step 2 as a question. In REPORT mode this extends to the plan file: the whole skill run is read-only.
- **The plan stays a plan.** The deliverable is the plan's own text — its prose and its steps — made more accurate and more complete. A few lines of illustrative pseudo-code are fine when that's the clearest way to pin down an algorithm, data shape, or tricky sequencing: non-runnable, no imports, no error handling. Anything longer becomes a plan instruction instead (file, function, expected behavior) for an implementer to act on later.

## Step 0 — Locate the plan

**If the invocation carried a path argument, that is the plan.** Use it and skip discovery — a caller that names its own plan file should never have this skill guess from conversation. Everything below applies when no path was given.

Identify what plan is being hardened. Look in the current conversation and any uploaded files for a plan, design doc, refactor proposal, RFC, ADR, or migration document. If multiple candidates exist, ask the user which one (or which sections) to harden. If nothing is present, ask the user to share or paste the plan.

Work from the literal text. If the plan is a file, edit it in place; if it arrived as conversation text, write it to a file first and harden that file — the loop needs one artifact to converge on across rounds.

## Step 1 — Review the plan against reality

Walk the plan and surface findings of two kinds: claims that don't hold up against reality, and collateral damage the plan doesn't handle. Both feed the same list for Step 2 — capture them as you go, in either order.

**Verify every claim.** A "claim" is anything assertable: file paths, function names, API behaviors, data shapes, sequencing assumptions, performance numbers, library capabilities, configuration values, current-state descriptions ("X currently does Y"), or causal reasoning ("changing A will fix B"). For each, do exactly one of:
- **Read the related code** — open files, trace call sites, inspect schemas — when the claim is about the codebase.
- **Consult official documentation** — fetch the docs page, API reference, or changelog — when the claim is about a third-party library, framework, or platform. Prefer primary sources over blog posts.
- **Run a read-only query** — grep/search, a check-only linter or type-checker, a read-only DB or API query.
- **Flag it as an unverified finding** for Step 2 to ask about, when no read-only lookup can settle it.

Capture the source of each verification (file:line, doc URL, search result) as you go, and cite it in the output — the user shouldn't have to trust you on the verification itself. Judge each claim against its source, never against how plausible it sounds; plausible-sounding wrong claims are exactly what this loop exists to catch. If you have no verification tools at all, every empirical claim falls into the last bullet and goes to the user.

**Assess collateral damage.** For each step in the plan, consider what else it touches and whether the plan handles it:
- other call sites and consumers
- data integrity (migrations, in-flight records, idempotency)
- security and permissions
- backwards compatibility (clients, persisted state, wire formats)
- performance and scaling
- tests and CI
- observability (logs, metrics, alerts)
- rollout and rollback
- operational risk and blast radius

Anything the plan doesn't mention is a finding by default. Anything it does mention but handles in a way you'd push back on is a finding flagged as a judgment call for the user.

## Step 2 — Triage and ask

Rank every finding as **critical**, **major**, or **minor**:
- **Critical** — the plan won't work as written, will cause data loss or outage, or has a security flaw.
- **Major** — the plan will technically work but produces a meaningfully worse outcome or leaves significant risk unhandled.
- **Minor** — wording, polish, nice-to-haves.

**REPORT mode asks nothing.** There is no fix to gate on an answer, so every open choice becomes an entry in the report's *Open questions* section — the finding, the options, and the implication of each — for the caller to resolve. The rest of this step (ranking) applies in both modes.

For any critical or major finding where there's a real choice to make (tradeoffs, design preferences, scope decisions), ask the user before moving to Step 3. Use a structured multiple-choice prompt if this agent has one; otherwise ask in plain text with the options numbered. Gather every open question first and ask them in one round rather than dripping them one at a time. For each, state the finding, the options, and the implication of each option concretely.

Findings with a clear right answer don't need a question — they go straight to Step 3. Minor findings are noted for the final summary but not fixed.

If the user pushes back on a finding, re-verify against the source rather than deferring or doubling down. Findings can be wrong, and that's exactly why verification matters.

## Step 3 — Fix critical and major findings *(FIX mode only)*

**REPORT mode skips this step entirely** and proceeds to Step 5.

Apply fixes for every critical and major finding from Step 2, incorporating the user's clarifications where given. Every design decision that had a real choice in it should already have been triaged as a question in Step 2 — fix what the user settled, and raise anything new the same way rather than deciding it silently.

Leave minor findings as-is — they get noted in the final summary, not fixed in the plan.

After applying fixes, list what changed — briefly, e.g. "Plan step 3: corrected file path", "Plan step 5: added rollback section", "Plan step 7: removed, superseded by step 6" — so the user can see the diff at a glance.

## Step 4 — Stop or loop *(FIX mode only)*

**REPORT mode never loops.** Nothing changed, so a second pass would produce the same findings; go straight to Step 5 (or Step 6 under `--fast`).

- **If Step 3 applied no fixes this round** → the verify-and-fix loop has converged. Proceed to **Step 5** — unless invoked with `--fast`, in which case skip to **Step 6**.
- **Otherwise** → return to Step 1 and run another full pass on the updated plan. The fixes themselves are new claims and new steps that may have introduced new problems or new collateral damage.

If after 3 full rounds critical findings keep emerging, stop the loop and tell the user: the right answer is sometimes "this approach is fundamentally wrong; consider alternative X" rather than another round of patching.

## Step 5 — Closing structural sweep

Steps 1–4 prove the plan is *true*; they don't prove it's *unambiguous*. A plan can be accurate about every file, function, and API and still be built two incompatible ways by two competent engineers. This closing "think out of the box" pass hunts the defects that survive claim verification: latent ambiguity, hidden assumptions, missing failure paths, unstated invariants, unreachable states. It stays **read-only**, and every fix is still a plan edit, never code.

If the plan marks **hard constraints** separately from **open proposals**, treat them asymmetrically: a conflict between hard constraints is critical; an open proposal is a finding only when some allowable resolution of it would violate a hard constraint or create downstream divergence. If the plan uses no such convention, treat everything as a hard constraint unless the text marks it tentative.

**Pick your lenses.** On the first sweep, all eight lenses below are fair game — pick the two-to-four most relevant to the plan's risk profile (a state-machine-heavy plan pulls state-reachability and invariant; an integration-heavy plan pulls failure-mode and interface/contract). If this sweep is re-running after a prior sweep's fixes, pick at least two lenses the prior sweep didn't lean on — the point is to find what it missed. State which lenses you're using and why before producing findings, and work each selected lens over the *whole* plan before starting the next.

**Aim at the thin spots.** The claim-verification rounds (Steps 1–4) concentrate wherever the plan made the most checkable claims, leaving other sections lightly examined. Identify the sections those rounds touched least and spend disproportionate attention there — an under-scrutinized section is exactly where a structural defect survives to reach the implementer.

### The eight lenses

1. **Two-implementer divergence.** Where would two competent engineers building independently produce incompatible systems? Catches ambiguous data shapes, ordering, naming, types, defaults, edge-case behavior — choices the plan leaves without acknowledging them as choices. Apply: for each component or interface, write the smallest decision needed to write the first line of code; if the plan doesn't answer it, that's a finding.
2. **Hidden assumption.** What does the plan rely on without stating? Catches assumed ordering guarantees, idempotency, clock behavior, message uniqueness, delivery semantics, transaction isolation, encoding, timezone. Apply: read each step and ask "what must be true about the world for this to work?" — any answer the plan doesn't state is a finding. The tell is a verb that quietly assumes a property: "process", "store", "send", "retry".
3. **Failure-mode coverage.** For each external dependency, tool call, and DB transaction, what happens on failure, timeout, or partial result? Catches silent error fallthrough, missing retry/backoff, unhandled timeouts, partial-write recovery, unclear post-failure state. Apply: enumerate every external boundary; for each, locate the plan's handling of timeout, transient error, permanent error, partial success, malformed response. Silence on any is a finding.
4. **Invariant.** What must always be true, and who enforces it? Catches assumed-but-unstated invariants, invariants asserted with no owner, invariants an allowed operation can break. Apply: list every invariant; for each, find the step responsible for maintaining it, and trace it against every operation that mutates the relevant state.
5. **Interface / contract.** Between each pair of components, are inputs, outputs, preconditions, and postconditions specified? Are shared concepts defined identically everywhere? Catches drift in a shared term's meaning across sections, missing pre/postconditions, return values described in one place but not another. Apply: for each shared concept, scan every occurrence — mismatched definitions are findings; for each boundary, write `(inputs) -> (outputs) {pre, post}` and check the plan supports every field.
6. **State-reachability.** Enumerate the states the system can be in — is every transition handled, and are there trap or unreachable states? Catches missing transitions on error/retry/terminal events, unnamed implied states, states you can enter but not exit. Apply: draw the state graph; for each (state, event) pair confirm the destination is defined; run reachability from the initial state.
7. **Coherence.** Do any hard constraints conflict with each other or with an open proposal? Catches individually-reasonable constraints that are jointly unsatisfiable, proposals whose answer space includes constraint-violating options, drift between sections written at different times. Apply: pair-check the constraints; for each open proposal, enumerate plausible resolutions and check each against the constraints.
8. **Verifiability.** For each requirement, can the implementer or a reviewer tell from the built system whether it was met? Catches requirements too vague to test — "should be efficient", "must be robust", performance targets with no measurement procedure. Apply: for each requirement, propose the test or observation that would falsify it; if you can't, rewrite it as a measurable statement.

**High signal only.** Every finding needs evidence — quoted plan text, a cited conflicting section, or an official doc / established principle. Preference is not evidence: "I'd prefer pattern Y" is not a finding; "pattern X conflicts with the invariant in step 5" is. A lens that comes up clean is a useful result — say so and move on.

**Wiring back into the loop.** *(FIX mode.)* In REPORT mode the sweep's findings join the report alongside Steps 1–2's, and the skill proceeds to Step 6. In FIX mode, feed every critical or major finding through **Step 2** (triage and ask) and **Step 3** (fix), exactly as in the loop above.

- **If the sweep produced fixes** → the plan changed, so return to **Step 1** for a fresh verification round. The loop reconverges at Step 4 and re-runs this sweep, until a sweep comes up clean with nothing to fix.
- **If the sweep found nothing to fix** → proceed to **Step 6**.

## Step 6 — Wrap up

**REPORT mode** — the output *is* the deliverable. Lead with the findings, grouped by severity (critical, major, minor), each carrying its evidence (`file:line`, doc URL, or quoted plan text) and a **suggested** fix stated precisely enough for the caller to apply without re-deriving it. Then an *Open questions* section for every judgement call, and the residual-minor list. State that the plan was not modified, and whether the closing sweep ran or was skipped via `--fast`.

**FIX mode** — summarize what changed across all rounds (including the closing sweep), what residual minor items remain, and any explicit assumptions the hardened plan now rests on. Note whether the closing sweep ran or was skipped via `--fast`.

## Output style

- Lead with the findings — they're what the user is here for.
- Present the full updated plan at the end of each round (or a clearly-marked diff if it's very large). The user shouldn't have to mentally reassemble it from deltas.
