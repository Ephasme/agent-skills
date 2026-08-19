# Evidence tiers, ownership and conflicts of interest

## Contents

1. [Two label sets](#two-label-sets)
2. [Ownership-checking procedure](#ownership-checking-procedure)
3. [Recommendation-source tiers](#recommendation-source-tiers)
4. [Dated ownership map](#dated-ownership-map)
5. [Conflict-of-interest artifact table](#conflict-of-interest-artifact-table)
6. [Vendor-claim gaming](#vendor-claim-gaming)
7. [Two hard cases for calibration](#two-hard-cases-for-calibration)

## Two label sets

The 0–4 tiers below classify outlets that *recommend* — labs, reviewers, listicles, lead-gen sites.
A regulator database, an operator failure dataset, a peer-reviewed paper or a vendor's own
contractual terms are not "tier 2"; they carry a **type** instead:

`regulator` · `operator-dataset` · `peer-reviewed` · `preprint` · `platform-first-party` ·
`vendor-terms` · `vendor-marketing`

The output contract's Evidence-table `tier or type` column takes a value from whichever set
applies. `source-ledger.md`'s `type` column uses this same vocabulary — nowhere else restates it.

## Ownership-checking procedure

Do this **before** trusting a named tier below, because ownership changes — CNET changed hands
twice in four years, and an earlier draft of this skill's own design got its current owner wrong.

1. Read the site's Terms of Service or Privacy Policy for the **contracting legal entity name**,
   not the masthead or About page's marketing copy.
2. Search `"[site]" "owned by"` and `"[site]" "parent company"`.
3. Check the affiliate `tag=` (or equivalent) value on an outbound link — a value matching another
   brand name is a fast tell.
4. For a suspected tone shift around an acquisition or lawsuit-settlement date, compare Wayback
   Machine snapshots (`web.archive.org/web/*/[url]`) from before and after.
5. **Re-check before quoting a tier.** A tier assignment below is dated at the time it was verified,
   not evergreen.

## Recommendation-source tiers

**Tier 0 — no advertising, buys every unit at retail, refuses submitted samples, published
protocol, member/non-profit funded.**

- **Consumer Reports** (US) — 501(c)(3), takes no advertising, buys essentially all tested products
  at retail; its own materials say it "expect[s] to spend more than $30 million" annually on testing
  (a forward projection, not audited spend), with roughly 70% of revenue from ~4M paying members.
  Source: Consumer Reports, "Policies & Financials", consumerreports.org/about-us/policies-and-financials/.
- **Which?** (UK) — no advertising, no government funding, revenue from a commercial trading arm.
- **Stiftung Warentest** (Germany) — ad-free, financially independent of government.
- **UFC-Que Choisir** (France) — member-funded, refuses manufacturer-submitted samples, AFNOR
  NFX 50-005 protocol.

**Tier 1 — for-profit or creator-funded, but buys its own units or refuses sponsorship outright;
publishes full methodology; on-record history of not softening under manufacturer pressure.**

- **RTINGS.com** — states repeatedly, in its own words, "We buy every product ourselves, like
  normal consumers (no paid or sponsored reviews)." Its own live counters show a **cumulative 4,837
  products bought and tested site-wide**, and "we buy and test more than 40 TVs each year." (The
  "$714,000 / 618 products per year" figure that circulates in secondary blog aggregators does
  **not** appear anywhere in RTINGS' own published material and should not be repeated — see
  `source-ledger.md`.) Source: rtings.com/company/revamping-our-membership-program;
  rtings.com/company/about-us; rtings.com/tv/learn/how-we-test.
- **Project Farm** (YouTube) — its own Patreon "About" page states, verbatim: "Patreon donations
  allow me to decline all sponsorship opportunities and remain unbiased, since I have nothing to
  sell nor do I have a corporate sponsor to please... EVERY penny donated is spent on buying
  products that viewers want tested, test equipment or other expenses directly related to making
  videos." Source: patreon.com/projectfarm/about.
- **Gamers Nexus** (YouTube/web) — subscriber-funded, publishes sourcing/config methodology,
  publicly combative with manufacturers over review-unit access.
- *(Hardware Unboxed sits at the 1/2 boundary: mixed ad/sponsorship/Patreon funding, but with a
  documented Nvidia press-access ban over editorial independence.)*

**Tier 2 — large outlets with real testing infrastructure and disclosed affiliate/ad revenue,
structurally separated in whole or part from editorial decisions, that accept manufacturer loaner
units under embargo.**

- **Wirecutter (NYT)** — visible affiliate disclosure, claimed editorial/business firewall, no
  commission on returns. (The firewall claim itself is only moderately sourced — see
  `source-ledger.md`'s open questions.)
- **Notebookcheck** — instrumented, quantitative scoring; mixed ad/affiliate/advertorial revenue.
- **DXOMARK** — publishes its scoring formulas for transparency, but its parent (DxO Labs) sells
  paid consulting/engineering services to manufacturers through its DxO Analyzer / Image Quality
  Solutions business — the same manufacturers whose cameras DXOMARK then scores and ranks as
  independent. DXOMARK does not deny running this paid-consulting business; it disputes the bias
  inference, with a VP stating tests are "always the same for everyone." Best-sourced account:
  Android Authority, "DxOMark scores shouldn't be your definitive camera rating system"
  (Kris Carlon, 2019-10-09), corroborated by PetaPixel's 2017-10-13 writeup of an MKBHD
  investigation. Place any DXOMARK-sourced claim at the bottom of this tier, or in Tier 3 depending
  on what specifically is being checked.

**Tier 3 — affiliate-commission "best of" content at scale from multi-brand conglomerates; little
disclosed hands-on testing; at least one documented content-quality or ownership incident somewhere
in the portfolio.**

- **CNET** — owned by **Ziff Davis** as of Q3 2024 (previously Red Ventures, 2020–2024; see the
  ownership map below). In January 2023, Futurism reported CNET had quietly published
  AI-generated financial-explainer articles without disclosure; CNET's editor-in-chief acknowledged
  errors in 41 of 77 AI-generated stories on internal review, including a materially wrong
  compound-interest calculation. CNET paused AI generation and published a revised AI-use policy in
  June 2023 — a point-in-time incident; check the outlet's current AI-disclosure policy before
  assuming it still applies. Sources: CNN Business, 2023-01-25, cnn.com/2023/01/25/tech/cnet-ai-tool-news-stories;
  Gizmodo, 2023-01-17, gizmodo.com/cnet-ai-chatgpt-news-robot-1849996151.
- **TechRadar / Tom's Guide / Tom's Hardware** — Future plc, confirmed directly on
  futureplc.com/brands/; 240+ brands total as of 2022 reporting.
- **ScreenRant / CBR / Collider / XDA Developers** — Valnet, confirmed directly on
  valnetinc.com's brand grid; XDA specifically "Acquired and owned by Valnet Inc. since February
  2022" (valnetinc.com/xda).

**Tier 4 — regulator action on record, or owned by a vendor in the reviewed vertical, or lead
capture is the site's core function. Treat any specific ranking here as presumptively compromised
until proven otherwise.**

- **vpnMentor / Wizcase** — owned by Kape Technologies since its $149.1 million acquisition of
  Webselenese, announced 2021-03-08 (BusinessWire press release, ID 20210308005178). Kape also owns
  the VPN brands CyberGhost (since 2017-03), Private Internet Access (since 2019-11) and ExpressVPN
  (since 2021-12) — the same category of product these two "independent" review sites rank.
- **LendEDU** — FTC alleged it told consumers its financial-product rankings were "objective,"
  "accurate," and "unbiased" while adjusting rank and rate-table position by how much a company
  paid, added a real compensation disclosure only after learning of the FTC investigation, and that
  90% of its 126 Trustpilot reviews were written by employees or their friends/family, all 5-star.
  Settled May 2020 for **$350,000**, with an order permanently barring misrepresentation of ranking
  objectivity. Sources: FTC press releases, 2020-02 and 2020-05,
  ftc.gov/news-events/news/press-releases/2020/02/... and .../2020/05/....
- **MediaAlpha / QuoteLab** — operated sites that appeared to offer health-insurance quotes but sold
  none; harvested sensitive personal data and auctioned it to telemarketers, falsely implied
  government affiliation, used paid-actor testimonials for non-existent plans. Settled 2025-08-07
  for $45 million.

## Dated ownership map

Every row below carries the **closing** date of the transaction, not the signing/announcement date
— cite closing dates by convention, since a deal can be announced and never close, or close months
after signing. Re-check the parent before quoting a tier (procedure above); this map is a dated
illustration, not a standing fact.

| Property | Owner | Since | Source |
| --- | --- | --- | --- |
| Bankrate, The Points Guy | Red Ventures | closed 2017-11-08 | Bankrate's own SEC 8-K exhibit |
| CNET | Ziff Davis | completed Q3 2024 (previously Red Ventures 2020-10-30–2024, ~$500M) | Ziff Davis press release via BusinessWire, ID 20241001349422 |
| TechRadar, Tom's Guide, Tom's Hardware | Future plc | current | futureplc.com/brands/ |
| ScreenRant, CBR, Collider, XDA Developers | Valnet | XDA since 2022-02; others current | valnetinc.com brand grid |
| vpnMentor, Wizcase | Kape Technologies | since 2021-03-08 ($149.1M) | BusinessWire press release, ID 20210308005178 |
| CyberGhost / PIA / ExpressVPN | Kape Technologies | 2017-03 / 2019-11 / 2021-12 | Kape's own investor materials |
| Bluehost, HostGator | Newfold Digital (formerly EIG) | current | Newfold's own newsroom |

**EIG/Newfold, stated as a limit, not a finding:** Newfold's ownership of the smaller brands
(iPage, FatCow, JustHost, HostMonster, A Small Orange, HostNine) rests only on secondary sourcing —
newfold.com blocks automated verification. More importantly, **no FTC enforcement action, complaint
or notice against EIG or any of its affiliate programs exists in the FTC's own legal library.** A
widely repeated claim that EIG affiliates received "FTC-compliance emails" in 2011–2012 traces to a
single low-authority blog describing EIG's *own internal* notices to its affiliates — not an
FTC-issued action. Do not cite this as an enforcement case. The pattern of EIG-owned hosts appearing
together on nominally independent "best hosting" sites remains real and worth checking (ownership
procedure above), but it is unadjudicated.

## Conflict-of-interest artifact table

| # | Observable artifact | What it means | How to check |
| --- | --- | --- | --- |
| 1 | `tag=` (or equivalent) affiliate ID in an outbound retailer URL | Site earns a commission if you buy via this link | View or hover the link; check for `tag=`, `ref=`, `affid=`, `aff_id=` |
| 2 | Outbound link redirects through `redirect.viglink.com`, `go.skimresources.com`, `linksynergy.com` or similar | Every outbound commercial link is auto-monetized, even ones the writer didn't personally choose | Hover/copy the resolved destination before it lands on the merchant |
| 3 | `rel="sponsored"` HTML attribute present or absent | Signals Google-facing SEO compliance only — says nothing about reader-facing disclosure | View page source |
| 4 | "We may earn a commission" text placed at/near the recommendation vs. buried in a footer | Near-placement is closer to genuine FTC-disclosure intent; buried is weaker | Check text position relative to the buy link |
| 5 | Parent-company name absent from About/footer while independence is explicitly claimed | Possible concealed ownership conflict (the vpnMentor/Wizcase pattern) | Search the page for the suspected parent; cross-check the ToS entity name |
| 6 | ToS/Privacy-Policy legal entity name differs from the public brand and matches a vendor in the reviewed category | Hidden same-owner conflict | Read the ToS/Privacy footer for the contracting entity |
| 7 | "Award," "certified," "top X%" badge with no published selection criteria or visible non-winners | Pay-to-play award mill | Search for the awarding body's methodology page; absence is the red flag |
| 8 | Ranking order for the same product changes over time in ways correlated with a partnership/payment | Paid ranking manipulation | Compare Wayback Machine snapshots across dates |
| 9 | Near-identical prose or "top 3 picks" repeated verbatim across nominally independent domains | Shared content-mill/parent origin, or syndicated "parasite SEO" content | Search a distinctive sentence fragment in quotes across sites |
| 10 | A niche-vertical "independent" review site consistently ranks one brand's products #1 across many categories | Self-referential same-owner conflict | Check whether the top-ranked brand also owns the review site |
| 11 | Star-rating histogram missing the 2–4 star middle, with the large majority at 5 stars | Anomalous relative to the expected J-shaped/bimodal distribution of genuine reviews (see `rating-forensics.md` — no numeric threshold is sourced; treat as inference, not a rule) | View the platform's rating-distribution histogram where available |
| 12 | Sudden spike in review volume in a short window, especially many 5-star reviews from low-activity/new accounts | Coordinated fake-review injection | Check review dates/timestamps for clustering; check reviewer profile age where visible |
| 13 | Sub-brand hosted under a famous news domain with a separately-branded "About" page and different staff | Licensed/"parasite SEO" commerce content borrowing the parent domain's search trust | Check whether the sub-brand's masthead overlaps with the parent's actual newsroom |
| 14 | Marketing copy ("up to X hours," "up to X miles") with no independent real-world measurement cited | Best-case ceiling claim, not a typical result | Search for independent real-world testing of the same spec |
| 15 | Comparison/"quote" site requiring phone number or email before showing any price or ranking | Lead-generation site, not a genuine comparison tool (the MediaAlpha/QuoteLab pattern) | Attempt to view results without submitting contact info |

## Vendor-claim gaming

- **Benchmark detection and boosting — Huawei, 2018 (confirmed).** UL (Futuremark) tested Huawei
  devices in its own lab and, after confirming rule violations, delisted the **Huawei P20 Pro, Nova
  3 and Honor Play** from its 3DMark approved list based on its own testing, plus the **Huawei P20**
  based on AnandTech's reporting. The public 3DMark app scored up to **47% higher** than an internal,
  non-public build with identical code, because the devices recognized the 3DMark app by name and
  engaged a hidden "Performance Mode." Source: UL's own blog post, 2018-09-06,
  benchmarks.ul.com/news/ul-delists-huawei-phones-with-suspect-benchmark-scores.
- **Samsung's Game Optimizing Service, 2022 (corrected attribution).** Samsung's own official
  statement (2022-03-03) acknowledges GOS "optimizes CPU and GPU performance to prevent excessive
  heat" and promised a fix; separately, **Geekbench** — not UL/3DMark — removed the Galaxy S10/S20/
  S21/S22 series from its approved-devices list via its own announcement on 2022-03-04. Two
  different benchmark organizations, five years and one unrelated Samsung incident apart (Futuremark
  delisted an earlier Samsung Note in 2013, over a different issue) — do not conflate the two dates
  or the two organizations. Source: Samsung's own statement,
  r2.community.samsung.com/t5/Tech-Talk/Official-Statement-on-Game-Optimization-Services-GOS-from/td-p/10964704.
- **"Detect the test" as a general mechanism — Volkswagen, 2015.** VW's diesel engines detected
  emissions-testing conditions and activated a compliant mode only during the test, reverting to a
  higher-emissions mode otherwise. Source: US EPA Notice of Violation, 2015-09-18. Cited here as the
  general pattern any "detect the test" case follows, not because cars are this skill's subject.
- **"Up to" claims as ceilings, not typical results.** Sustained-load performance and burst
  performance are different measurements; a marketing figure ("up to 18 hours," "up to 300 miles")
  is a best-case number under specific, usually undisclosed, conditions. Convert every such claim
  into a testable question: what conditions, measured by whom, and does an independent source (Tier
  0–1) report a real-world figure for the same spec?
- **Silent SKU revisions and regional variants.** The same marketing model number can hide a
  different panel, chipset bin, or silicon revision between regions or between production runs.
  Check the specific SKU/serial or region-locked spec sheet, not just the model name.

## Two hard cases for calibration

**Casper v. Sleepopolis (2016).** Casper sued Sleepopolis and two other mattress-review sites in
April 2016 (CourtListener docket 1:16-cv-03223) for undisclosed affiliate bias. The Sleepopolis
founder had received $40,000 in SEO consulting fees from competitor Leesa over roughly 20 months
while reviewing Leesa favorably. **The "~33,000 sales / ~$1.6M in commissions" figure is Fast
Company's own traffic-based estimate, explicitly called "inflated" by Leesa's CEO** — treat it as a
contested estimate, never as a court-established fact. Mattress Nerd and Sleep Sherpa settled and
their negative Casper reviews disappeared; Casper later financed a media company's acquisition of
Sleepopolis, after which Sleepopolis published a revised, positive Casper review. Underlying
settlement terms were largely confidential — causal claims about what the settlement required are
informed reader speculation, not confirmed fact.

**FTC v. LendEDU (2020).** See Tier 4 above — the full LendEDU entry is this skill's cleanest
regulator-adjudicated example of the "pay for rank, fabricate the reviews, disclose only when
investigated" pattern, because every element traces to the FTC's own press releases and consent
order rather than to reporting or estimate.
