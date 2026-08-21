---
name: true-quality
description: Use when the real quality of something has to be established from internet evidence and the obvious sources are compromised — choosing between products, models, brands, tools, services, lodgings, contractors or suppliers; judging whether a rating, a review pool, a "best X" ranking, a benchmark or a vendor spec can be trusted. Trigger phrases — "is X actually any good", "which X should I buy", "best X", "is X worth it", "are these reviews fake", "why is this rated so highly", "quel est le meilleur", "est-ce que ça vaut le coup", "faux avis". Also when a previous answer leaned on a listicle, an affiliate round-up, a star average or a manufacturer claim.
---

# True Quality

Compiled 2026-08-19. **`$SKILL_DIR` is notation, not a variable that is already set** — it stands
for this skill's own directory, the directory holding this `SKILL.md`. Build every read from that.

## Core principle

Quality is measured, not rated. The cheapest evidence to fake is exactly the evidence most search
results are made of — a star average, a "best of" listicle, a manufacturer spec. Route to harder-to-fake
evidence first; read the crowd data with real statistics, never a raw mean; audit who funds every
source that survives; then answer in a fixed shape that states its own uncertainty.

## Files

| File | What it is | When to open it |
| --- | --- | --- |
| [`references/primary-sources.md`](references/primary-sources.md) | Category → primary-database routing, 36 sources | Step 2, always, before reading any rating |
| [`references/rating-forensics.md`](references/rating-forensics.md) | The lower-bound formulas, J-shape/herding/reciprocity biases, platform base rates | Step 3, whenever a rating is quoted |
| [`references/evidence-tiers.md`](references/evidence-tiers.md) | Ownership-checking procedure, 0–4 source tiers, conflict-of-interest artifact table | Step 4, for every surviving source |
| [`references/fraud-signals.md`](references/fraud-signals.md) | Behavioural/platform fraud signals, query patterns, dead tools | Step 5, disconfirmation hunting |
| [`references/source-ledger.md`](references/source-ledger.md) | Provenance for every citation in this skill | To judge whether a citation here is admissible or needs re-checking |
| [`scripts/rating-bounds.py`](scripts/rating-bounds.py) | Computes the Wilson/Dirichlet/shrinkage bounds (`python3`, stdlib only) | Step 3, whenever `n` and a histogram are available. If `python3` is unavailable, `rating-forensics.md` gives every formula for hand computation — the script is an optimisation, not a requirement. |

## The pipeline

1. **Frame** — name 3–6 decision criteria before looking, each tagged `[measurable]` or
   `[experiential]`, plus the failure modes that would actually matter for this item. A "best" with
   no stated criteria is marketing, not an answer.
2. **Route** — identify the category (durable hardware / vehicle / appliance / software or SaaS /
   open-source dependency / lodging / trade or professional service / consumable) and pull the
   matching primary source from `primary-sources.md` **before reading any rating**.
3. **Read the crowd correctly** — get `n` and the histogram; compute the lower bound with
   `scripts/rating-bounds.py` (or by hand from `rating-forensics.md`); check the platform's own base
   rate and its year; check the distribution shape and timing. Never the raw mean alone.
4. **Audit the money** — assign every surviving source a tier or type from `evidence-tiers.md`,
   check its funder/ownership via the procedure there, and collapse same-owner sources into one.
5. **Hunt disconfirmation** — run at least one failure-term query and one recall/litigation check
   per finalist, from `fraud-signals.md`'s query patterns and `primary-sources.md`'s registries.
6. **Arbitrate** — when sources disagree, resolve by the table below, never by averaging.
7. **Answer in the contract shape** below.

## Arbitration

| Question | Winner | Why |
| --- | --- | --- |
| Measurable performance (nits, dB, kWh, throughput, AFR) | instrumented lab or large-N operator dataset | the crowd cannot measure it |
| Safety / catastrophic defect | regulator database (recall, Safety Gate, NHTSA, CPSC, RappelConso) | legally forced disclosure, unfakeable by a private party |
| Failure rate over years | large-N operator/inspection data > member reliability survey > review text | the review window is early, the failure window is late |
| Unit-to-unit QC, dead-on-arrival rate | the crowd, read as *negative-tail frequency*, never a mean | a lab tests one unit |
| After-sales service, RMA, support | the crowd + complaint aggregators | not lab-measurable |
| Fit, comfort, taste, ergonomics | the crowd, stratified by use case | subjective by construction; a mean destroys the information |
| Vendor promise (support window, warranty) | the vendor's own written terms, against the regulatory floor | it is a contract, not an opinion |

## Output contract

The answer IS these parts, in this order. Reported bound precision: two decimals.

