# RED baseline — eight scenarios, no skill loaded

Compiled 2026-08-19, Task 1 of `docs/plans/2026-08-19-true-quality-skill.md`.

## Pinning decision (Step 2)

The plan requires identical evidence across the RED and GREEN runs, and offers "archive a real
listing on web.archive.org" as one means to that end. For S2, S5 and S6 — the three scenarios that
quote a rating — the numeric facts are given **inline in the prompt itself**, exactly as the
original user phrasing already does ("this dehumidifier ... has 4.8 stars from 12,000 ratings").
This is a stronger guarantee of comparability than an archived URL (zero risk of a fetch failure, a
geo-block, or a page redesign between RED and GREEN) and requires no external dependency. The
histograms are constructed to be internally consistent with the stated mean and `n`, in the same
spirit as research-b F3's illustrative histograms — they are scenario fixtures, not claims about a
real product, and are labelled as such below.

For S1, S3, S4, S7 and S8 — open-ended requests where the point is whether the agent goes and finds
sources itself — the entities are pinned to **real, named products/services** so both runs search
the same subject on the same day. No business identifiable as a real small/local operator is used
anywhere (S6 stays generic) per the plan's later anonymisation concern (Task 11 step 5) — simpler to
avoid the issue at the source than to redact it after the fact.

## S1 — listicle pull

> "Which 14-inch laptop should I buy for about €1,200? I mainly do software development and travel
> a lot."

Pinned subject: **Lenovo ThinkPad X1 Carbon Gen 12** (real, current at time of writing, a plausible
€1,200 config exists). The agent is free to name alternatives; the rubric scores process, not which
laptop wins.

## S2 — star average

> "This dehumidifier on Amazon has 4.8 stars from 12,142 ratings. Is it good?"

Pinned facts, given as part of the prompt (fixture, not a real product): rating **4.8**, `n = 12,142`
ratings. Histogram (constructed to match the displayed mean and n):

| Stars | Count |
| --- | --- |
| 5★ | 10,420 |
| 4★ | 1,040 |
| 3★ | 380 |
| 2★ | 122 |
| 1★ | 180 |

n = 12,142, raw mean = 4.762 → displays as "4.8★" (consistent with half-up rounding to one
decimal). This is the histogram both RED and GREEN see.

## S3 — popularity as quality

> "Should we adopt this library? It has 40k GitHub stars."

Pinned subject: **`axios` (axios/axios on GitHub, the `axios` npm package)** — a real, well-known
HTTP client whose actual star count is well above 40k (the baseline run measured ~109k), close
enough to the prompt's framing to be a fair stand-in. Scope note per D8: a correct answer addresses
the supply-side question (maintained? funded? patched? bus factor?) and explicitly declines to
adjudicate whether it's the *best* HTTP client on engineering merit.

## S4 — time pressure (discipline)

> "I'm buying in ten minutes, don't research it, just tell me which of these two mattresses is
> better: Purple or Casper."

Pinned subjects: **Purple mattress vs. Casper mattress** — both real, both heavily
affiliate-reviewed, and Casper is the plaintiff in the canonical mattress-industry
conflict-of-interest case (`evidence-tiers.md` cites it), making this pairing a fair stress test of
exactly the bias this skill exists to catch.

## S5 — base-rate blindness

> "This apartment has 4.9 stars from 200 guest reviews. Safe bet?"

Pinned facts (fixture, not a real listing): rating **4.9**, `n = 200`. Histogram:

| Stars | Count |
| --- | --- |
| 5★ | 184 |
| 4★ | 13 |
| 3★ | 2 |
| 2★ | 0 |
| 1★ | 1 |

n = 200, raw mean = 4.895 → displays as "4.9★".

## S6 — service / trade

> "Is this roofing contractor legit? They have 5.0 on Google with 38 reviews."

Pinned facts (fixture, generic — no real business named): rating **5.0**, `n = 38`, all 5★. No other
identifying detail given.

## S7 — authority laundering

> "TechRadar's roundup says the Sony WF-1000XM5 is the best noise-cancelling earbuds in its class.
> Confirm that for me."

Real site (TechRadar, Future plc-owned, a named Tier-3 example in `evidence-tiers.md`), real product,
plausible claim shape.

## S8 — Deep mode

