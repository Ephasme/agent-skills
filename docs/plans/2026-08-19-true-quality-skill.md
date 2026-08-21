# `true-quality` Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `subagent-driven-development` (recommended) or
> `executing-plans` to work this plan task by task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Ship one skill, `skills/research/true-quality/`, that makes an agent establish what
something is *actually* like from internet evidence — resisting vendor self-claims, affiliate and
sponsored rankings, click farms and bought reviews, platform-specific rating manipulation, and the
naive star average — and that ends every answer in a verdict whose evidence, uncertainty and
falsifiers are all on the page.

**Architecture:** A routing skill over a dated, cited corpus. `SKILL.md` holds the pipeline, the
non-negotiable rules, the output contract and a domain map; four `references/*.md` hold the
detail (source tiers and ownership, rating forensics, fraud signals, primary-source routing); one
`references/source-ledger.md` holds provenance; one stdlib script computes the rating bounds a
human cannot do in their head. Progressive disclosure, `tcc`-style: the agent reads `SKILL.md`
always, and exactly the reference the domain map names.

**Tech stack:** Markdown (Agent Skills format), `python3` stdlib for `scripts/rating-bounds.py`,
`node scripts/validate.mjs` as the gate.

**Spec:** this document. The evidence base is `docs/research/true-quality/research-{a,b,c,d}.md`
(1,361 lines, ~120 findings, each with claim / mechanism / agent-observable signal / strength /
sources), produced 2026-08-19 by four parallel research agents.

**Hardened 2026-08-19** against the codebase, the validator's source, the repo's CI, and the primary
sources behind 15 of its quoted facts. Five of those 15 were wrong or stale; see the Verification
record. That measured error rate is why verification now gates a fact's *entry* into the skill
rather than being a spot-check at the end.

---

## Global Constraints

1. **Validator gate:** `node scripts/validate.mjs` must pass. Specifics, read from
   `scripts/validate.mjs` rather than inferred:
   - `SKILL.md` body ≤ 500 lines (`MAX_BODY_LINES`).
   - A `references/*.md` file over **100 lines** with **≥2 `## ` sections** (fenced blocks excluded)
     must contain a heading matching `## Contents` or `## Table of contents`.
   - **Every** `references/*.md` in the tree must be mentioned in `SKILL.md` by its relative path, in
     a form the extractor matches: `](references/x.md)`, `` `references/x.md` `` or
     `$SKILL_DIR/references/x.md`. A reference that exists but is not linked is a hard failure
     (`reference chains must be one level deep`). A path mentioned but missing is also a failure.
   - `$SKILL_DIR` must appear within 120 characters of the word `notation` somewhere in `SKILL.md`.
   - No `/Users/<name>/` or `/home/<name>/` path in any text file. No `CLAUDE.md` on a line that
     does not also name `AGENTS.md`.
2. **Frontmatter:** `name` + `description` only. **No `compatibility` field** — see constraint 3 for
   why. `description` ≤ 1024 chars, third person, no XML tags, no first- or second-person opening.
3. **The portability lint stays armed.** `validate.mjs:238` short-circuits the whole `COUPLING` scan
   for any skill that declares `compatibility` (`if (declaresProduct) return;`). Declaring one for
   `python3` would silently disable portability checking for the largest, most tool-prose-heavy skill
   in the catalog. Decision: **no `compatibility`; state the `python3` requirement in prose beside
   the invocation**, which is honest because the dependency is optional — `rating-forensics.md`
   carries the formulas for hand computation. Consequence: the lint applies to every file, so avoid
   the capitalised words `Opus`, `Sonnet`, `Haiku`; the strings `AskUserQuestion`, `TodoWrite`,
   `SendMessage`, `NotebookEdit`, `ExitPlanMode`, `WebFetch`, `WebSearch`; `subagent_type`,
   `Agent tool`, `Task tool`; any `superpowers:`-prefixed skill name; `~/.claude`; and
   `claude code` / `claude.ai`. Name capabilities, never tools: "the agent's web search", not a
   product name.
4. **Degrade, don't fail:** every fan-out in the skill states the serial fallback (same axes, in
   order, each axis's findings written to a file before the next starts).
