# Micro-test: output-contract wording (Task 8)

Compiled 2026-08-19. Tests whether D6's output contract, presented as a positive recipe (Arm B,
shipped in `SKILL.md`), produces more consistent, compliant output than the same requirement
presented as a list of prohibitions (Arm C), against a no-guidance control (Arm A). Per
`writing-skills`, this runs *before* the full scenario re-run (Task 9) — verify wording first,
scenarios are the final gate.

## Task

Same for all 15 reps: "Two dehumidifiers I'm considering: (1) one on Amazon with 4.8 stars from
12,142 ratings. (2) a competing model with 5.0 stars from 14 ratings. Which is the safer buy?" —
S2's pinned histogram (Item A: 4.8★/n=12,142) plus a new small-`n` competitor (5.0★/n=14), designed
to tempt exactly the naive-mean-wins failure the Dirichlet lower bound corrects. Five fresh
single-shot reps per arm, no coordination between reps.

- **Arm A** — no shape guidance at all.
- **Arm B** — the exact D6 recipe from `SKILL.md`, presented as a required shape.
- **Arm C** — the same content, converted to six prohibition-style rules ("don't bury the verdict,"
  "don't rank without naming criteria," etc.).

## Scoring

**Compliance** (0–7): one point per D6 part present, in order, correctly filled: Verdict (with
confidence + depth), Criteria (tagged `[measurable]`/`[experiential]`, before any ranking), Evidence
(a table with tier/funder/date), Crowd data (n/histogram/base-rate-with-year/computed-bound/flags),
Against it (present, even if the disconfirmation search came back empty), What-would-change,
Cheapest-next-check. **Variance**: how many distinct structural shapes appear across an arm's 5
reps (same section labels, same order, same field completeness = one shape).

## Results

| Rep | Compliance /7 | Notes |
| --- | --- | --- |
| A1 | 1 | Verdict-ish opener, prose reasoning, bulleted checklist. No tagged criteria, no Evidence table, no labeled Crowd-data/Against-it/What-would-change sections. Independently invoked "Wilson score interval" as a concept but never computed one. |
| A2 | 1 | Same shape as A1. |
| A3 | 1 | Same shape as A1 and A2. |
| A4 | 1 | Same shape again — brand-comparison bullets substituted for Evidence table. |
| A5 | 1 | Same shape; explicitly flags fake-review/timing red flags in prose, never in a structured field. |
| B1 | 7 | All 7 parts present and labeled. Notably **refused to compute a numeric Wilson bound** ("a fabricated-precision shortcut... I'm retracting an earlier draft that did this") because no real histogram was given — used the contract's own escape hatch ("say the bound is uncomputable and why") correctly instead of forcing a number. |
| B2 | 7 | All 7 parts; computed Wilson bound via a stated `(mean−1)/4` proxy with the approximation flagged; found the real CPSC Gree-dehumidifier fire-recall as its "Against it" evidence. |
| B3 | 7 | All 7 parts; explicitly separated "manipulation flags" for each product; cited the same CPSC recall independently. |
| B4 | 7 | All 7 parts, cleanest execution — Evidence table rows carry tier, funder and date exactly as specified; Crowd data correctly flags "histogram shape: unknown (not retrievable...)" rather than inventing one. |
| B5 | 7 | All 7 parts; cross-checked the Wilson bound against an IMDb-style shrinkage calculation as a second method — beyond what was asked, still inside the contract shape. |
| C1 | ~3.5 | Verdict-like opener with confidence stated in prose, not a labeled field; criteria numbered but untagged; no Evidence table (inline citations in prose); Wilson bound computed in an unlabeled "math" section; disconfirming evidence present but not under an "Against it" label; what-would-change and cheapest-check merged into one combined section. |
| C2 | ~3.5 | Same shape as C1: prose-embedded confidence/depth, untagged criteria list, no table, unlabeled disconfirmation section, merged closing section. |
| C3 | ~3 | Same family shape as C1/C2, one fewer distinguishable section. This rep's own returned JSON included the literal fields `"arm": "C"` and a `"condition"` description of the experiment — a demand-characteristic artifact worth flagging (see Caveats) even though the prose answer itself was scored blind to that leakage. |
| C4 | ~3 | Same family shape; disconfirmation and "what would change" sections combined into one, unlike C1/C2's separation. |
| C5 | ~3 | Same family shape; six section headers versus C4's five — the specific header count and order drifts rep to rep in a way Arm B's did not. |

**Arm means:** A = 1.0/7, variance = low (one consistent essay shape, missing the same elements
every time). B = **7.0/7**, variance = low (identical 7-part labeled structure, same order, every
rep). C = ~3.3/7, variance = **moderate** (a shared family resemblance — verdict-first, stated
criteria, a disconfirmation pass, a closing checklist — but the exact section count, order and
labels differ rep to rep: 5–6 headers, sometimes merged, never the specific 7-field structure).

## Verdict

**Arm B wins on both compliance and variance — ship it as-is.** This matches `writing-skills`'
documented finding that a positive recipe outperforms an equivalent prohibition list. No change to
`SKILL.md`'s Output contract section; Step 2's "delete if the control already complies" clause does
not apply (Arm A's compliance is 1/7). The `writing-skills`-mandated contingency for "if arm C wins,
the evidence overrides the design" does not fire — B beat C decisively on the metric that mattered
(labeled-shape compliance), not narrowly.

**A secondary finding, not part of the win/lose verdict but worth recording:** the underlying
research diligence was already strong in *all three* arms — every one of the 15 reps, unprompted,
found and correctly used the real CPSC recall history for Gree-manufactured dehumidifiers as
context, and most computed some form of small-sample correction even without being told to. The
contract's job, empirically, is not to bootstrap missing research behaviour from nothing — it's to
make research that was already happening **legible and complete**: forcing criteria before ranking,
forcing a labeled uncertainty statement, forcing the disconfirming evidence into a fixed, never-omitted
slot instead of leaving it as one paragraph among several. That is exactly D6's stated rationale for
treating `Against it` as a structural slot rather than a prose reminder — this run is direct evidence
for it, not just an inference from `writing-skills`.

## Caveats

- C3's leaked `"arm": "C"` field suggests at least one subagent inferred the experimental framing
  despite the task text giving no indication of one. This is a known risk of dispatching micro-test
  reps as subagents rather than raw API calls (per `writing-skills`' own recommended method) — it was
  not judged to have contaminated the *content* of C3's answer (which matches C1/C2/C4/C5's family
  shape closely), but a future micro-test on this skill should prefer single-shot API calls where
  available to remove the risk entirely.
- All 15 reps ran with real web search enabled and found real information (the CPSC recall is a
  genuine, verifiable event, not a fabrication) — this micro-test measures *shape and compliance*,
  not factual accuracy, which Task 9 and Task 11 check separately.
