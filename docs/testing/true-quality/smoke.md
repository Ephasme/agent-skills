# Live smoke test — three real questions, real internet

Compiled 2026-08-19. Task 11 of `docs/plans/2026-08-19-true-quality-skill.md`. Three genuinely
different categories, real web search/browsing throughout, no pinned fixtures. Full transcripts:
`history://SmokeA` (durable hardware), `history://SmokeB` (open-source dependency), `history://SmokeC`
(trade service, anonymised below per Step 5).

## A — Durable hardware: Anker 737 Power Bank (PowerCore 24K)

**Question:** "Is the Anker 737 Power Bank actually good, or is the rating inflated?"

Found a real, currently listed product (model A1289, Amazon ASIN B09VPHVT2Z). Amazon's own
histogram endpoints returned live HTTP 503s during the session — correctly left uncomputable rather
than substituted with the bare 4.4★/n=17,476 mean. Cross-shopped the identical SKU on Best Buy (model
A1289011), read its histogram directly off the live page (14/5/11/65/621 across 1★–5★, n=716),
computed a Dirichlet-multinomial lower bound of **4.71**, and queried the CPSC recall registry
directly, correctly distinguishing that this specific model is **not** named in any of the
manufacturer's three 2024–2025 lithium-battery fire recalls even though three sibling models are —
using that gap ("not yet recalled is the weakest form of evidence this skill recognizes") as the
central, correctly-hedged disconfirming point rather than either dismissing or overstating it. Also
proactively identified and excluded five templated, apparently AI-generated "long-term review" sites
from the SEO layer, naming them and stating why they were excluded rather than silently omitting
them.

## B — Open-source dependency: lodash vs. es-toolkit

**Question:** "Should we add `lodash` as a new dependency in 2026, or is there a better-maintained
alternative?"

Followed the open-source-dependency routing exactly — OpenSSF Scorecard and deps.dev first, stars
and downloads used only as the anti-manipulation cross-check the routing table specifies, never as
primary evidence. Found and correctly reversed the popular "lodash is dead" narrative: a real,
verified ~5-year release gap (4.17.21 → 4.18.0) followed by a real, live-verified institutional
funding and governance reboot (OpenJS Foundation + Sovereign Tech Agency, announced 2025-10-14, with
two subsequent coordinated CVE releases). Computed Wilson lower bounds on the fork-to-star ratio for
both packages as the routing's stated substitute for a rated crowd pool (lodash 0.1149, inside the
healthy band; es-toolkit 0.0490, at the anomaly-worth-investigating threshold — correctly read as
"consistent with a small, young star base," not asserted as manipulation). Verdict correctly scoped
to the supply-side question only, per the skill's When-NOT-to-use boundary.

## C — Trade service: a licensed electrician in Austin, TX (anonymised)

**Question:** "Find a real, currently licensed, highly-rated electrician in Austin, and tell me
whether they're actually trustworthy — not just highly rated."

Found a real, currently operating Texas electrical contractor via open search (referred to here as
**"[Contractor]"** — the real business name and licence number are in the unredacted session
transcript at `history://SmokeC` but withheld from this committed file per the plan's anonymisation
step). Verified, live, directly against the regulator's own systems rather than a secondary
description of them: Texas TDLR's own electrical-contractor licence-file bulk download (active
licence, correct trade classification, expiry date confirmed), the Texas Comptroller's own
franchise-tax/SOS status API (LLC active and in good standing, though only ~16 months old), TDLR's
own disciplinary-orders search ("No record"), CourtListener's federal/appellate docket search (zero
results, with the coverage gap for small-claims/JP court explicitly disclosed rather than read as a
clean record), and the actual statutory text of the Texas insurance-floor rule (16 TAC §73.40) via
Cornell LII, rather than trusting a secondary description of the requirement.

Google Maps, Yelp, Trustpilot and BBB all blocked direct reading this session (a JS-rendering
limitation and three HTTP 403s). **Correctly refused to fabricate a crowd-data bound from either of
two disagreeing secondary aggregator figures (144 reviews/5.0★ vs. 300+ reviews/4.9★)** — reported
both, reported that neither is independently verified, dropped confidence one level exactly as the
contract's rule requires, and stated explicitly that the "highly rated" half of the question could
not be resolved this session rather than resolving it anyway. Calibrated language held throughout: a
`?`-marked, unverified single historical billing complaint was reported as exactly that — dated,
low-severity, unverified at its primary source — never escalated into an accusation.

## Citation check (Step 2)

Eight load-bearing URLs spot-checked live across all three runs: the CPSC Anker recall page, the
exact Best Buy review page (histogram re-confirmed digit-for-digit: 14/5/11/65/621), the OpenJS
Foundation's own lodash-funding announcement, the specific lodash GitHub Security Advisory
(CVE-2025-13465), TDLR's licence-file lookup tool, Cornell LII's mirror of 16 TAC §73.40, the
TechRadar power-bank review, and the OpenSSF Scorecard API result for lodash. **All eight resolve
and confirm what the runs claimed.** One verification note, not a citation error: the scout run that
checked the CPSC page compared a model list against the wrong one of the run's three cited recalls
(Sept-2025 vs. Oct-2024) — re-checked by hand, both lists as originally cited are correct, and the
core claim (model A1289 excluded from all three) holds.

## Arithmetic check (Step 3)

Recomputed independently: `python3 skills/research/true-quality/scripts/rating-bounds.py --hist
14,5,11,65,621 --z 1.96` → lower bound **4.71**, matching SmokeA's reported output exactly.

## Language check (Step 4)

No output in any of the three runs asserts fraud, dishonesty, or wrongdoing by an identifiable
business absent a first-party artifact or regulator record. The one genuinely negative finding about
an identifiable party (Anker's three real, CPSC-confirmed sibling-model recalls) is a regulator
action, which the contract explicitly permits stating plainly. The `[Contractor]` run's one
unverified complaint is marked `?` and described in calibrated terms ("a billing-communication
miscommunication," not "this business overcharges customers"). No violation found; no Task 10 rework
triggered.

## Outcome

Three live runs, zero unresolvable or misattributed citations, the recomputed bound matches, every
run's `Against it` slot filled from real evidence (never left empty), and the one run that hit a
genuine data-access wall (C) disclosed the gap rather than papering over it — the exact behaviour the
skill's non-negotiable rules require.
