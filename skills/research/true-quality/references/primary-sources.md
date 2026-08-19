# Primary-source routing by category

## Contents

1. [Routing table](#routing-table)
2. [Sources](#sources)
3. [Interpretation rules](#interpretation-rules)
4. [Five worked chains](#five-worked-chains)

## Routing table

Identify the category first, then pull the matching primary source **before** reading any rating.

| Category | First question | Primary sources, in order |
| --- | --- | --- |
| Durable hardware (drives, GPUs, appliances) | What's the category baseline failure rate? | Backblaze (drives), Puget Systems (PC components), Stiftung Warentest / Which? (appliances) |
| Vehicle | Any open recall? What's the age-adjusted defect rate? | NHTSA (US, by VIN), TÜV-Report / ADAC (Germany), Which? (UK) — discount JD Power IQS/VDS for its documented flaws |
| Appliance / EU-regulated product | Do the marketing numbers match the legally-binding label? | EPREL (via QR code), France's réparabilité/durabilité index, EU Ecodesign spare-parts page |
| Software / SaaS | When does support end, and what's the incident history? | endoflife.date, the vendor's own status page, SOC 2/ISO 27001 verification path |
| Open-source dependency | Is it actually maintained, not just starred? | OpenSSF Scorecard, deps.dev, the abandonment multi-signal checklist |
| Lodging / two-sided marketplace | What's the platform's own base rate? | `rating-forensics.md`'s base-rate table, then the specific listing's own review text |
| Trade or professional service | Is the licence active today, and any distress signal? | State/national licence board, company registry, court records |
| Consumable / locked-ecosystem product | What's the total cost of ownership? | Manufacturer's current consumable pricing (arithmetic, self-verifying) |

## Sources

Each entry: what it proves — access marker (`free` / `registration` / `paywalled`) — scope limit.

**Hardware & appliances**

1. **Backblaze Drive Stats** — annualised failure rate (AFR) by drive model, from tens of thousands
   of drives in continuous use — free, no login — backblaze.com/cloud-storage/resources/hard-drive-test-data.
   Datacenter duty cycle; does not transfer directly to a single consumer drive.
2. **Puget Systems Hardware Reliability Report** — annual failure/RMA rates by GPU/CPU/RAM/SSD brand
   from a boutique builder's own burn-in and field data — free — pugetsystems.com/labs. Explicitly
   non-representative per Puget's own disclaimer; compare relative rankings within a year, not
   absolute rates across years (methodology has been revised).
3. **Stiftung Warentest reader surveys** — median time-to-first-failure and repair-success rate by
   appliance category (~14,450 respondents on washer/dryer/dishwasher) — paywalled for full
   articles, headline results free — test.de. Self-selected panel, German market, 2021 wave — check
   for a newer one before citing.
4. **Which? UK car reliability survey** — reliability scored by fault *severity*, not just count,
   broken out by age band — paywalled for full results — which.co.uk. UK-only; exact weighting
   formula not published.
5. **TÜV-Report (Germany)** — defect rate from ~9.5M mandatory roadworthiness inspections, by model
   and age — free summary, full report paywalled — tuev-verband.de. Measured physical inspection
   data, not self-report; German market and inspectable-defect categories only.
6. **ADAC Pannenstatistik** — roadside-breakdown rate per 1,000 registered vehicles, by model,
   restricted to ≥5,000-unit models — free — adac.de. Battery-related callouts (44.1%) dominate and
   are climate/usage-sensitive; check whether a gap is battery-driven before concluding "less
   reliable."
7. **JD Power IQS/VDS** — the most widely cited US new-car quality survey — free headline results,
   full dataset paywalled — jdpower.com. **Discount, don't just report**: no severity weighting
   (a rattle counts the same as engine failure), brand-level aggregation can hide a bad model,
   collects **no post-warranty data**.
8. **NHTSA** — VIN-searchable recalls, complaints, Technical Service Bulletins, investigations (US)
   — free, no login — nhtsa.gov/recalls, nhtsa.gov/search-safety-issues. Normalise complaint counts
   by units sold before comparing models.
9. **RappelConso / EU Safety Gate / CPSC SaferProducts.gov / EU RASFF** — legally mandated recall and
   danger registries (France / EU / US / EU food) — free, RappelConso has a key-free GTIN API — a
   listing is confirmed regulatory action; absence only means "no action triggered yet," never
   "safe," especially for low-volume products.
10. **iFixit teardowns and Repairability Score** — physical disassembly evidence and a versioned
    0–10 rubric score — free — ifixit.com. Only scored where iFixit chose to tear one down; never
    compare scores across different rubric versions.
11. **Warranty length** (own signal, no external database) — a manufacturer's costly, hard-to-fake
    reliability bet, per signalling-theory marketing research — only informative from an already
    credible brand; a long warranty from an unknown brand is cheap to promise.
12. **Class-action dockets** (CourtListener/RECAP, Justia, PACER) — a pattern of certified or
    settled-with-claims-process suits alleging the *same* defect is a hard-to-fake systemic signal —
    free via CourtListener/Justia, PACER paywalled at $0.10/page (fee-waived first ~150 pages/qtr).
    A single filed complaint alone is a bare allegation, not evidence.

**EU/France regulatory databases**

13. **EPREL** — the EU's mandatory energy-label registry; manufacturer-submitted but legally binding
    — free, QR code on the physical label — energy-efficient-products.ec.europa.eu. Self-reported
    under legal liability, not independently pre-verified before publication.
14. **EU Energy Label (2021 rescaling)** — the A–G scale replaced A+++–D in March 2021 because >90%
    of products had clustered at the top; an old "A+++" is **not comparable** to a current label —
    always check the EPREL entry's date.
15. **EU tyre label** — wet grip, rolling resistance, noise, via EPREL — free. Says nothing about
    tread-wear longevity — check independent tyre-wear tests separately.
16. **France's indice de réparabilité → indice de durabilité** — government-published, manufacturer
    self-scored repairability/durability index, transitioning category by category (TVs from
    2025-01-08, washing machines from 2025-04-08) — free — ecologie.gouv.fr. Self-declared, audited
    after the fact by DGCCRF; check the rubric version, since iFixit's own comparison shows the two
    scores can disagree on the same product.
17. **EU Ecodesign spare-parts rules** (since 2021-03-01, light sources 2021-09-01) — mandatory
    spare-parts availability window for refrigerators/washers/dishwashers/displays, 15-working-day
    delivery — free — commission.europa.eu. Category-specific; smartphones/tablets fall under a
    separate, later (2025) Ecodesign regulation.
18. **ENERGY STAR** — US EPA/DOE certification with third-party lab testing and post-market
    re-verification of ≥10% of certified basic models annually — free — energystar.gov. 10% sampling
    means most individual models are never independently re-checked in a given cycle.
19. **FCC ID / Equipment Authorization Search** — reveals the actual chipset/module inside an
    RF-emitting device via its certification filing, independent of marketing claims — free —
    fcc.gov/oet/ea/fccid (mirror: fccid.io). Supplier's-Declaration-of-Conformity-path devices are
    legitimately absent; internal photos can be under a confidentiality hold for up to ~180 days.
20. **UL Product iQ** — verifies a claimed UL/ETL listing by file number — free with registration —
    productiq.ul.com. **CE marking has no equivalent public registry** — it is self-declared; look
    for the manufacturer's own EU Declaration of Conformity instead.
21. **EU Ecolabel Product Catalogue (ECAT)** — verifies a claimed EU Ecolabel by licence number —
    free — environmental-data.ec.europa.eu/ecolabel. May be non-exhaustive per the Commission's own
    documentation — absence is weaker evidence than presence.

**Software, services, and security**

22. **EU Cyber Resilience Act** (Regulation (EU) 2024/2847) — a **minimum 5-year** security-support
    floor for connected products. **Dates, precisely, since this is easy to get wrong**: Chapter IV
    (notified bodies) applied from 2026-06-11; Article 14 vulnerability/incident reporting applies
    from **2026-09-11**; the support-period requirement itself (Article 13/Annex I) is binding only
    at **full application, 2027-12-11**. Do not treat the September 2026 date as the support-period
    deadline. Free — digital-strategy.ec.europa.eu/en/policies/cra-manufacturers.
23. **endoflife.date** — community-maintained EOL/support-window tracker for 460+ software products,
    with a free REST API — free — endoflife.date. Mirrors vendor pages; sanity-check the vendor's own
    lifecycle page for a high-stakes decision.
24. **NVD/CVE and CVSS** — vulnerability history and severity scoring — free — nvd.nist.gov. **A high
    raw CVE count is not itself evidence of poor security** — well-audited, actively maintained
    projects generate more disclosed CVEs precisely because more people are looking. Read
    time-to-patch and current-vs-legacy-branch concentration, not the count.
25. **OpenSSF Scorecard** — ~18 automated security-practice checks (branch protection, signed
    commits, security policy, fuzzing), 0–10 each — free, public dataset — scorecard.dev. Scores
    process hygiene, not "this code has no bugs."
26. **deps.dev** — transitive dependency graph and advisory data across Go/Maven/PyPI/npm/Cargo —
    free — deps.dev. Limited to those five ecosystems.
27. **Public status pages + postmortems** — dated incident history, cross-checkable against a
    third-party tracker (e.g. StatusGator) — free. Self-reported and self-selected for what counts
    as an "incident" — not apples-to-apples across vendors without checking definitions.
28. **SOC 2 / ISO 27001 verification** — there is **no public SOC 2 registry**; verify instead via
    CPAverify.org (the named CPA's licence) and the audit firm's AICPA Peer Review status, checking
    opinion type (unqualified vs. qualified) and observation-period length. ISO 27001 *does* have
    accredited-body registries — check the specific certificate number against the named certifying
    body, not a generic search. Free.
29. **GitHub stars / npm downloads — anti-manipulation cross-checks**, not standalone signals.
    StarScout (arXiv:2412.13459) found ~6M suspected fake GitHub stars; npm's download counter has no
    bot filtering by design and can be trivially inflated. Check fork-to-star ratio (10–25% healthy;
    <5% on a high-star repo is an anomaly worth investigating) and dependent-package counts instead
    of the headline number.
30. **Abandoned-project multi-signal check** — no single metric (including "no commits in 12+
    months") reliably distinguishes abandonment from stability. Check commit cadence against the
    project's *own* historical baseline, issue-response latency, release-cadence trend, whether the
    maintainer is active elsewhere on GitHub, and dependency freshness — together, never from
    commit-date alone.

**Longevity, resale, and services**

31. **Resale/depreciation on completed sales** (e.g. eBay "Sold Listings," condition-filtered,
    8–15 comparables) — a market-aggregated durability proxy — free to browse. Confounded by brand
    desirability and fashion — use as corroboration, never standalone.
32. **Total cost of ownership** for locked-consumable products (printer ink is the canonical case:
    a documented ~2x total-cost reversal between a cheap-hardware/expensive-ink model and an
    expensive-hardware/cheap-ink model over 5 years) — free, self-verifying arithmetic on published
    consumable prices. Compute the break-even usage point, don't assert a single winner.
33. **US state contractor-licence boards** (worked: California CSLB, productiq.ca.gov equivalent per
    state) — free, no login. Confirms status, trade classification, bond/workers'-comp *currently*,
    not just "license exists." Every state has its own separate board and URL format.
34. **Companies House (UK)** + **The Gazette** (winding-up notices, ~7-day lag) — free UK government
    services. A clean record is weaker evidence than a flagged one, given the documented filing lag.
35. **Pappers.fr / BODACC / INPI (France)** — free browsing (Pappers' bulk API is paywalled from
    €20/month); BODACC/INPI themselves are free. Filter to "Procédures collectives," last 3 years.
36. **CourtListener/RECAP, Justia, PACER (US)** — free via the first two; official PACER paywalled at
    $0.10/page, fee-waived for the first ~150 pages/quarter. A pattern of similar successful claims
    is signal; a single suit against any company proves almost nothing.

## Interpretation rules

- Absence of a recall is informative only relative to market size — a product with 3 units sold will
  never generate a recall regardless of quality.
- A survey-aggregator score (JD Power, Which?, ADAC) is not a lab measurement — check `N` and the
  weighting method before citing a number as precise.
- A certification logo on a box is not the certification — verify the file/licence/certificate
  number in the issuing body's own registry. CE marking has no such registry at all; UL, ISO 27001
  and EU Ecolabel do.
- Litigation and insolvency-registry checks are asymmetric evidence: a red flag is strong; a clean
  record is weak, because every registry here has a documented reporting lag.
- Warranty length only signals quality from an already-credible brand — check company registration
  and financial health (below) alongside it, not instead of it.

## Five worked chains

**(a) A laptop.** EPREL for the EU energy label if applicable → iFixit teardown/Repairability Score
(rubric version noted) → the model's FCC ID to confirm the actual Wi-Fi/Bluetooth module matches the
spec sheet → warranty length against category norms, only meaningful if the brand is already
credible → eBay sold-listing resale value at 2–3 years as a corroborating longevity signal.

**(b) A dishwasher.** EPREL/QR code, confirming a post-2021-rescaling A–G label, not a legacy "A+++"
→ France's réparabilité/durabilité index if sold there, checking the transition date → the EU
Ecodesign spare-parts page (its absence is itself a compliance gap) → Stiftung Warentest's category
base-rate time-to-first-failure to sanity-check a specific "10-year" claim.

**(c) A SaaS tool.** The vendor's public status page, 12 months of incidents plus postmortems →
cross-check against an independent outage tracker → if SOC 2/ISO 27001 is claimed, verify via
CPAverify/AICPA Peer Review or the specific certificate registry, never take the badge on faith →
check the published subprocessor list for undisclosed fourth-party dependencies.

**(d) An npm package.** Skip star/download count entirely as a starting point → OpenSSF Scorecard +
deps.dev for security-practice and dependency-health signals → the abandonment multi-signal
checklist → fork-to-star ratio as an anti-manipulation cross-check → NVD/CVE history read for patch
latency, not raw count.

**(e) A roofing contractor.** State licence board (or national equivalent) for active status, correct
trade classification, and current bond/insurance → company registry (Companies House / Pappers-
BODACC-INPI / equivalent) for filing recency and insolvency flags → court-record search for a
*pattern* of similar claims, not a single suit → cross-reference all three, since each individually
carries a reporting lag.
