# GREEN verification — eight pinned scenarios, skill loaded

Compiled 2026-08-19. Task 9 of `docs/plans/2026-08-19-true-quality-skill.md`. Same eight pinned
scenarios as `baseline.md`, same inputs, this time with `skills/research/true-quality/` loaded and
followed. Full transcripts at `history://GreenS1`–`history://GreenS8`.

## Scoring matrix (Step 2)

**Contract-shape lines** (one per D6 part, all 8 scenarios): verdict-first-with-confidence-and-depth,
criteria-before-ranking, evidence-table-with-tier-funder-date, crowd-data-field-present (`none
observed`/`uncomputable` counts as present), against-it-non-empty, falsifiers-listed, cheapest-check.
**Process lines** (all 8): ownership-checked-before-corroboration, disconfirmation-search-run,
depth-matches-selection-rule. **Rating-specific lines** (required only for S2/S5/S6, the scenarios
that quote a rating): n, histogram, base-rate-with-year, computed-lower-bound.

| Scenario | Shape 7/7 | Process 3/3 | Rating-specific | Notes |
| --- | --- | --- | --- | --- |
| S1 laptop | 7/7 | 3/3 | n/a (voluntarily applied anyway to an incidental Zenbook rating: correctly flagged the histogram as JS-rendered/uncomputable and dropped confidence rather than using the bare 4.1 mean) | Depth: Standard, correct default. Found a real "frequently returned" flag and an independent battery-degradation finding as `Against it`. |
| S2 dehumidifier | 7/7 | 3/3 | 4/4 — n=12,142 ✓, histogram exact match to the pinned fixture ✓, base rate ~4.2–4.3★ dated and flagged secondary-sourced ✓, lower bound 4.75 computed via the script ✓ | Found the real CPSC Gree-dehumidifier fire-recall history unprompted as `Against it` — this exact finding recurred independently in S4's mattress run's disconfirmation search style, evidence the pipeline step is doing real work, not decoration. |
| S3 axios | 7/7 | 3/3 | n/a | Correctly scoped to the supply-side-only question per D8; corrected the pinned "40k+" premise to the real 109,237; found a genuine March 2026 supply-chain compromise via primary sourcing (Datadog Security Labs cross-checked against the maintainers' own GitHub comments). |
| **S4 mattresses (discipline gate)** | 7/7 | 3/3 | n/a | **Gate passed.** Depth explicitly named as Triage per the selection rule (time pressure + reversible purchase), real lookups run (CPSC, BBB, litigation trackers), verdict is a stated low-confidence toss-up — not silence, not a confident unverified pick. Independently surfaced `evidence-tiers.md`'s own Casper v. Sleepopolis hard case as directly relevant to discounting a quick listicle search right now. |
| **S5 Airbnb (base-rate scenario)** | 7/7 | 3/3 | 4/4 — n=200 ✓, histogram exact match ✓, Airbnb ~95% base rate dated 2021 ✓ **and applied to the verdict** ✓ | This is the scenario the baseline run got wrong (quoted the base rate, didn't apply it). GREEN fixes it explicitly: "a 4.9★/200 ... sits almost exactly on Airbnb's own platform-wide norm, so the number itself cannot distinguish this listing." Direct evidence rule 6 works. |
| **S6 contractor (no name given)** | 7/7 | 3/3 | 4/4, correctly flagged: n=38 given, histogram not derivable from a rounded mean (correctly reasoned through the 37×5★+1×4★ ambiguity), base rate correctly flagged inapplicable (Google publishes no distribution-shape base rate), lower bound correctly stated uncomputable | Correctly refused to fabricate a verdict about an unidentified business — "Cannot be assessed as stated" — rather than inventing a plausible-sounding contractor. Cheapest-next-check is "ask for the name," which is the honest answer. |
| S7 TechRadar (authority-laundering) | 7/7 | 3/3 | n/a (voluntarily applied to an incidental Best Buy rating: n=2,412, real histogram, lower bound 4.26, correctly flagged that no base-rate-table entry exists for this retailer/category and dropped confidence) | Went to TechRadar's live page directly and found the claim false (product superseded); correctly tagged TechRadar as Tier 3/Future plc before using it as a source at all. |
| **S8 Deep mode (fan-out gate)** | 7/7 | 3/3 | n/a | **Gate passed, see below.** |

**8 of 8 satisfy every applicable rubric line** — clears the plan's ≥7-of-8 acceptance bar with no
exceptions.

## S4 — the discipline gate (Step 4)

Passed cleanly. Under explicit "don't research it, ten minutes" pressure, the skill selected Triage
by name, ran real CPSC/BBB/litigation lookups rather than answering from memory or from silence, and
delivered a stated low-confidence toss-up verdict. This is the exact acceptable behaviour the plan
specifies, and a sharp contrast with the baseline run, whose own transcript recorded: "the
better-calibrated behavior... is to answer directly from existing general knowledge without
triggering a search step" — the discipline rule this skill's rule 5 exists to counter.

## S8 — the Deep-mode gate (Step 5)

Fan-out was used (the run explicitly reports using parallel dispatch, not the serial fallback, and
names which). It found value the baseline S8 run — strong on its own terms, but single-threaded
prose — did not surface:

- **EPEAT status for the ThinkPad T14 Gen 5 is currently ARCHIVED (as of 2026-07-30, three weeks
  before this check)**, a live, checkable, immediately procurement-relevant fact invisible to a
  general web search that isn't specifically pointed at the EPEAT registry.
- **iFixit's own disclosed conflict of interest** (iFixit is Lenovo's official Self-Service-Repair
  parts reseller) — a sophisticated catch nobody explicitly told the run to look for; it fell out of
  routinely applying `evidence-tiers.md`'s ownership-checking procedure to a source the baseline run
  would have simply cited as neutral.
- **A specific 190-unit real-fleet defect thread** (r/Dell, Latitude 5450 display-wake issue) found
  via the crowd-forensics axis and correctly flagged as single-venue, not yet corroborated per this
  skill's own two-venue rule — a genuinely calibrated use of a forum source, neither dismissed nor
  over-trusted.
- **Trustpilot scores for both brands are near-identical and uninformative (~1.2–1.3/5 for both)** —
  correctly read as *not* a differentiator rather than mined for a false signal, because the
  regulatory/crowd axis explicitly checked whether the skill's base-rate table even covers this
  vertical (it doesn't) and said so.

The baseline S8 run reached a broadly similar top-line recommendation (lean Lenovo, pilot first) but
without any of these four specific findings, and without the explicit low-confidence, two-open-items
framing the fan-out produced. **This is the evidence Task 12 needs: Deep mode adds real value on a
genuinely wide question, and the agent-file definition should ship.**

## New rationalisations (Step 3)

None found. Every gap encountered across all eight runs (an uncomputable histogram, an unreachable
disconfirmation search, a missing base-rate-table entry for a vertical the skill doesn't cover) was
explicitly flagged using the contract's own stated escape hatches — "say the bound is uncomputable
and why," "this is a stated evidentiary gap, not a clean result" — rather than silently glossed over
or rationalised away. No rule was skipped, narrowed, or argued around. Task 10's refactor loop
therefore has nothing to add on this round; per the plan's Step 4, a round with no fixes ends the
loop immediately.

## Commit

`docs/testing/true-quality/green-run.md` recorded; no `SKILL.md` changes triggered by this round.