```
Verdict — one line, plus a confidence (low | medium | high) and the depth run
          (triage | standard | deep), so a reader can see how much work backs it
Criteria — the 3-6 named criteria, in priority order, each [measurable] or [experiential]
Evidence — table: finding | source | tier or type | who funds it | date | what it actually measures
Crowd data — n, histogram shape, platform base rate (with its year), computed lower bound,
             manipulation flags (named from fraud-signals.md's signal set; "none observed" if none —
             never omitted). If the platform publishes no histogram, say the bound is uncomputable
             and why, and drop confidence by one level — never substitute the bare mean.
Against it — REQUIRED: the strongest disconfirming finding. If none was found, name the
             disconfirmation searches that came back empty. This slot is never omitted.
What would change this verdict — 1-3 specific, findable facts
Cheapest next check — one concrete action the user can take in under five minutes
```

Two rules that decide whether the Crowd-data field holds up: (1) where a platform publishes
percentages, not counts, derive counts as `round(pct × n)` per bucket and say they're derived; (2)
`z = 1.96` is this skill's fixed standard for every bound — never switch it mid-comparison.

**Calibrated language is part of the contract.** This skill's output makes claims about identifiable
businesses and people. Phrase manipulation findings as *consistency with a pattern* ("this timeline
is consistent with a purchased burst"), never as an accusation ("these reviews are fake") — an
accusation is permitted only when a platform's own first-party artifact says so (a Consumer Alert
banner, a paused-reviews notice, a regulator's published action). Same rule for a trade or
professional: report the record found, not a character judgment.

## Depth

| Depth | Budget | Contents |
| --- | --- | --- |
| Triage | ~3 lookups | criteria; one tier-0/1 measurement or one primary database; one failure-term query. Verdict at explicitly low confidence, plus the cheapest next check. |
| Standard | ~8–15 lookups | full pipeline, two independent venues minimum, ownership checked before corroboration counted |
| Deep | fan-out | one axis per worker: measurement, reliability/failure, ownership/conflict-of-interest, crowd forensics, regulatory/primary databases. **Serial fallback** if no fan-out is available: the same five axes, in order, each writing its findings to a file before the next starts. |

**Depth is a rule, not a judgement call** — left to discretion, the answer under pressure is always
the cheapest one, and that is exactly the failure this skill has to survive.

| Observable | Depth |
| --- | --- |
| The user signals time pressure, asks to skip research, or the decision is cheap and reversible (returnable, free trial, one-off consumable) | Triage |
| Anything else — the default | Standard |
| Multi-unit, multi-year, or hard-to-reverse commitment, or the user asks for depth | Deep |

Name the chosen depth in the Verdict line — that is what makes the choice auditable. "Two
independent venues" (Standard) means **different owner and different funding model** — two Tier-3
sites under one parent are one venue; a Tier-0 lab and a forum thread are two. This is the same rule
as "two same-owner sources are one source," stated here so it can't be read as a separate, looser
test.

## Non-negotiable rules

**Baseline-driven** (each traceable to an observed failure in this skill's own pre-launch testing):

1. Never answer a quality question from memory. Search, every time.
2. A vendor claim is evidence of a promise, never of quality — convert it into a testable question
   before using it.
3. Every source in the Evidence table carries a tier-or-type and a funder, or it cannot support the
   verdict.
4. Never report a mean without `n`, the histogram, the platform's base rate (with its year), and the
   computed lower bound.
5. Name the depth you're taking, out loud, before researching — under time pressure, take Triage
   with stated low confidence; never silence, and never a confident answer built on nothing.
6. If you cite a base-rate finding (a platform's own typical distribution), apply it to the verdict —
   quoting it and then ignoring what it implies is the same as not checking it.
7. State criteria before ranking anything.

**Corpus hygiene** (no single baseline run needs to exhibit these — they hold regardless):

8. Refuse to rank on Tier-3/4 evidence alone; say what's missing and the cheapest check that would
   resolve it.
9. Two same-owner sources are one source, never two.
10. Never cite a dead analyser (Fakespot, ReviewMeta, TheReviewIndex — see Decay), an undated
    platform percentage, or an unversioned legal regime.
11. Never invent a numeric threshold the sources don't give — "an inference, no threshold" beats a
    fabricated cutoff every time.
12. Collect evidence by ordinary reading only. No bulk scraping, no automated harvesting of reviewer
    profiles, nothing a platform's terms forbid — every signal in this skill is readable from what a
    page shows a visitor.

## When NOT to use this

| The question is really about | Goes to |
| --- | --- |
| Comparing two libraries/APIs on engineering merit | ordinary engineering judgement — this skill answers only the *supply-side* half (is it maintained, is the vendor solvent) |
| Whether claims in a document the user supplied are true | `fact-check-document` |
| Pure sourcing discipline on any topic | `cite-or-refuse` |
| French insurance cover, a refused claim, a policy | `assurance-fr` |
| Whether a therapy or mental-health product works | `tcc` |
| Medical, legal or financial advice for a specific person | no skill here — state the evidence and say the decision belongs with a professional |

## Domain map

| Question shape | Reference, section |
| --- | --- |
| "Which primary source for category X?" | `primary-sources.md` routing table |
| "Is this rating trustworthy — the math" | `rating-forensics.md`, lower-bound formulas |
| "Why does this rating distribution look the way it does" | `rating-forensics.md`, J-shape / biases |
| "Who owns this review site, is it independent" | `evidence-tiers.md`, ownership procedure + tiers |
| "Is this a paid placement / affiliate ranking" | `evidence-tiers.md`, conflict-of-interest artifact table |
| "Are these reviews fake / manipulated — the signals" | `fraud-signals.md`, detection signals + platform mechanics |
| "What does the law require here" | `fraud-signals.md`, regulation as artifact generator |
| "How do I search around SEO listicles" | `fraud-signals.md`, query patterns |
| "Is this benchmark/spec gamed" | `evidence-tiers.md`, vendor-claim gaming |

## Conventions

`?` marks a claim not read at its own source — never promote one to a plain assertion without
opening the source, and never drop the prefix when quoting a `?`-marked line from a reference file.
Ordinary reading only (rule 12 above) — this skill's signals are all visible to a person looking at
a page normally.

## Rationalisations — and what actually happened when this skill's guidance was absent

| Excuse observed | Reality |
| --- | --- |
| "I did not check who funds/owns the individual [buying-guide/roofing/dehumidifier-advice] sites I cited... I didn't explicitly flag their commercial nature to the user." | Noticing the gap and not acting on it is the same failure as not noticing it. Rule 3: no source enters the Evidence table without a tier/type and a funder. |
| "[Under 'don't research it,'] the better-calibrated behavior... is to answer directly from existing general knowledge without triggering a search step." | This is silence dressed as calibration. Rule 5: time pressure selects Triage — three real lookups and a stated low confidence — never zero lookups and a confident brand pick. |
| Quoting a platform's own inflation/base-rate finding and then concluding "reasonably safe bet" from a rating that finding says is nearly uninformative. | Rule 6. A base rate you cite but don't apply is decoration, not evidence. |

**Red flags** — if you catch yourself thinking any of these, stop and restart the pipeline step you
skipped:

- "The reviews are overwhelmingly positive, that's enough" — that's exactly the shape a J-shaped
  honest distribution takes; it is also exactly the shape manipulation produces. Run Step 3.
- "It's a reputable [tech/lifestyle] site" — reputable and Tier-3-affiliate-funded are not mutually
  exclusive. Run Step 4.
- "The user said not to research it" — Triage still runs three lookups. It is not zero.
- "I already have a good sense of this category" — a sense is not `n`, a histogram, or a source tier.

## Decay — dated, re-check before quoting

1. **Third-party analysers die.** Fakespot shut 2025-07-01; TheReviewIndex's own page says
   permanently down; ReviewMeta's status is `?` — no primary source confirms it, only convergent
   secondary reports. Never send anyone to any of the three.
2. **Affiliate economics move.** Amazon Associates rates were cut by up to 50%, reaching the US
   ~2026-03-09.
3. **Regulation is mid-flight — today is 2026-08-19.** Already in force: EU Omnibus Directive
   2019/2161 (since 2022-05-28), the DSA (since 2024-02-17), FTC 16 CFR Part 465 (since
   2024-10-21), UK DMCC Schedule 20 (since April 2025), the EU Right to Repair Directive (since
   2026-07-31). Pending: the Cyber Resilience Act's Article 14 reporting duty from **2026-09-11**
   (three weeks out) and its 5-year security-support floor only at full application, **2027-12-11**
   — do not conflate these two CRA dates.
4. **Penalty figures are indexed, not fixed.** The FTC's per-violation maximum is $53,088 as of
   2025-01-17 (unchanged for 2026) — quote it with the mechanism and the as-of date, or fetch it live.
5. **Platform figures are annual and directional.** Yelp's recommended share fell from 75% (2022) to
   70% (2025 report). Every such percentage needs its year attached.
6. **Ownership changes.** CNET went Red Ventures (2020–2024) → Ziff Davis (Q3 2024). Re-check the
   parent before quoting a tier — `evidence-tiers.md`'s procedure, not its map, is the durable part.
7. **This corpus was built by agents and self-audited.** Of the citations first drafted here, several
   were wrong or stale on first verification (see `docs/plans/2026-08-19-true-quality-skill.md`'s
   Verification record) — a `?`-marked or `secondary`-flagged row in `source-ledger.md` is a lead,
   not a settled fact.

## Kill switch

If this skill's breadth proves wrong in practice — firing on questions it shouldn't — the fix is
either adding `disable-model-invocation: true` to the frontmatter above with matching "explicit
invocation only" prose, or removing the skill from the store. Installing a skill here activates it
immediately, with no separate on/off step, so this is the only lever.

## Cross-references

`cite-or-refuse` — general sourcing discipline, for topics beyond quality/purchase questions.
`fact-check-document` — when the input is a document of claims to verify, not a purchase decision.