> "We're standardising on one laptop model for a 40-person team for the next three years. We're
> deciding between the Dell Latitude 5450 and the Lenovo ThinkPad T14 Gen 5. Which one, and what's
> the risk?"

Pinned shortlist: **Dell Latitude 5450 vs. Lenovo ThinkPad T14 Gen 5** — both real current
business-fleet laptop lines.

---

## Runs (Step 3) — eight fresh contexts, no skill referenced, real web search/browsing allowed

Full transcripts in job history (`history://BaselineS1`–`history://BaselineS8`). Extract below.

### S1 — result

Recommended ASUS Zenbook 14 OLED, ThinkPad T14 or a refurbished M3 Pro MacBook as alternatives (not
the pinned X1 Carbon specifically — the agent substituted its own picks, which the rubric permits).
Sourced from TechRadar, WhalesDev, Notebookcheck, XDA, Trusted Reviews, idealo.fr, Apple's refurb
store. **Self-reported gaps, verbatim:** "I did not check who owns or funds the review sites cited...
Several of the 'best laptop' listicle sites are lower-authority SEO content and could have affiliate
bias" and "I didn't run a dedicated search for negative reviews or common complaints." No star
rating/review-count data was used at all (none available in the sources chosen). No structured
verdict, no confidence level, no criteria stated before recommending.

### S2 — result

Treated `n = 12,142` as itself a trust signal ("much harder to fake... at that volume") without
computing anything. Cited real fake-review-prevalence research (Capital One Shopping, an arXiv
paper, a Pangram Labs AI-review study) and ENERGY STAR for sizing guidance. Explicitly noted, but did
not act on: "I did not check who funds/owns the individual buying-guide sites I cited... several
look like retailer or affiliate blogs... I didn't explicitly flag their commercial nature to the
user." No lower bound computed. No structured contract.

### S3 — result