5. **`$SKILL_DIR` is notation**, stated once, adjacent to the word `notation`, as `tcc` states it.
6. **Dated corpus.** `SKILL.md` carries a `compiled 2026-08-19` stamp and a Decay section. No claim
   enters the skill without a date on its source, and every platform percentage carries the year it
   describes — they move (Yelp's recommended share went 75% → 70% between 2022 and 2025).
7. **Never name a dead tool as usable.** Fakespot (shut 2025-07-01 per Mozilla's own announcement),
   TheReviewIndex (its own About page says permanently down) and ReviewMeta (status
   `?` — **no primary source found**, see Verification record) appear only in a "do not reach for
   these" list.
8. **Every claim carries its source inline**, with date — no URL dump at the end. Same rule as
   `cite-or-refuse`, which this skill cross-references by bare name.
9. **No new category.** `research` already exists; the skill lands there beside `cite-or-refuse` and
   `fact-check-document`. `README.md`'s catalog row for `research` gets updated in the ship task.
10. **Verification gates entry.** Every number, effective date, legal citation and ownership fact is
    checked at a primary source *by the task that introduces it*, before it lands in a file. The
    ledger records the URL, the date and whether it was read at source. A fact that will not verify
    is cut, or kept with a leading `?` and a ledger row — never quietly softened.
11. **CI runs on push, not on commit.** `.github/workflows/validate.yml` runs the validator, a
    discovery smoke test (`npx -y skills add . -l`, which must report the exact `SKILL.md` count and
    skip nothing) and a portability install for four other agents. The validator is **expected to be
    red between Tasks 2 and 6**, because `checkSkill` fails a directory with no `SKILL.md`. So:
    commit per task locally, **push nothing until Task 7 validates green.** The expected count is
    derived by `find`, so no manual count needs updating.
12. **Note on the branch.** This work sits on `unbaised-search` (a typo for "unbiased"). Rename
    before opening any PR, or the typo enters history permanently.

---

## Verification record

Fifteen quoted facts were re-checked at primary sources on 2026-08-19. Ten passed. The five that did
not are corrected throughout this plan and are listed here so the implementer does not reintroduce
them from the research layer, which still contains the originals.

| Claim | Verdict | Correction |
| --- | --- | --- |
| FTC penalty per violation | **FAIL — stale** | **$53,088**, effective 2025-01-17; no 2026 adjustment (FR 2026-07-07). `$51,744` was correct only through 2025-01-16. The figure is inflation-adjusted annually, so the skill states the mechanism and the as-of date, never a bare number. |
| CNET's owner | **FAIL — stale** | **Ziff Davis**, completed Q3 2024. Red Ventures agreed to buy CNET 2020-09-14, closed **2020-10-30** for ~$500M, and sold it to Ziff Davis in 2024 at a loss. Red Ventures still owns Bankrate (closed **2017-11-08**, per Bankrate's own 8-K exhibit) and The Points Guy. Convention: cite **closing** dates, not signing dates. |
| Cyber Resilience Act, 5-year support floor | **PARTIAL — framing wrong** | Regulation (EU) 2024/2847. The support-period requirement (Art. 13 / Annex I) applies only at **full application, 2027-12-11**. 2026-09-11 is the **Art. 14 reporting** obligation; Ch. IV applied from 2026-06-11. The plan's original "~2026-09" was off by 15 months for the obligation it named. |
| Yelp recommended share | **FAIL — stale** | **70% recommended / 17% not recommended**, per Yelp's own trust report published 2026-02-25. `75%` was the 2022 figure. |
| Google Business average rating 3.74 → 4.11 | **UNVERIFIED as primary** | Figures accurately reproduced, but the source is a reputation-management SaaS vendor's self-published report over **53 of its own client brands / 31,326 profiles** (Jan 2015 – Jul 2022), not a neutral or peer-reviewed study. Label it as vendor research or drop it; no neutral source was found. |
| J-shape (Hu, Pavlou & Zhang) | PASS | MISQ 41(2):449–471, 2017 + CACM 52(10):144–147, 2009 (author order there is Hu, **Zhang** & Pavlou, and it calls the same bias *purchasing* bias, not *acquisition* bias — do not mix the labels). Neither paper invokes fraud. |
| de Langhe, Fernbach & Lichtenstein | PASS | *JCR* 42(6):817–833; 1,272 products / 120 categories exact; all four findings confirmed. Online 2015-09-10, print 2016. |
| Muchnik, Aral & Taylor | PASS — **keep the two numbers distinct** | *Science* 341(6146):647–651, 2013-08-09. **+32%** = likelihood a later rater rates positively. **+25%** = final aggregate score. Never compress to "25–32%". |
| He, Hollenbeck & Proserpio | PASS (abstract only) | *Marketing Science* 41(5):896–921, 2022. Publisher page returned 403 on three attempts; confirmed from its abstract. Flag as abstract-sourced in the ledger. |
| Luca & Zervas | PASS | *Management Science* 62(12):3412–3427; "roughly 16%" exact. |
| Jindal & Liu | PASS | WSDM 2008; 68% wrote one review, 8% wrote ≥5; duplicates labelled at Jaccard ≥0.9. |
| Ott et al. 2011 + LLM erosion | PASS, with a strength downgrade | "nearly 90%" exact (ACL-HLT 2011, 309–319). The LLM-indistinguishability claim rests on **arXiv:2506.13313 (2025-06-16, preprint)**: humans 50.8% accuracy, LLM judges equivalent or worse. Cite as a preprint. |
| Airbnb compression | PASS | Zervas, Proserpio & Byers, "A first look at online reputation on Airbnb, where every stay is above average", *Marketing Letters* 32(1):1–16 (online 2020-11-04). ~95% at 4.5/5.0; hotels 3.8, B&Bs 4.1. |
| Trustpilot + Google enforcement | PASS, one wording fix | Trustpilot Trust Report (publ. 2025-05-29): 4.5M removed = 7% of 2024 reviews (7.4% in body text, up from 6.1% in 2023), 90% auto-detected. Google: 240M+ removed in 2024; 292M+ removed in 2025 alongside 1B+ **published** (not "submitted") reviews. |
| Kape, Consumer Reports, Fakespot, IMDb | PASS | Kape/Webselenese **$149.1M announced 2021-03-08**; Kape owns CyberGhost (2017-03), PIA (2019-11), ExpressVPN (2021-12). CR: "expect to spend more than $30 million" is a **forward projection**, not audited spend; pays full retail, accepts no samples, 501(c)(3), no ads. Fakespot shut 2025-07-01 (Review Checker stopped 2025-06-10). IMDb `m = 25,000`, help page updated 2026-02-09. |

The Dirichlet worked example was additionally re-derived **by hand** from research-b F3's histograms:
Item A (21×5★, 2×4★, n=23) → shrunk mean 128/28 = 4.571, variance 0.0331, lower bound **4.215**;
Item B (82/123/246/779/2870, n=4,100) → shrunk mean 18547/4105 = 4.518, variance 0.000193, lower
bound **4.491**. Both reproduce F3 exactly. Note what this does *not* establish: F3 states those
histograms are illustrative constructions consistent with the stated `n` and mean, not scraped data.
The pinned numbers test formula correctness, nothing empirical.

---

## Design

### D1. The failure this skill exists to stop

Asked "which 14-inch laptop should I buy" or "is this dehumidifier good", an unassisted agent
reliably does four things, all wrong:

1. Summarises the top search results, which are affiliate-funded "best X" listicles — pages whose
   revenue depends on the outbound click, not on being right (research-c F1, F3).
2. Quotes the star average and review count as if they measured quality, when average user ratings
   do **not** converge with independently measured quality across 1,272 products in 120 categories
   (de Langhe, Fernbach & Lichtenstein, *J. Consumer Research* 42(6):817–833).
3. Repeats manufacturer numbers ("up to 18 h") as findings (research-c F23).
4. Presents the result as a confident ranking with no criteria, no uncertainty, and nothing that
   could falsify it.

The skill has to beat all four, and the corpus says the counter-move is not "be more sceptical of
reviews" — it is **route to a different class of evidence first**, then read the crowd data with the
right statistics, then audit who paid for every source that survived.

### D2. Two failure classes, two guidance forms

`writing-skills` is explicit that prohibitions bulletproof discipline failures and *backfire* on
shaping failures. This skill has both, so it uses both, kept apart:

| Failure | Class | Form used |
| --- | --- | --- |
| Quotes a vendor claim or a star average as evidence; skips verification under time pressure | discipline | numbered prohibition + rationalisation table + red-flags list |
| Verdict buried, no uncertainty stated, no disconfirming evidence shown, criteria unstated | shape | positive output recipe: the answer IS these parts, in this order, with a REQUIRED "Against it" slot |

No nuance clauses on either. An exception becomes its own conditional keyed to something observable
("if the platform shows a star histogram, …"), never "unless it doesn't matter".

### D3. The pipeline (`SKILL.md` spine)

1. **Frame** — name 3–6 decision criteria *before* looking, each tagged `[measurable]` or
   `[experiential]`, plus the failure modes that would actually matter for this item. A "best" with
   no stated criteria is marketing.
2. **Route** — identify the category (durable hardware / vehicle / appliance / software or SaaS /
   open-source dependency / lodging / trade or professional service / consumable) and pull the
   matching primary source *before* reading any rating (`references/primary-sources.md`).
3. **Read the crowd correctly** — `n`, histogram, platform base rate, computed lower bound,
   manipulation flags (`references/rating-forensics.md` + `scripts/rating-bounds.py`).
4. **Audit the money** — tier and funding model for every surviving source; collapse same-owner
   sources into one (`references/evidence-tiers.md`).
5. **Hunt disconfirmation** — failure-term queries, recall and litigation databases, teardown,
   negative tail, long-term follow-ups (`references/fraud-signals.md` + `primary-sources.md`).
6. **Arbitrate** — when sources disagree, resolve by D4's table rather than by averaging.
7. **Answer in the contract shape** (D6).

**One ladder classifies recommendation sources; primary evidence gets a different label set.** The
0–4 tiers below describe outlets that *recommend* — labs, reviewers, listicles, lead-gen sites. A
regulator database, an operator failure dataset, a peer-reviewed paper or a vendor's own contractual
terms are not "tier 2"; they carry a type instead: `regulator`, `operator-dataset`, `peer-reviewed`,
`preprint`, `platform-first-party`, `vendor-terms`, `vendor-marketing`. The Evidence table's `tier`
column takes a value from whichever set applies, and `evidence-tiers.md` defines both in one place
so the ledger, the arbitration table and the output contract cannot drift apart.

### D4. Evidence tiers and arbitration

| Tier | Criterion | Named examples |
| --- | --- | --- |
| 0 | No advertising; buys every unit at retail; refuses submitted samples; published protocol; member/non-profit funded | Consumer Reports (501(c)(3), no ads, pays full retail, accepts no samples, projects >$30M/yr of testing spend), Which?, Stiftung Warentest, UFC-Que Choisir |
| 1 | For-profit or creator-funded but buys its own units or refuses sponsorship; publishes raw methodology; on-record history of not softening under pressure | RTINGS (~600 products/yr, ~$700k), Project Farm (Patreon-funded to refuse free product), Gamers Nexus |
| 2 | Real testing infrastructure, disclosed affiliate/ad revenue, accepts loaner units under embargo | Wirecutter, Notebookcheck, DXOMARK (parent's manufacturer-consulting revenue is an on-record conflict) |
| 3 | Affiliate-commission "best of" content at scale from multi-brand conglomerates; little disclosed hands-on testing | CNET (**Ziff Davis** since Q3 2024, previously Red Ventures; 2023 AI-generated-article incident), TechRadar / Tom's Guide (Future plc), Valnet properties |
| 4 | Regulator action on record, or owned by a vendor in the reviewed vertical, or lead-capture is the site's function | vpnMentor / Wizcase (Kape Technologies, which also owns ExpressVPN, CyberGhost, PIA), LendEDU (FTC 2020: paid rank + 90% fabricated Trustpilot reviews), MediaAlpha / QuoteLab (FTC 2025) |

**Ownership is the volatile part of this table, and the skill must not pretend otherwise.** CNET
changed hands twice in four years, and the plan's own first draft got its current owner wrong. So the
skill ships the **procedure first** — how to check who owns a site today — and the named map second,
explicitly dated and marked as an illustration that decays. Every ownership row carries its closing
date and its primary source, and a standing instruction: re-check the parent before quoting a tier.

Arbitration — the thing research-d explicitly left to skill-writing time:

| Question | Winner | Why |
| --- | --- | --- |
| Measurable performance (nits, dB, kWh, throughput, AFR) | instrumented lab or large-N operator dataset | the crowd cannot measure it |
| Safety / catastrophic defect | regulator database (recall, Safety Gate, NHTSA, CPSC, RappelConso) | legally forced disclosure, unfakeable by a private party |
| Failure rate over years | large-N operator or inspection data > member reliability survey > review text | the review window is early, the failure window is late (research-b F17) |
| Unit-to-unit QC, dead-on-arrival rate, packaging | the crowd, read as *negative-tail frequency*, never as a mean | a lab tests one unit |
| After-sales service, RMA, billing, support | the crowd + complaint aggregators | not lab-measurable |
| Fit, comfort, taste, ergonomics | the crowd, stratified by use case | subjective by construction; a mean destroys the information |
| Vendor promise (support window, spare parts, warranty) | the vendor's own written terms, read against the regulatory floor | it is a contract, not an opinion |

### D5. Rating forensics, correctly scoped

The starting intuition — "5/5 stars is very often bad data" — is **half right, and the skill must
state the correct version**, because the corpus contains both halves and they contradict each other
if stated loosely:

- **Not supported:** "a 5.0 average is inherently suspicious." Rating distributions are structurally
  J-shaped (heavy 5★, a smaller 1★ spike, thin middle) with **zero** fraud, from acquisition bias
  plus under-reporting bias (Hu, Pavlou & Zhang, *MIS Quarterly* 41(2):449–471, 2017; earlier as
  Hu, Zhang & Pavlou, *CACM* 52(10):144–147, 2009, where the first bias is called *purchasing* bias).
- **Supported and load-bearing:** a 5.0 at small `n` is *uninformative*, not excellent — compare
  lower bounds, not means (research-b F1–F3). A rating on a platform whose own base rate is ~95%
  ≥ 4.5 (Airbnb, versus TripAdvisor hotels at 3.8 and B&Bs at 4.1 — Zervas, Proserpio & Byers,
  *Marketing Letters* 32(1):1–16) carries almost no information. And the mean itself correlates
  weakly with measured quality while being inflated by price and brand (de Langhe et al.).
- **Inference, and labelled as such:** "a histogram whose 1–3★ complaint tail is missing is more
  anomalous than a merely high average." This follows *from* the J-shape papers rather than being
  measured by them — research-a F10 reasons it out, no study puts a number on it. Therefore the skill
  states it as an inference and **ships no numeric threshold**. The ">90% at 5★" figure that appears
  in research-c's artifact table has no cited source; inventing a cutoff here would be exactly the
  unsourced-threshold failure this skill exists to prevent.

So the skill teaches: `n` → lower bound → histogram shape → platform base rate → timing → reviewer
behaviour, in that order, and never the mean on its own.

Maths that ships (research-b F2–F7), with the scope error it must avoid stated out loud:

- **Wilson score lower bound** for binary signals (helpful/not, recommend/don't). Closed form.
- **Dirichlet-multinomial credible-interval lower bound** for K-star histograms. This is the correct
  analogue for star data; **Wilson's formula does not apply to a star mean** — research-b F3 and its
  dead-ends section call plugging a star average into Wilson out explicitly.
- **Bayesian / shrinkage average** toward a category prior (Laplace, Beta-Binomial, and IMDb's
  published `WR = (v/(v+m))·R + (m/(v+m))·C`, `m = 25,000` per IMDb's own help page updated
  2026-02-09 — the widely copied `m = 1,300` is stale).
- **Inverse-variance weighting** (Cochrane form) for combining heterogeneous evidence, with the
  bias-versus-variance caveat: weighting does not fix a biased source, it just averages it in.

### D6. Output contract (the recipe)

The answer IS these parts, in this order:

```
Verdict — one line, plus a confidence (low | medium | high) and the depth run
          (triage | standard | deep), so a reader can see how much work backs it
Criteria — the 3-6 named criteria, in priority order, each [measurable] or [experiential]
Evidence — table: finding | source | tier or type | who funds it | date | what it actually measures
Crowd data — n, histogram shape, platform base rate (with its year), computed lower bound,
             manipulation flags. Flags take their names from the signal set in
             `fraud-signals.md`; when none were observed the field reads `none observed`
             rather than disappearing. When the platform publishes no histogram, say the
             bound is uncomputable and why, and drop confidence by one level — never
             substitute the bare mean
Against it — REQUIRED: the strongest disconfirming finding. If none was found, name the
             disconfirmation searches that came back empty. This slot is never omitted.
What would change this verdict — 1-3 specific, findable facts
Cheapest next check — one concrete action the user can take in under five minutes
```

Two fields carry rules that decide whether the whole contract holds:

1. **The lower bound needs counts, and platforms often publish percentages.** Derive counts as
   `round(pct × n)` per bucket, state that they are derived, and note that rounding moves the bound
   in the third decimal — which is why an answer reports the bound to two, while the script's
   self-test asserts three to catch an implementation error. If only a mean is published, the bound
   is uncomputable: say so in the Crowd-data field.
2. **`z = 1.96` is the skill's fixed standard** for every bound it reports, so two runs are
   comparable. `z = 1.65` appears only as a sensitivity check, labelled as one.

`Against it` is a structural slot rather than a prose reminder, because the baseline failure is
*omission of an element from something the agent already produces* — the form `writing-skills`
prescribes for that failure is a REQUIRED field in the template, not an instruction near it.

**Calibrated language is part of the contract.** The skill's output makes claims about identifiable
businesses and named people. Manipulation findings are phrased as *consistency with a pattern*
("this review timeline is consistent with a purchased burst"), never as an accusation ("these reviews
are fake"), and an accusation is permitted only when a platform's own first-party artifact says so
(a Yelp Consumer Alert, a paused-reviews banner, a regulator's published action). Same rule for
people and trades: report the record found, not a character judgment.

### D7. Depth tiers

| Depth | Budget | Contents |
| --- | --- | --- |
| Triage | ~3 lookups | criteria; one tier-0/1 measurement or one primary database; one failure-term query. Verdict with explicitly low confidence and the cheapest next check. |
| Standard | ~8–15 lookups | full pipeline, two independent venues minimum, ownership check before counting corroboration |
| Deep | fan-out | one worker per axis: measurement, reliability/failure, ownership and conflict of interest, crowd forensics, regulatory/primary databases. **Serial fallback:** same five axes in order, each writing findings to a file before the next starts. |

Triage exists so the skill is not abandoned under time pressure — the pressure scenario in Task 1
is where that gets proven or disproven.

**Which depth applies is a rule, not a judgement call** — leave it to the agent's discretion and
the answer under pressure is always the cheapest one. Keyed on observables:

| Observable | Depth |
| --- | --- |
| The user signals time pressure, or asks to skip research, or the decision is cheap and reversible (returnable purchase, free trial, one-off consumable) | Triage |
| Anything else — this is the default, and an agent that wants a different depth must be able to point at the row that licenses it | Standard |
| The commitment is multi-unit, multi-year, or hard to reverse (fleet standardisation, a platform dependency, a contractor on a build), or the user asks for depth | Deep |

The chosen depth is named in the Verdict line (D6), which makes the choice auditable instead of
invisible.

**"Two independent venues" means different owner *and* different funding model.** Two tier-3 sites
under one parent are one venue; a tier-0 lab and a forum thread are two. This is the same rule as
"two same-owner sources are one source", stated where the venue count is set so it cannot be read
as a separate, looser test.

### D8. What the skill refuses, and where it hands off

Refuses:

- To rank on tier-3/tier-4 evidence only. It says what is missing and the cheapest check that would
  resolve it (the `cite-or-refuse` posture, cross-referenced by bare name).
- To count two same-owner sources as corroboration.
- To name a live third-party review-analyser that no longer exists.
- To treat "Verified Purchase" as proof: brushing produces genuinely verified fake reviews
  (research-a F12).
- To present a rating comparison across platforms without each platform's base rate and its year.
- To collect evidence by any means beyond ordinary reading. Read pages as a person would; no bulk
  scraping, no automated harvesting of reviewer profiles, nothing a platform's terms forbid. The
  signals in this skill are all readable from what a page shows a visitor.

Hands off — a **When NOT to use** section, because the description's triggers are broad enough to
catch questions this skill is wrong for:

| The question is really about | Goes to |
| --- | --- |
| Comparing two libraries, APIs or technical approaches on engineering merit | ordinary engineering judgement, not this skill; use it only for the *supply-side* question (is the project maintained, is the vendor solvent) |
| Whether the claims in a document the user supplied are true | `fact-check-document` |
| Pure sourcing discipline on any topic | `cite-or-refuse` |
| French insurance cover, a refused claim, a policy | `assurance-fr` |
| Whether a therapy or mental-health product works | `tcc` |
| Medical, legal or financial advice for a specific person | no skill: state the evidence, say the decision belongs with a professional |

### D9. Decay (goes in `SKILL.md`, dated)

1. **Third-party analysers die.** Fakespot shut 2025-07-01 (its Review Checker stopped 2025-06-10);
   TheReviewIndex's own site says permanently down; ReviewMeta's status is `?` — no primary source
   found, and a probe returned an ambiguous 403. Never send an agent to any of them.
2. **Affiliate economics move.** Amazon Associates rates were cut by up to 50%, reaching the US
   around 2026-03-09 — commission-driven ranking incentives shift with them.
3. **Regulation is mid-flight, and today is 2026-08-19.** Already in force: the EU Omnibus Directive
   2019/2161 (applicable since 2022-05-28); the DSA, Regulation (EU) 2022/2065 (all providers since
   2024-02-17; Arts. 27, 30 and 31 support review integrity *indirectly* — recommender transparency,
   trader traceability, marketplace compliance-by-design — they are not a fake-review ban); the FTC's
   16 CFR Part 465 (effective 2024-10-21); the EU Right to Repair Directive (EU) 2024/1799
   (applicable since 2026-07-31). Pending: the Cyber Resilience Act, Regulation (EU) 2024/2847 —
   Art. 14 reporting from **2026-09-11** (three weeks out), full application including the **5-year
   security-support requirement** (Art. 13 / Annex I) only on **2027-12-11**.
4. **Penalty figures are indexed, not fixed.** The FTC's per-violation maximum is $53,088 as of
   2025-01-17, unchanged for 2026 — it is adjusted annually for inflation, so quote it with its
   as-of date or fetch it live.
5. **Platform enforcement numbers are annual and directional.** Trustpilot's 2024 figures (4.5M
   removed, 7% of reviews, 90% auto-detected) and Google's (240M+ in 2024; 292M+ in 2025 against 1B+
   published) come from the platforms' own reports; Yelp's recommended share fell from 75% (2022) to
   70% (2025 report, published 2026-02-25). Every such percentage needs its year attached.
6. **Ownership changes.** CNET went Red Ventures (closed 2020-10-30) → Ziff Davis (Q3 2024). Check
   the parent before quoting a tier.
7. **The corpus was built by agents.** Of the 15 facts re-verified at source on 2026-08-19, five were
   wrong or stale. Treat any claim whose ledger row is not marked read-at-source as a lead.

---

## File Structure

| Path | Responsibility | Budget |
| --- | --- | --- |
| `skills/research/true-quality/SKILL.md` | frontmatter, pipeline, non-negotiable rules, output contract, depth tiers, domain map, when-not-to-use, conventions, rationalisation table, red flags, decay, kill switch | ≤ 480 lines (validator's hard limit is 500) |
| `skills/research/true-quality/references/evidence-tiers.md` | ownership-checking procedure, tier 0–4 with criteria, dated ownership map, 15-row conflict-of-interest artifact table, vendor-claim gaming | 200–350 |
| `skills/research/true-quality/references/rating-forensics.md` | the four formulas with variables and assumptions, two worked examples, histogram reading, platform base rates with years, herding/reciprocity/inflation biases, aggregation | 200–350 |
| `skills/research/true-quality/references/fraud-signals.md` | behavioural/graph/temporal signals, per-platform mechanics and first-party artifacts, regulator-forced disclosures, dead tools, query patterns | 200–350 |
| `skills/research/true-quality/references/primary-sources.md` | category → primary source routing, ≥25 named databases with URL, what-it-proves, access marker, scope limit | 250–400 |
| `skills/research/true-quality/references/source-ledger.md` | every source cited anywhere in the skill: URL, date, type, strength, read-at-source flag, why admissible | 150–400 |
| `skills/research/true-quality/scripts/rating-bounds.py` | Wilson LB, Dirichlet-multinomial LB, shrunk average, from CLI args; stdlib only; carries its own `--selftest` | ≤ 180 |
| `docs/research/true-quality/research-{a,b,c,d}.md` | raw research layer (already written) | 1,361 total |
| `docs/testing/true-quality/{baseline,microtests,green-run,smoke}.md` | test artifacts, kept out of the research directory so provenance and test logs don't blur | — |
| `agents/quality-scout.md` | optional subagent for Deep mode | ≤ 60 |

The self-test lives **inside** the script behind a `--selftest` flag rather than in a second file:
a separate test file would be copied into every agent's store as dead weight, and `SKILL.md` would
have to mention it or leave an unlinked file in the tree.

**The 480-line budget is not tight.** Estimating the mandated sections — opening and file table ~25,
pipeline 7 × 8 = 56, output contract ~30, depth tiers and selection ~20, non-negotiable rules ~25,
arbitration ~12, when-not-to-use ~12, domain map ~15, conventions ~10, rationalisation table ~14,
red flags ~8, decay ~22, kill switch ~3, cross-references ~4, plus headings and blank lines ~40 —
lands near 290. There is room for Task 10's additions without cutting a section, so an implementer
who finds themselves deleting content to fit should suspect they have inlined a reference instead.

**Two invariants have no automated enforcer**, unlike the line limit and the reference links, which
the validator checks: *no numeric threshold without a cited source*, and *no platform percentage
without its year*. Task 6's ledger is the enforcement mechanism — a threshold or percentage in any
file must have a ledger row — and Task 13 adds the runnable spot check that closes the loop.

---

## Task 1: The RED baseline

**Files:**
- Create: `docs/testing/true-quality/baseline.md`
- Creates nothing under `skills/` — an empty directory is not committable, and the first commit that
  touches `skills/research/true-quality/` should be one the validator can pass.

**Interfaces:**
- Produces: `baseline.md` — the **pinned scenario inputs** and the verbatim rationalisations. Tasks 7,
  9 and 10 quote from it. No skill text is written before this file exists.

**The Iron Law applies to documentation:** no skill before a watched failure. Run each scenario in a
fresh context with **no** skill loaded, capture the answer verbatim, and classify each failure as
discipline or shape (D2).

- [ ] **Step 1: Write the eight baseline scenarios into `baseline.md`**, verbatim, before running any:

  1. **S1 listicle pull** — "Which 14-inch laptop should I buy for about €1,200? I mainly do
     software development and travel a lot."
  2. **S2 star average** — "This dehumidifier on Amazon has 4.8 stars from 12,000 ratings. Is it
     good?"
  3. **S3 popularity as quality** — "Should we adopt this library? It has 40k GitHub stars."
     Scope note for the rubric: per D8 this is *partly* out of scope. A correct answer addresses the
     supply-side question (maintained, funded, patched, bus factor) and says plainly that the
     engineering-merit question is not what this skill answers. Scoring a correct scope-refusal as a
     failure is the trap to avoid here.
  4. **S4 time pressure (discipline)** — "I'm buying in ten minutes, don't research it, just tell me
     which of these two mattresses is better." (combined pressures: time + explicit instruction to
     skip work + a forced binary)
  5. **S5 base-rate blindness** — "This apartment has 4.9 stars from 200 guest reviews. Safe bet?"
  6. **S6 service / trade** — "Is this roofing contractor legit? They have 5.0 on Google with 38
     reviews."
  7. **S7 authority laundering** — "A major tech site's round-up says model X is the best in its
     class. Confirm that for me." (tests whether the agent launders a tier-3 affiliate ranking as
     corroboration, and whether it caves to the user's framing)
  8. **S8 Deep mode** — a question wide enough to need the fan-out: "We're standardising on one
     laptop model for a 40-person team for the next three years. Which one, and what's the risk?"
     (Task 12's gate depends on this run existing.)

- [ ] **Step 2: Pin every scenario's inputs before running anything.** RED and GREEN must face
      identical evidence, or the difference between them measures search-result drift instead of the
      skill. For each scenario record in `baseline.md`: the exact product/model/brand strings, the
      exact URLs the run may use as its starting point, and — for S2, S5, S6 — a **fixed star
      histogram and review count**, written out, so the arithmetic is comparable across runs. Where a
      real listing is used, archive it (`web.archive.org`) and cite the snapshot.
- [ ] **Step 2a: The archived snapshot is authoritative, not the live page.** Once a scenario's
      inputs are pinned and archived, the archive is what both RED and GREEN read. A live listing
      whose histogram or review count moves between the two runs invalidates the comparison, and the
      failure mode is silent: the GREEN run looks better or worse for reasons that have nothing to do
      with the skill. Record the snapshot URL beside each scenario.
- [ ] **Step 2b: Record `n` as a rating count, not a review count.** Several platforms publish both,
      and they differ — a star histogram usually covers *ratings* while the visible review list
      covers *reviews with text*. Mixing them produces a bound computed from the wrong denominator.
      Pin which number each scenario's histogram belongs to.
- [ ] **Step 3: Run all eight in fresh contexts with no skill.** Parallel workers are fine; each
      returns the full answer text plus its own account of why it chose those sources.
- [ ] **Step 4: Record verbatim** in `baseline.md`, per scenario: sources cited (with tier, assigned
      by hand); whether `n`, histogram, base rate, ownership, disconfirmation appeared at all;
      whether uncertainty was stated; the exact rationalisation sentences.
- [ ] **Step 5: Classify** each failure as discipline or shape, and tally which appear in ≥5 of 8
      runs. Those are the failures the skill's *discipline* rules must address, and Task 7 step 6
      traces each such rule back to this tally. Corpus-hygiene rules — never cite a dead analyser,
      never quote an undated platform percentage, never invent a threshold — are exempt from the
      tally by construction: a baseline agent that has never read the corpus cannot exhibit them, so
      requiring baseline evidence for them would make the rule set unsatisfiable. Record which rules
      are baseline-driven and which are hygiene, because Task 10 only re-tests the first kind.
- [ ] **Step 6: Commit (local only — do not push; see Global Constraint 11).**

```bash
git add docs/
git commit -m "true-quality: research corpus, plan, and RED baseline"
```

**Acceptance:** `baseline.md` contains eight scenario sections with pinned inputs, verbatim output
excerpts and a discipline/shape label, plus a frequency tally. If a scenario shows **no** failure, it
is recorded as such and the corresponding guidance is dropped from the skill rather than written
speculatively.

**If three or more of the eight scenarios show no failure, stop and say so** rather than proceeding.
The skill's premise is that unassisted agents reliably get this wrong; a mostly-clean baseline is
evidence against the premise, and the right response is a smaller skill — or none — not a skill
written against failures that did not occur.


---

## Task 2: `references/evidence-tiers.md`

**Files:**
- Create: `skills/research/true-quality/references/evidence-tiers.md`
- Read: `docs/research/true-quality/research-c-conflict-of-interest.md` (F1–F29, tier hierarchy,
  artifact table, query patterns)

**Interfaces:**
- Produces: the tier names `Tier 0`–`Tier 4` and the artifact-table row numbers that `SKILL.md`'s
  audit step and the output contract's `tier` / `who funds it` columns refer to. Fixed vocabulary —
  Tasks 3, 4, 5 and 7 use these exact labels.

- [ ] **Step 1: `## Contents` list first** (the file will exceed 100 lines with ≥2 sections; the
      validator fails without it).
- [ ] **Step 2: The ownership-checking procedure, before the map.** Read the Terms of Service or
      Privacy Policy for the *contracting legal entity*, not the masthead; search
      `"[site]" "owned by"`; check whether the affiliate `tag=` value matches another brand; check
      Wayback snapshots for a tone shift around an acquisition date. The procedure is the durable
      part; the map below decays.
- [ ] **Step 3: Tier table** — the five tiers with the *placement criterion* for each, ≥3 named
      examples per tier, and one line per named source on what it is good for, what it is not, and
      whether it is paywalled. Carry research-c's qualified placements as qualifiers, not as clean
      tiers (Hardware Unboxed at the 1/2 boundary; DXOMARK at the 2/3 boundary because of its
      parent's manufacturer-consulting revenue). For Consumer Reports, state that the >$30M testing
      figure is CR's own forward projection, not audited spend.
- [ ] **Step 3a: The label sets, in one place** — both ladders from D4: the 0–4 recommendation tiers
      and the primary-evidence types (`regulator`, `operator-dataset`, `peer-reviewed`, `preprint`,
      `platform-first-party`, `vendor-terms`, `vendor-marketing`). State which column of the output
      contract's Evidence table takes which, and that the ledger's `type` column uses the same
      vocabulary. Every other file points here rather than restating it.
- [ ] **Step 4: Dated ownership map**, every row carrying a **closing** date (not a signing date) and
      its primary source: Red Ventures — Bankrate (closed 2017-11-08, per Bankrate's 8-K exhibit) and
      The Points Guy; CNET — Red Ventures (agreed 2020-09-14, closed 2020-10-30, ~$500M) then **Ziff
      Davis (completed Q3 2024)**, which is its owner today; Future plc; Valnet; Dotdash Meredith;
      Kape Technologies — Webselenese for $149.1M announced 2021-03-08, plus CyberGhost (2017-03),
      PIA (2019-11), ExpressVPN (2021-12); EIG/Newfold, marked as pattern-level evidence with no
      adjudicated case. Head the section with the standing instruction to re-check the parent before
      quoting a tier.
- [ ] **Step 5: Conflict-of-interest artifact table** — all 15 rows from research-c: `tag=` and other
      affiliate parameters; third-party redirect domains (`go.skimresources.com`,
      `redirect.viglink.com`, `linksynergy.com`); `rel="sponsored"` and why it is an SEO signal and
      **not** a reader disclosure under 16 CFR Part 255; disclosure placement at the link versus in a
      footer; parent absent from About while independence is claimed; award badges with no published
      criteria or visible non-winners; ranking changes correlated with partnership news (Wayback
      Machine); verbatim prose duplicated across domains; a niche site whose top pick is always one
      brand; the missing-middle histogram — **stated as an inference, with no numeric threshold, per
      D5**; review-volume bursts; sub-brands parked on a news domain (site-reputation abuse); "up to"
      claims with no independent measurement; lead-capture gates.
- [ ] **Step 6: Vendor-claim gaming section** — benchmark detection and whitelisting (Samsung GOS,
      Huawei 3DMark, Dieselgate as the general "detect the test" mechanism), sustained versus burst
      performance, "up to" as a ceiling, silent SKU revisions and regional variants, cherry-picked
      baselines. Each ends in the *testable question* the claim converts into.
- [ ] **Step 7: The two named "hard" cases** for calibration: Casper v. Sleepopolis (2016-04; $40k in
      SEO fees from a competitor while reviewing it; ~33,000 sales and ~$1.6M in commissions over 18
      months; critic later acquired by the plaintiff's financier) and FTC v. LendEDU (2020: paid rank
      placement plus 90% fabricated Trustpilot reviews).
- [ ] **Step 8: Verify before entry (Global Constraint 10).** Every ownership date, transaction value
      and enforcement case is checked at a primary source — SEC filing, company press release, FTC
      complaint, court docket — as it is written, not afterwards. Anything that will not verify is cut
      or carries a leading `?` plus a ledger row. Do not copy a date from the research layer without
      opening its source: the CNET ownership error in this plan's first draft came from exactly that.
- [ ] **Step 9: Commit (local only).**

**Acceptance:** 5 tiers × ≥3 examples; procedure precedes the map; 15-row artifact table with a "how
to check" column; every ownership and enforcement claim carries a closing date and a primary URL
opened during the task; no unsourced numeric threshold anywhere; `## Contents` present; ≤ 350 lines.

---

## Task 3: `references/rating-forensics.md` and `scripts/rating-bounds.py`

**Files:**
- Create: `skills/research/true-quality/references/rating-forensics.md`
- Create: `skills/research/true-quality/scripts/rating-bounds.py`
- Read: `docs/research/true-quality/research-b-rating-statistics.md` (F1–F20)

**Interfaces:**
- Produces: the CLI contract
  `python3 $SKILL_DIR/scripts/rating-bounds.py --hist n1,n2,n3,n4,n5 [--binary pos,n]
  [--prior mean,strength] [--z 1.96] [--selftest]`, printing the naive mean, the
  Dirichlet-multinomial lower bound, the Wilson lower bound when `--binary` is given, and the shrunk
  average when `--prior` is given. `SKILL.md` step 3 and Tasks 9 and 11 cite this exact invocation.

- [ ] **Step 1: Write the failing self-test first.** Embed research-b F3's two histograms verbatim —
      Item A `0,0,0,2,21` (n=23, raw mean 4.913) and Item B `82,123,246,779,2870` (n=4,100, raw mean
      4.520) — and assert the Dirichlet-multinomial lower bounds **4.215** and **4.491** to 3 dp at
      `z = 1.96`, so the naive ranking reverses. Add the F2 binary case (2-of-2 versus 100-of-101)
      asserting the 100/101 item ranks higher. Compare with a numeric tolerance
      (`abs(got - want) < 5e-4`), never string equality — float formatting differs across interpreter
      versions and a string comparison would fail on a correct implementation. Both expected values
      were re-derived by hand during
      hardening (see Verification record) — they test the formula, and the reference file must say
      the histograms are illustrative constructions, not measured data.
- [ ] **Step 2: Run it. Expect failure** — no such file.
- [ ] **Step 3: Implement the script**, stdlib only, `argparse`, no third-party import:
      Dirichlet(1,…,1) posterior over the histogram, posterior mean and variance of the linear score
      `f(p) = Σ k·p_k`, normal-approximation lower bound at `z`; Wilson lower bound for `--binary`;
      Beta/IMDb-form shrinkage for `--prior`. Print each result with its formula name and `n`. No
      `compatibility` frontmatter field will declare `python3` (Global Constraint 3), so the script's
      own `--help` and the reference file are where the requirement is stated.
- [ ] **Step 4: Run `--selftest`. Expect pass**, both bounds to 3 dp.
- [ ] **Step 5: Write the reference file** — `## Contents`, then: why a mean is not an estimate;
      Wilson (with its binary-only scope stated as a prohibition, since research-b's dead-ends
      section shows this is the error people actually make); Dirichlet-multinomial with the full
      formula and both worked examples; Laplace / Beta-Binomial / IMDb `WR` with `m = 25,000` (IMDb
      help page, updated 2026-02-09) and a note that `m = 1,300` is stale; James–Stein in one
      paragraph as "why category priors help"; inverse-variance weighting with the bias caveat.
      State the `python3` requirement here, plus the hand-computation path for when it is absent.
- [ ] **Step 6: Add the distribution and bias sections** — J-shape as the honest baseline (Hu, Pavlou
      & Zhang, MISQ 41(2), 2017; Hu, Zhang & Pavlou, CACM 52(10), 2009 — note the reversed author
      order and that CACM calls it *purchasing* bias where MISQ calls it *acquisition* bias) and what
      the *anomalous* shapes are, marked as inference with no threshold; herding (Muchnik, Aral &
      Taylor, *Science* 341(6146):647–651, 2013 — randomised; **+32% likelihood that a later rater
      rates positively**, and separately **+25% in the final aggregate score**; keep the two figures
      distinct and never compress them into a range) and why early ratings on a young listing deserve
      extra scepticism; sequential and anchoring bias and the effect of the page's default sort order;
      reciprocity and retaliation in two-sided markets (Airbnb ~95% of listings ≥ 4.5 versus
      TripAdvisor hotels 3.8 and B&Bs 4.1 — Zervas, Proserpio & Byers, *Marketing Letters* 32(1),
      2021; plus eBay's effective-percent-positive worked example); cross-cultural extreme-response
      style; the early-review / late-failure window mismatch and the pointer to reliability data.
- [ ] **Step 7: Platform base-rate table**, one row per platform, each figure carrying **the year it
      describes** and its source: Airbnb ~95% ≥ 4.5 (2021 paper); Yelp **70% recommended / 17% not
      recommended** (Yelp's own report published 2026-02-25 — *not* the stale 75% from 2022);
      Trustpilot 7% of 2024 reviews removed as fake, 90% auto-detected (Trust Report, 2025-05-29);
      Google 240M+ removed in 2024 and 292M+ in 2025 against 1B+ **published** reviews. For Google
      Business Profile *average ratings*, either omit the 3.74 → 4.11 drift or label it plainly as a
      reputation-management vendor's report over 53 of its own client brands (31,326 profiles,
      Jan 2015 – Jul 2022) — no neutral source exists for it. A rating is only readable against its
      own platform's norm, and the norm has a date.
- [ ] **Step 8: Dead-ends section** — no threshold on the 5★:4★ ratio is sourced; Benford digit
      analysis does not apply to star values (only weakly to review word counts); "5.0 is inherently
      suspicious" is not supported as a standalone rule; Wilson on a star mean is a scope error.
- [ ] **Step 9: Verify before entry.** Every figure in the base-rate table is read off the
      platform's or publisher's own page during this task, with its date recorded for the ledger.
- [ ] **Step 10: Commit (local only).**

```bash
python3 skills/research/true-quality/scripts/rating-bounds.py --selftest
```

**Acceptance:** `--selftest` passes and reproduces 4.215 / 4.491; every formula states its variables
and assumptions; the illustrative-histogram caveat is present; the base-rate table has a year and a
primary URL per row; the herding figures are stated separately; `## Contents` present; no third-party
import; no `compatibility` field anywhere.

---

## Task 4: `references/fraud-signals.md`

**Files:**
- Create: `skills/research/true-quality/references/fraud-signals.md`
- Read: `docs/research/true-quality/research-a-review-fraud.md` (F1–F32 + regulatory + tools)

**Interfaces:**
- Produces: the named signal set (`singleton`, `burst`, `co-review`, `missing tail`, `template
  structure`, `platform fraud banner`) that `SKILL.md` step 3 and the output contract's
  "manipulation flags" field enumerate.

- [ ] **Step 1: `## Contents`.**
- [ ] **Step 2: Signals section, strongest first, each with what the agent can observe from a public
      page:** behavioural and graph signals beat linguistic ones (Jindal & Liu, WSDM 2008: 68% of
      reviewers wrote exactly one review, 8% wrote ≥5; near-duplicate text across accounts, labelled
      at Jaccard ≥ 0.9); Yelp's filter tracks behavioural features, not language (Mukherjee et al.
      2013); fraud incentive peaks at weak reputation (Luca & Zervas, *Management Science*
      62(12):3412–3427 — "roughly 16%" of Yelp restaurant reviews filtered); collective detection
      beats single-signal (SpEagle, KDD 2015); temporal burstiness correlated with rating direction
      (Xie et al., KDD 2012); purchased-review campaigns move ratings and then decay, and target
      already-successful listings too (He, Hollenbeck & Proserpio, *Marketing Science* 41(5):896–921,
      2022 — mark as abstract-sourced, the publisher page 403s).
- [ ] **Step 3: State the LLM erosion explicitly** — Ott et al. (ACL-HLT 2011, 309–319) reached
      "nearly 90%" with a bigram+LIWC SVM on imaginative-versus-informative language, and that signal
      is now **weakened**: a 2025 preprint (arXiv:2506.13313) found humans at 50.8% accuracy — chance
      — on LLM-written fake reviews, with LLM judges equivalent or worse. Cite it as a preprint, not
      as peer-reviewed. Therefore: fluency and specificity are no longer evidence of authenticity;
      fall back on behavioural, graph and temporal signals, and on repeated paragraph *structure*
      across a batch.
- [ ] **Step 4: Per-platform mechanics and first-party artifacts** — Amazon (brushing produces real
      Verified Purchase badges; the mandatory Vine badge; ASIN merging and review hijacking, with the
      "review text describes a different product" tell); Trustpilot (invited versus organic; 2024:
      4.5M removed = 7% of reviews posted, 90% auto-detected, per the Trust Report published
      2025-05-29); Google Business Profiles (review gating is banned; the "reviews paused" banner is
      the platform's own fraud call, surfaced to the consumer; 240M+ removed in 2024, 292M+ in 2025);
      Yelp (**70% recommended / 17% not recommended** per its 2025 report, the not-recommended list
      is readable, four Consumer Alert types); app stores (incentivised-review bans, rating resets on
      version change); Booking-style stay-gated models and their loopholes; G2 / Capterra /
      TrustRadius disclosed gift-card programmes; GitHub stars (StarScout: ~6M suspected fake) and
      npm download pumping.
- [ ] **Step 5: Regulation as artifact generator.** One line each on the *observable* artifact the
      rule forces onto the page — that is the only reason regulation is in a skill about quality.
      FTC 16 CFR Part 465 (effective 2024-10-21; civil penalty **$53,088 per violation as of
      2025-01-17, adjusted annually for inflation — state the mechanism and the as-of date, never a
      bare figure**; the proposed review-hijacking ban was **dropped** from the final rule and is
      pursued under the FTC Act instead); 16 CFR Part 255 (Endorsement Guides, effective 2023-07-26);
      EU Omnibus Directive 2019/2161 and UCPD Annex I (applicable since 2022-05-28); the DSA,
      Regulation (EU) 2022/2065, Arts. 27, 30 and 31 — **recommender transparency, trader
      traceability and marketplace compliance-by-design, which support review integrity indirectly
      and are not a fake-review ban**; UK DMCC Act 2024 Schedule 20 with CMA208; France DGCCRF plus
      NF Z74-501 / ISO 20488.
- [ ] **Step 6: Dead tools, first-class** — Fakespot (Mozilla, shut 2025-07-01; Review Checker
      stopped 2025-06-10), TheReviewIndex (its own About page says permanently down), ReviewMeta
      (`?` status: no primary source, a probe returned an ambiguous 403). Marked "do not instruct
      anyone to use these", with ReviewMeta's uncertainty stated rather than hidden.
- [ ] **Step 7: Query patterns** — the 15 copy-pasteable patterns from research-c's search section
      (failure terms, `site:` restriction to tier-0/1 domains, `after:` date filters, teardown,
      recall/class-action, "one year later", exact-phrase duplicate check, ownership lookup, forum
      broadening with `-site:`), plus the Wayback Machine step for anything historical. Include the
      caveat that forum consensus is itself manipulable and needs two differently moderated venues,
      and the ordinary-reading bound from D8 (no bulk collection).
- [ ] **Step 8: Myths section** — kill all seven from research-a: "5.0 is suspicious", "more reviews
      = more trustworthy", "verified = genuine", "detailed = trustworthy", "use Fakespot/ReviewMeta",
      "read only the 1-star reviews", "no reviews = bad".
- [ ] **Step 9: Verify before entry.** Every platform percentage, rule number, effective date and
      penalty figure is read at the platform's own report, the Federal Register / eCFR, or EUR-Lex
      during this task. The five errors in the Verification record were all of exactly this type.
- [ ] **Step 10: Commit (local only).**

**Acceptance:** ≥8 platforms, each with a first-party observable artifact and a year on every
percentage; every academic claim carries author, year, venue, and preprints are marked as such; the
DSA articles are described by what they actually require; the FTC penalty carries its mechanism and
as-of date; dead tools marked with ReviewMeta's `?`; 15 query patterns; `## Contents`.

---

## Task 5: `references/primary-sources.md`

**Files:**
- Create: `skills/research/true-quality/references/primary-sources.md`
- Read: `docs/research/true-quality/research-d-objective-data.md` (F1–F39 + worked examples)

**Interfaces:**
- Produces: the category vocabulary used by `SKILL.md`'s domain map — `durable hardware`, `vehicle`,
  `appliance`, `software/SaaS`, `open-source dependency`, `lodging`, `trade or professional service`,
  `consumable` — and the routing table keyed on it.

- [ ] **Step 1: `## Contents`.**
- [ ] **Step 2: Routing table** — one row per category: the question to ask, the primary sources in
      order, and the first thing to check. This is the table `SKILL.md` step 2 dereferences.
- [ ] **Step 3: Source entries, ≥25**, each with URL, one-line "what it proves",
      `free / registration / paywalled`, and its **scope limit**: Backblaze Drive Stats; Puget
      Systems; TÜV Report; ADAC Pannenstatistik; J.D. Power IQS/VDS *with* its methodology caveats;
      NHTSA complaints/TSBs/recalls; EU Safety Gate; RappelConso; CPSC SaferProducts; EPREL and the
      2021 label rescaling; the EU tyre label; France's `indice de réparabilité` → `indice de
      durabilité` transition; ecodesign spare-parts rules; ENERGY STAR; FCC ID lookup as a way to
      identify the actual hardware inside a product; UL Product iQ — with the explicit contrast that
      **CE marking is self-declared and has no equivalent public registry**; iFixit repairability
      scores and teardowns; endoflife.date; NVD/CVE read without punishing audited projects; OpenSSF
      Scorecard; deps.dev; status pages and post-incident history; CPAverify and AICPA peer review
      for SOC 2 claims (there is no public SOC 2 registry); CourtListener/PACER; Companies House;
      Pappers / BODACC / INPI; a US state licence board (e.g. CSLB); resale price after N years.
- [ ] **Step 4: Get the EU timeline right**, since three regimes overlap and today is 2026-08-19:
      Right to Repair Directive (EU) 2024/1799 — **applicable since 2026-07-31**, subject to national
      transposition; Cyber Resilience Act Regulation (EU) 2024/2847 — Ch. IV since 2026-06-11,
      Art. 14 reporting from **2026-09-11**, and the **5-year security-support requirement only from
      2027-12-11**, which is the single most consequential date correction from hardening; ecodesign
      spare-parts rules per product category. Mark each as in force or pending, with the date.
- [ ] **Step 5: Interpretation rules** — absence of a recall is informative only against market size;
      warranty length is a real signalling bet but only from a brand with something to lose;
      litigation is informative as a *pattern* of similar successful claims, never as "has been
      sued"; survey aggregators are not lab measurements, so check `N` and weighting; a certification
      logo on a box is not a certification — verify in the registry.
- [ ] **Step 6: Five worked chains**, question → source → what it answers, one each for a laptop, a
      dishwasher, a SaaS tool, an open-source dependency and a roofing contractor. Copy the shape
      from research-d's worked examples; these double as the skill's examples.
- [ ] **Step 7: Verify before entry** — every URL is opened during this task; anything unreachable is
      marked `UNVERIFIED-STATUS` with the date checked, and every regulatory date is read at EUR-Lex
      or the Commission's own summary rather than taken from the research layer. Drop the Mindfactory
      RMA lead entirely — research-d could not find a live source, and a dead lead in a routing table
      costs an agent a wasted search every time.
- [ ] **Step 8: Commit (local only).**

**Acceptance:** ≥25 sources, each with URL + what-it-proves + access marker + scope limit; every URL
opened this session or flagged; the EU timeline distinguishes in-force from pending with dates; five
worked chains; routing table keyed on the eight categories; `## Contents`.

---

## Task 6: `references/source-ledger.md`

**Files:**
- Create: `skills/research/true-quality/references/source-ledger.md`

**Interfaces:**
- Consumes: every citation introduced by Tasks 2–5.
- Produces: the provenance record `SKILL.md` points at for "is this source admissible" and "was this
  read at source" — the `tcc` ledger pattern.

- [ ] **Step 1: `## Contents`,** then one table per reference file.
- [ ] **Step 2: One row per source**: URL, title, date, type (peer-reviewed / preprint / regulator /
      platform first-party / vendor methodology / industry report / anecdotal), which finding it
      supports, **read at source | abstract only | snippet only**, and why it was admissible. The
      read-at-source column is mandatory and has no default — a blank means the claim may not appear
      in any reference body, only here.
- [ ] **Step 3: Carry the hardening verdicts in.** The five corrected facts from this plan's
      Verification record each get a row recording the wrong value, the corrected value, and the
      primary source — so a future editor cannot reintroduce them from the research layer.
- [ ] **Step 4: Rejected-source rows.** "Only marketing pages assert this" is a finding worth
      keeping — it stops the next agent re-searching a dead end. Includes the Google average-rating
      drift (vendor client sample) and ReviewMeta's unverifiable status.
- [ ] **Step 5: Open-question rows** — carry across the four research files' open questions, notably:
      the Askalidis et al. (2017) DOI; a directly loaded (non-403) copy of He/Hollenbeck/Proserpio;
      a primary statement on the Wirecutter editorial firewall; a directly adjudicated hosting-review
      case; whether any live retailer RMA dataset exists in 2026; a neutral source for platform
      average-rating drift.
- [ ] **Step 6: Commit (local only).**

**Acceptance:** every URL appearing anywhere in the skill has a ledger row with a non-blank
read-at-source value; the five corrections are recorded; rejected sources and open questions present;
`## Contents`.

---

## Task 7: `SKILL.md` (GREEN)

**Files:**
- Create: `skills/research/true-quality/SKILL.md`
- Read: `docs/testing/true-quality/baseline.md`, all five reference files

**Interfaces:**
- Consumes: the tier labels (Task 2), the script CLI (Task 3), the signal names (Task 4), the
  category vocabulary (Task 5).
- Produces: the frontmatter `name: true-quality` and the output contract that Tasks 8–11 test.

- [ ] **Step 1: Frontmatter.** `name: true-quality`, `description`, and nothing else — **no
      `compatibility`** (Global Constraint 3). Third person, ≤ 1024 chars, triggers in English and
      French, and — per the SDO rule — **no summary of the workflow**, because a description that
      summarises the process becomes the shortcut agents take instead of reading the body. Draft:

      > Use when the real quality of something has to be established from internet evidence and the
      > obvious sources are compromised — choosing between products, models, brands, tools,
      > services, lodgings, contractors or suppliers; judging whether a rating, a review pool, a
      > "best X" ranking, a benchmark or a vendor spec can be trusted. Triggers: "is X actually any
      > good", "which X should I buy", "best X", "is X worth it", "are these reviews fake", "why is
      > this rated so highly", "quel est le meilleur", "est-ce que ça vaut le coup", "faux avis".
      > Also when a previous answer leaned on a listicle, an affiliate round-up, a star average or a
      > manufacturer claim.

      Note the deliberate omission of "compare X and Y" from the trigger list: it fires on ordinary
      engineering comparisons the skill is wrong for. The When-NOT-to-use table (step 7) is the
      backstop.
- [ ] **Step 2: Opening** — `compiled 2026-08-19` stamp; the `$SKILL_DIR` sentence with the word
      `notation` inside 120 characters of it; the file table linking **all five** reference files by
      relative path in `](references/x.md)` form plus the script, each with "when to open it" (an
      unlinked reference file is a validator failure); and the core principle in two sentences:
      *quality is measured, not rated; the cheapest evidence to fake is the evidence most search
      results are made of.*
- [ ] **Step 3: The pipeline**, D3's seven steps, each ≤ 8 lines, each naming the reference it
      dereferences and the concrete artifact it produces.
- [ ] **Step 4: The output contract**, verbatim from D6 including the calibrated-language rule, as a
      fenced template with `Against it` marked REQUIRED in the template itself.
- [ ] **Step 5: Depth tiers**, D7's table **and its selection rule**, with Triage first so the
      pressured path is the visible one and the rule that licenses each depth is impossible to miss.
- [ ] **Step 6: Non-negotiable rules**, numbered, in two labelled groups per Task 1 step 5 —
      **baseline-driven** (each traceable to a ≥5-of-8 failure) and **corpus hygiene** (no baseline
      evidence required or possible):
      *Baseline-driven:* never answer from memory; a vendor claim is evidence of a promise, never of
      quality; every source carries a tier-or-type and a funder or it cannot support a verdict; never
      report a mean without `n`, histogram, base rate (with its year) and lower bound; two same-owner
      sources are one source; run at least one disconfirmation search per finalist; state criteria
      before ranking.
      *Corpus hygiene:* refuse to rank on tier-3/4 evidence alone and say what is missing; never cite
      a dead analyser, an undated platform percentage or an unversioned legal regime; never invent a
      numeric threshold the sources do not give; never collect evidence beyond ordinary reading.
- [ ] **Step 7: Arbitration table and the When-NOT-to-use table**, D4's second table and D8's
      hand-off table, including the routes to `assurance-fr` and `tcc` and the no-professional-advice
      line.
- [ ] **Step 8: Domain map** — question shape → which reference and which section. The `tcc` pattern:
      route before researching.
- [ ] **Step 9: Conventions block** — define the `?` prefix inline ("`?` marks a claim not read at
      source; never promote one to a plain assertion without opening its source, and never drop the
      prefix when quoting"), since a fresh agent has no access to this repo's own conventions. Add
      the ordinary-reading bound from D8.
- [ ] **Step 10: Rationalisation table and red flags**, seeded from `baseline.md`'s verbatim
      sentences, not invented. Expect entries like "the reviews are overwhelmingly positive, that's
      enough", "it's a reputable tech site", "the user said not to research", "no time for the full
      pipeline", "I know this category well" — but only those that actually appeared.
- [ ] **Step 11: Decay section**, D9's seven items, each dated, including the note that the corpus
      was agent-built with a measured 5-of-15 error rate at first verification.
- [ ] **Step 12: Kill switch.** State, in one line, how to stop the skill loading autonomously if its
      breadth proves wrong in practice: add `disable-model-invocation: true` and the matching
      "explicit invocation only" prose, or remove it from the store. This matters because in this
      setup installing a skill *is* activating it (`skills.enableAgentsUser: true`), so there is no
      separate off switch.
- [ ] **Step 13: Cross-references** by bare name: `cite-or-refuse` for sourcing discipline,
      `fact-check-document` when the input is a document of claims rather than a purchase question.
      No namespace prefix, no `@` link, no `superpowers:` form (the lint rejects it).
- [ ] **Step 13a: The no-network conditional.** Every step of the pipeline assumes live search and
      page access. State what the skill does when it has neither: it says so, answers nothing from
      memory, and names the two or three lookups a human should run — the `cite-or-refuse` posture.
      Without this, an offline agent will fall back on recall, which is the exact failure the skill
      exists to prevent.
- [ ] **Step 14: Run the validator and the length check.** This is the first point at which the
      validator can be green.

```bash
node scripts/validate.mjs
wc -l skills/research/true-quality/SKILL.md   # must be under 500
```

- [ ] **Step 15: Commit. Push now if you want CI to see it** — this is the earliest safe push.

**Acceptance:** validator passes; body < 500 lines; all five references linked and resolving; each
non-negotiable rule maps to a baseline failure; description carries no workflow summary and no
"compare X and Y" trigger; When-NOT-to-use present; `?` convention defined; kill switch stated; no
`compatibility` field; no COUPLING-pattern string anywhere in the tree.

---

## Task 8: Micro-test the output contract's wording

**Files:**
- Modify: `skills/research/true-quality/SKILL.md` (contract section only)
- Create: `docs/testing/true-quality/microtests.md`

The output contract is behaviour-shaping guidance, so `writing-skills` requires it be micro-tested
against a no-guidance control **before** the expensive pressure scenarios — micro-tests verify
wording, scenarios are the final gate. Running them in the other order means every scenario result
is stale the moment the wording changes.

- [ ] **Step 1: Three arms**, 5 fresh single-shot reps each, same task (S2's pinned histogram, plus a
      rating quoted at small `n`): (A) no contract; (B) the contract as a recipe (D6); (C) the
      contract expressed as prohibitions ("don't bury the verdict, don't omit uncertainty").
      **Score each rep on two measures, both defined before the runs:** *compliance* = how many of
      D6's seven parts are present, in order, correctly filled (0–7, counted by hand); *variance* =
      how many distinct output shapes appear across that arm's five reps. The winner needs a strictly
      higher mean compliance than the control **and** at most two distinct shapes; an arm that wins
      on compliance while producing five different shapes has not produced binding wording.
- [ ] **Step 2: Control check first.** If arm A already produces the right shape, delete the *shape
      recipe* — there is nothing to fix and the words are dead weight. Delete only the recipe: the
      REQUIRED `Against it` slot and the calibrated-language rule are separate requirements that this
      test does not measure, and Task 11 step 4 depends on the second one. Record in `microtests.md`
      that D6's recipe was unnecessary, and drop the contract-shape group from Task 9's rubric so its
      acceptance criterion does not score against a section that no longer exists.
- [ ] **Step 2a: If arm C wins, the evidence overrides the design.** D2 asserts, on
      `writing-skills`' authority, that prohibitions backfire on shaping failures. If the
      prohibition arm measurably beats the recipe arm here, ship the prohibition wording and record
      the result in `microtests.md` as a correction to D2's prior for this case — a wording test that
      contradicts the assumption behind it is a finding, not a run to discard.
- [ ] **Step 3: Read every flagged match by hand.** Template echoes and quoted counter-examples
      masquerade as hits; automated counting alone overstates both success and failure.
- [ ] **Step 4: Keep the arm that wins on both compliance and variance.** Five different shapes
      across five reps means the wording is not binding — tighten the form, do not add words.
- [ ] **Step 5: Record all 15 runs** in `microtests.md` with the verdict and the reasoning.
- [ ] **Step 6: Commit.**

**Acceptance:** 15 runs recorded; the control arm's behaviour documented; the shipped wording is the
winning arm, with its win stated in terms of both compliance and variance.

---

## Task 9: GREEN verification — re-run the eight scenarios with the skill

**Files:**
- Create: `docs/testing/true-quality/green-run.md`

- [ ] **Step 1: Re-run all eight Task-1 scenarios** in fresh contexts, skill loaded, **using the
      pinned inputs from `baseline.md`** so the comparison is against the same evidence, not against
      a different day's search results.
- [ ] **Step 2: Score each run against the rubric, in two groups, per its applicability matrix.**
      *Contract-shape lines*, one per D6 part, mechanically checkable: verdict first with confidence
      and depth named; criteria listed before any ranking; Evidence table with a tier-or-type and a
      funder per row; Crowd-data field present (`none observed` counts as present); `Against it`
      non-empty or its empty searches named; falsifiers listed; cheapest next check present.
      *Process lines*, from the non-negotiable rules: ownership checked before corroboration was
      counted; at least one disconfirmation search run per finalist; the depth taken matches D7's
      selection rule. Four further lines — `n`, derived-or-published histogram, base rate with its
      year, computed lower bound — apply **only to S2, S5 and S6**, the scenarios that quote a
      rating; scoring them against S1, S3, S4, S7 or S8 is a category error, not a failure. The
      split matters for routing: a contract-shape miss is Task 8's problem (wording), a process miss
      is Task 10's (discipline). Write the matrix into `green-run.md` before scoring.
- [ ] **Step 3: Record every new rationalisation verbatim** — these are Task 10's input.
- [ ] **Step 4: S4 is the discipline gate.** Under explicit instruction to skip research, the
      acceptable behaviour is the Triage path with confidence stated — not a confident answer, and not
      a refusal to answer at all. If the run does either, the skill fails and Task 10 fixes it.
- [ ] **Step 5: S8 is the Deep-mode gate.** Record whether the fan-out produced findings the Standard
      path would have missed, and whether the serial fallback is actually followable as written. This
      result is what Task 12 is gated on.
- [ ] **Step 6: Commit.**

**Acceptance:** every applicable rubric line satisfied in ≥7 of 8 runs; S4 takes the Triage path;
S8's Deep-mode outcome recorded either way; all new rationalisations captured verbatim.

---

## Task 10: REFACTOR — close the loopholes

**Files:**
- Modify: `skills/research/true-quality/SKILL.md`

- [ ] **Step 1: Add a rationalisation-table row per new excuse** from Task 9, verbatim on the left,
      the counter on the right. No paraphrasing — the exact sentence is what the next agent will
      think.
- [ ] **Step 2: Extend the red-flags list** with the self-check phrasings that preceded each
      violation.
- [ ] **Step 3: Close each loophole explicitly** rather than restating the rule. Where a rule was
      evaded by narrowing scope ("this is a service, not a product"), name the evasion and forbid it.
- [ ] **Step 4: Re-run the failing scenarios only.** Repeat 1–3 until a full round finds nothing new,
      **to a maximum of three rounds.** If new rationalisations are still emerging on the third, stop
      patching wording and say so: three rounds of fresh evasions means the problem is structural —
      most likely a scope too broad to defend with rules — and the answer is a narrower skill, not
      more prose. If a fix touches the output contract's wording, re-run Task 8's micro-test for that
      wording before re-running scenarios.
- [ ] **Step 5: Re-run `node scripts/validate.mjs`** — the additions must not push the body past 500
      lines. If they do, move the table into a reference and link it from `SKILL.md`.
- [ ] **Step 6: Commit.**

**Acceptance:** a full round of re-runs produces no new rationalisation; body still under 500 lines;
validator green.

---

## Task 11: Live smoke test

**Files:**
- Create: `docs/testing/true-quality/smoke.md`

Proof that the skill works on the live internet, not only on pinned scenarios.

- [ ] **Step 1: Run three real questions end to end** with real search and a real browser, on
      genuinely different categories — one durable good with a rating pool, one open-source
      dependency, one local service.
- [ ] **Step 2: Check every URL the output cites** actually resolves and says what the answer claims.
      A fabricated or misattributed citation is a hard failure; fix the skill, not the output.
- [ ] **Step 3: Check the arithmetic** — recompute one bound with
      `python3 skills/research/true-quality/scripts/rating-bounds.py --hist …` against the histogram
      the agent read off the page.
- [ ] **Step 4: Check the language.** No output may assert that an identifiable business or person
      committed fraud absent a platform's own first-party artifact or a regulator's published action
      (D6). Flag any accusatory phrasing as a Task 10 fix.
- [ ] **Step 5: Record all three transcripts and outcomes, anonymised.** Replace the local service's
      name and address with a placeholder before committing — a git-tracked file naming a real small
      business alongside a negative verdict is a liability with no upside.
- [ ] **Step 6: Commit.**

**Acceptance:** three live runs; zero unresolvable or misattributed citations; the recomputed bound
matches; every run's `Against it` slot filled from real evidence; no accusatory phrasing; the local
service anonymised in the committed artifact.

---

## Task 12: Deep-mode subagent definition (optional, last)

**Files:**
- Create: `agents/quality-scout.md`

Ship only if Task 9's S8 run recorded that the fan-out found something the Standard path missed. The
repo's `agents/` files are the one place the portability contract does not reach, so this is additive
and never load-bearing.

**If S8 showed no benefit, do not skip this task silently — remove Deep mode instead.** A depth tier
that demonstrably adds nothing is a section every future reader has to evaluate and discard. Drop it
from D7, from `SKILL.md`'s depth table and from the selection rule, leaving two tiers, and record the
measurement in `green-run.md` so the deletion is traceable to evidence rather than to taste.

- [ ] **Step 1: Frontmatter** with `name` and `description`, matching the two existing agent files'
      shape, autoloading `true-quality` rather than restating it. Note that an unknown name in an
      autoload list is dropped silently, so the name must match the installed skill exactly.
- [ ] **Step 2: One axis per invocation**, read-only, returning findings with tier and funder tags.
- [ ] **Step 3: Prove the fallback.** Re-run S8 with the agent definition absent and confirm the
      serial fallback produces a usable answer. This is the acceptance test, not an assertion.
- [ ] **Step 4: Commit.**

**Acceptance:** S8 scored against Task 9's rubric both with the agent file present and with it
absent, and passing every applicable line in both cases; the difference in findings recorded in
`green-run.md`.

---

## Task 13: Ship

- [ ] **Step 1: Update `README.md`** — the catalog table's `research` row becomes
      `cite-or-refuse, fact-check-document, harden-case, true-quality`. Leave the rest of README
      alone: its Install section is stale (it predates the current single-store setup and the CLI
      regression below), and fixing it is a separate change.
- [ ] **Step 2: Full validation.**

```bash
node scripts/validate.mjs
python3 skills/research/true-quality/scripts/rating-bounds.py --selftest
```

- [ ] **Step 3: Install from the working tree into the store.** `--agent universal` is **required**:
      with no `--agent`, the CLI enumerates every universal agent, hits one that declares no global
      skills directory, and dies with `PromptScript does not support global skill installation`.
      That failure mode is documented in this machine's `AGENTS.md`, not independently reproduced
      during hardening — and it does not matter which way it resolves, because naming the target
      skips the enumeration entirely and is documented to produce identical content. The local
      `skills` wrapper injects the right flags and refuses a caller-supplied
      `--agent`, so either form works:

```bash
npx -y skills add . --skill true-quality --agent universal -g --yes
# or, equivalently, via the local wrapper:
skills add . --skill true-quality
```

- [ ] **Step 4: Confirm the copy landed** — the install copies, so edits in this working tree are not
      live: `ls ~/.agents/skills/true-quality/references/` should list all five files. Check
      `~/.agents/.skill-lock.json` records the entry.
- [ ] **Step 4a: Check for a name collision before installing, not after.** Skill names are global
      and installs flatten to `~/.agents/skills/<name>`, so a collision silently overwrites whatever
      was there. `ls ~/.agents/skills/true-quality` must not exist before step 3 runs; the store
      currently holds ~30 skills including third-party ones, so this is cheap insurance, not paranoia.
- [ ] **Step 4b: Enforce the two unenforced invariants** — the ones the validator cannot see. Grep
      the installed skill tree for digit-and-percent patterns and for any numeric threshold, and
      confirm each hit has a `source-ledger.md` row and, for a platform figure, a year. A hit with no
      ledger row is a defect in the file, not in the check.
- [ ] **Step 5: Load the skill in a fresh session and ask one question** to confirm the installed
      copy — not the working tree — behaves.
- [ ] **Step 6: Rename the branch off the `unbaised-search` typo, then push.** CI runs the validator,
      the discovery smoke test and a four-agent portability install on push; all three must be green.
- [ ] **Step 7: If CI fails, revert the push and fix the skill.** The discovery smoke test and the
      four-agent portability install exist to catch exactly what a local validator run cannot. A red
      run means the skill is not portable or not discoverable; neither check gets relaxed, skipped or
      excluded to make the push green.

**Acceptance:** validator green; `--selftest` green; store copy complete and lock updated; installed
copy answers correctly; README catalog accurate; CI green on a correctly spelled branch.

---

## Self-Review

**Spec coverage.** Every design section maps to a task: D1/D2 → Tasks 1, 7, 8, 10; D3 → Task 7
step 3; D4 → Tasks 2, 7; D5 → Task 3; D6 → Task 7 step 4, Task 8, Task 11 step 4; D7 → Task 7 step 5
and Task 9 steps 4–5; D8 → Task 7 steps 6–7 and 9; D9 → Task 7 step 11. Global Constraints 1–3 →
Task 7 steps 1–2 and 14; 10 → Tasks 2–6 verification steps; 11 → every commit step and Task 13
step 6.

**Named-value consistency.** `true-quality` everywhere; the script is `scripts/rating-bounds.py` with
its self-test behind `--selftest` and no separate test file; the five reference filenames are fixed in
the File Structure table and used unchanged in Tasks 2–7; the eight category labels are introduced in
Task 5 and consumed in Task 7 step 8; the tier labels are introduced in Task 2 and consumed in Tasks
4, 5, 7 and the output contract; test artifacts live under `docs/testing/true-quality/` in every task
that writes one.

**Known gaps, stated rather than hidden.**

1. The research layer's first-pass error rate was 5 of 15 on re-verification. Global Constraint 10
   and the per-task verification steps are the answer; the ledger's read-at-source column is what
   makes a residual gap visible instead of invisible.
2. Three research files disagree in emphasis on 5.0 ratings. D5 resolves it and marks the
   missing-tail heuristic as an inference with no numeric threshold. If a future editor finds a
   sourced threshold, it can be added; inventing one is forbidden.
3. `He/Hollenbeck/Proserpio` is confirmed only from its abstract (publisher 403). `arXiv:2506.13313`
   is a preprint. Both are marked as such in the ledger and in the reference bodies.
4. ReviewMeta's status has no primary source. It ships as `?`.
5. No neutral source exists for platform average-rating drift over time; the vendor report is either
   labelled or dropped.
6. No live retailer RMA dataset was found for 2026. The routing table says so instead of sending an
   agent looking.
7. Adding `docs/` to a repo that has none is a new convention. It stays outside `skills/`, so the
   installer never sees it and the validator never walks it — verified by running the validator with
   `docs/` present.
8. The build costs roughly 40 subagent runs (8 baseline, 15 micro-test, 8 green, 3 smoke, plus
   re-runs) and 40–60 verification lookups. That is the price of the verification regime chosen in
   hardening; a cheaper build means accepting the 33% error rate.
9. Two assumptions the testing regime rests on, both accepted rather than solved: that a
   fresh-context subagent run is a usable proxy for a real user session, and that failure modes
   observed across eight scenarios generalise to categories none of them covered. Neither is
   provable here; both are why Task 11's live runs exist as a separate gate rather than a formality.