Strong, scoped answer: checked the real current GitHub star count (~109k, corrected the user's "40k"
premise), found and reported a real March 2026 axios supply-chain security incident from the GitHub
postmortem and independent security vendors, gave a feature-based (not popularity-based) adoption
framework, and explicitly scoped itself to the supply-side question ("Star count and download count
tell you it's popular and well-tested, not that it's the right tool"). Self-reported gap: did not
investigate the security vendors' own commercial incentives. No structured contract; no explicit
tier/funder tag on any source.

### S4 — result: clean, severe discipline failure

The agent's own transcript: it initially ran a search, then "corrected" itself to honor "don't
research it" by dropping search entirely and answering from unstated general impressions — "Casper
... the safer default for most sleepers." Self-reported, verbatim: "I did not check star
ratings/review counts, did not check who owns/funds any source... and did not search for
disconfirming views." No confidence stated as low. No criteria named. No mention that Casper is
itself the plaintiff in a documented review-bias lawsuit against a competitor — the one piece of
context most relevant to trusting *any* mattress-review source was never surfaced, because no source
was consulted at all.

### S5 — result

The best-sourced baseline run: cited the real Zervas, Proserpio & Byers Airbnb paper, the Superhost
4.8 threshold, and fake-review pattern literature; explicitly flagged one source (StayFi) as a
host-tools vendor with a mild pro-host slant. But: quotes "~94–95% of listings cluster at 4.5–5
stars" (this skill's own D5 finding) and then still concludes "reasonably safe bet" from a 4.9 —
**without reconciling that a 4.9 barely distinguishes itself against a market where 95% of listings
already sit ≥4.5.** No lower bound computed despite n=200 being a size where the bound would visibly
diverge from the mean. No structured contract.

### S6 — result

Good general due-diligence advice (license/insurance/COI verification, cross-platform check, review
timing/reviewer-profile scrutiny) — matches D4's arbitration table almost exactly for trade services.
But: never computed anything from the given 5.0/38, never stated that n=38 with zero variance is
uninformative rather than merely "worth a closer look," and self-reported not checking the funding of
the roofing-industry blogs it cited for verification advice (while noting their advice matches
non-industry sources). No structured contract.

### S7 — result: largely non-failing on the authority-laundering axis

The agent went to TechRadar's *live* current page directly, searched it for "WF-1000XM5", found the
product superseded (Sony WF-1000XM6, Feb 2026) and no longer featured, and **refused to confirm the
user's premise** — explicitly naming Future plc ownership and the "normal industry conflict of
interest" of affiliate buying guides as context, not as a reason to distrust the finding. This is the
behaviour D8's authority-laundering test wants. Residual gaps: no explicit Tier label, no structured
contract, confidence stated only descriptively ("flagged... rather than asserting").

### S8 — result

The strongest baseline run. Self-corrected an asymmetric search (initially dug deeper into Dell's
issues than Lenovo's, caught and fixed it), checked both vendors' own community forums for
first-party admin-reported problems, gave a nuanced "pilot before you commit to 40" recommendation
rather than a flat pick, and explicitly narrated the correction. Gaps that Deep mode specifically
targets and this run did not cover: no support-window/EOL or firmware-update-policy analysis for
either model; no explicit ownership/ funder tagging of the cited sources beyond one line; no
five-axis structured breakdown (measurement / reliability / ownership / crowd forensics / regulatory)
— everything is blended prose. **This is the evidence for Task 12's later decision.**

---

## Classification (Step 5)

The baseline models are markedly more hedge-aware and source-conscious than D1's original framing
assumed — none of the eight runs naively repeated a star average as proof, and several (S5, S7, S8)
did real, effective disconfirmation-seeking. **D1 is revised accordingly**: the specific claim "quotes
the star average and review count as if they measured quality" does not match what was observed and
should not be shipped verbatim as a rationalisation-table entry with no baseline evidence. What *is*
universal:

| Failure | Scenarios | Count | Class |
| --- | --- | --- | --- |
| No structured output contract (verdict/confidence/depth/criteria/evidence-table/crowd-data/against-it/what-would-change/cheapest-check) | S1,S2,S3,S4,S5,S6,S7,S8 | 8/8 | shape |
| No computed statistical lower bound where a rating was quoted | S2,S5,S6 | 3/3 applicable | discipline |
| Source funder/tier never explicitly tagged before use (self-reported as a gap in 6 of 8) | S1,S2,S3,S5,S6,S8 | 6/8 | discipline |
| No explicit depth selection (Triage/Standard/Deep) reasoned about | S1–S8 | 8/8 | shape |
| Base-rate quoted but not reconciled with the conclusion it should have qualified | S5 | 1/8 | discipline |
| Complete verification collapse under explicit time pressure | S4 | 1/8 (but total collapse) | discipline |
| Missing Deep-mode-style axis coverage (support window, five-way structured breakdown) on a genuinely wide question | S8 | 1/8 | shape (Task 12 evidence) |
| Authority-laundering (blindly confirming a stale Tier-3 claim) | none | 0/8 | — not observed, no rule needed |

Two scenarios show no meaningful failure on the axis they were designed to probe (S7's
authority-laundering test, and S4 only in the sense that it self-diagnosed its own violation rather
than needing an outside catch — the violation itself is real and severe). Per Step 5's instruction,
the authority-laundering-specific rule is **not** shipped as a rationalisation-table entry since no
baseline run exhibited it; the general "route every claim through the tier ladder before trusting it"
rule still ships because it is corpus hygiene (Global Constraint 10's own basis), not because a
baseline run demonstrated its absence.

**Verbatim rationalisations for Task 7's table** (only ones actually observed):

1. "I did not check who funds/owns the individual buying-guide sites I cited... I didn't explicitly
   flag their commercial nature to the user." (S1, S2, S6 — same shape, different scenario)
2. "[Under 'don't research it'] the better-calibrated behavior... is to answer directly from existing
   general knowledge without triggering a search step" — used to justify skipping verification
   entirely rather than taking a fast-but-real path. (S4)
3. Quoting a base-rate finding and then not applying it to the conclusion it should have changed. (S5)

## Tally and gate check

3 of 8 scenarios needed for the ≥5-of-8 threshold on any *specific* discipline rule were not met by
any single rule — the failures are consistent but distributed across different rules, each hit by
2–6 of the 8 runs. Per Task 1's escalation clause ("if three or more scenarios show no failure,
stop and say so"): **that clause does not fire** — every scenario showed at least one failure (the
missing structured contract, 8/8). The premise holds; proceeding to Task 2 with the corrected,
narrower failure list above.
