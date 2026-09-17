# Source ledger

## Contents

1. [How to read this ledger](#how-to-read-this-ledger)
2. [evidence-tiers.md](#evidence-tiersmd)
3. [rating-forensics.md](#rating-forensicsmd)
4. [fraud-signals.md](#fraud-signalsmd)
5. [primary-sources.md](#primary-sourcesmd)
6. [Rejected sources](#rejected-sources)
7. [Open questions](#open-questions)

## How to read this ledger

`read-at-source`: **primary** (the cited document itself was opened), **abstract** (only the
abstract/summary page of a paywalled paper was read), **secondary** (a citing source describes a
primary document the ledger compiler did not open directly). A row with no value in this column has
not been checked and must not appear in a reference body without a `?` prefix. `type` uses the
vocabulary `evidence-tiers.md` §1 defines: `peer-reviewed` · `preprint` · `regulator` ·
`platform-first-party` · `vendor-methodology` · `industry-report` · `court-record` ·
`company-self-reported`.

## `evidence-tiers.md`

| Source | Date | Type | Supports | Read-at-source |
| --- | --- | --- | --- | --- |
| Consumer Reports, "Policies & Financials" | current | company-self-reported | Tier 0 placement | primary |
| Which?, no-ads/no-govt-funding policy | current | company-self-reported | Tier 0 placement | secondary |
| UFC-Que Choisir, member-funded/AFNOR NFX 50-005 | current | company-self-reported | Tier 0 placement | secondary |
| RTINGS, "Revamping Our Membership Program" | 2026-03-02 | company-self-reported | Tier 1 placement, corrected spend figure | primary (verbatim forum reproduction) |
| RTINGS, "About Us" / "How We Test" (TVs) | 2025-05-08/15 | company-self-reported | live product/TV counts | primary |
| Project Farm, Patreon "About" page | current | company-self-reported | Tier 1 placement | primary |
| Android Authority, "DxOMark scores shouldn't be your definitive camera rating system" (Kris Carlon) | 2019-10-09 | industry-report | DXOMARK conflict | primary |
| PetaPixel, MKBHD DXOMARK investigation writeup | 2017-10-13 | industry-report | DXOMARK conflict, corroborating | primary |
| corp.dxomark.com/about-us | current | company-self-reported | DXOMARK's own non-denial | primary |
| Bankrate SEC 8-K exhibit (Red Ventures acquisition close) | 2017-11-08 | company-self-reported | Red Ventures/Bankrate closing date | primary |
| Ziff Davis press release via BusinessWire, ID 20241001349422 | 2024 Q3 | company-self-reported | CNET's current owner | primary |
| Future plc, futureplc.com/brands/ | current | company-self-reported | TechRadar/Tom's Guide/Tom's Hardware ownership | primary |
| Valnet, valnetinc.com brand grid + valnetinc.com/xda | current | company-self-reported | ScreenRant/CBR/Collider/XDA ownership | primary |
| CNN Business, CNET AI-article scandal | 2023-01-25 | industry-report | Tier 3, CNET incident | primary |
| Gizmodo, CNET AI-article scandal | 2023-01-17 | industry-report | Tier 3, CNET incident, corroborating | primary |
| BusinessWire, Kape/Webselenese acquisition | 2021-03-08 | company-self-reported | Tier 4, vpnMentor/Wizcase ownership | primary |
| Kape Technologies investor materials (CyberGhost/PIA/ExpressVPN dates) | various | company-self-reported | Kape's own VPN brand portfolio | secondary |
| FTC press release, LendEDU settlement (Feb 2020) | 2020-02 | regulator | Tier 4, LendEDU | primary |
| FTC press release, LendEDU settlement finalised (May 2020) | 2020-05 | regulator | Tier 4, LendEDU, $350,000 figure | primary |
| FTC/insideprivacy.com, MediaAlpha/QuoteLab settlement | 2025-08-07 / 2025-09 | regulator (via secondary summary) | Tier 4, MediaAlpha | secondary |
| UL's own blog, Huawei 3DMark delisting | 2018-09-06 | industry-report | vendor-claim gaming, Huawei | primary |
| Samsung's own official GOS statement | 2022-03-03 | company-self-reported | vendor-claim gaming, Samsung, corrected attribution | primary |
| US EPA Notice of Violation, Volkswagen | 2015-09-18 | regulator | vendor-claim gaming, general "detect the test" pattern | secondary |
| CourtListener docket 1:16-cv-03223 | filed 2016-04 | court-record | Casper v. Sleepopolis | primary (docket-level, not full filing text) |
| Fast Company investigative account (33,000-sales/$1.6M estimate, ~20-month fee period) | ~2016–2017 | industry-report | Casper v. Sleepopolis, explicitly an estimate contested by Leesa's CEO | secondary |

## `rating-forensics.md`

| Source | Date | Type | Supports | Read-at-source |
| --- | --- | --- | --- | --- |
| Evan Miller, "Ranking Items With Star Ratings: An Approximate Bayesian Approach" | 2014-09-16 | industry-report (methodological blog, standard Bayesian statistics) | Dirichlet-multinomial formula | primary |
| Wilson (1927) / Evan Miller's popularisation | 1927 / 2009 | peer-reviewed / industry-report | Wilson score formula | secondary |
| IMDb Ratings FAQ | updated 2026-02-09 | company-self-reported | `WR` formula, `m = 25,000` | primary |
| Hu, Pavlou & Zhang, "On Self-Selection Biases in Online Product Reviews," *MIS Quarterly* 41(2) | 2017 | peer-reviewed | J-shape mechanism | primary (abstract; full text not opened) |
| Hu, Zhang & Pavlou, "Overcoming the J-Shaped Distribution of Product Reviews," *CACM* 52(10) | 2009 | peer-reviewed | J-shape mechanism, earlier framing | primary (abstract) |
| de Langhe, Fernbach & Lichtenstein, "Navigating by the Stars," *JCR* 42(6) | 2016 (online 2015-09-10) | peer-reviewed | mean-quality weak correlation | primary (abstract) |
| Muchnik, Aral & Taylor, *Science* 341(6146) | 2013-08-09 | peer-reviewed | herding, +32%/+25% | primary (abstract, exact quoted figures) |
| Zervas, Proserpio & Byers, "A First Look at Online Reputation on Airbnb," *Marketing Letters* 32(1) | online 2020-11-04 | peer-reviewed | Airbnb/TripAdvisor base rates | primary (abstract) |
| Fradkin, Grewal & Holtz, "Reciprocity and Unveiling," *Marketing Science* | 2021 | peer-reviewed | randomised unveiling experiment | secondary |
| Nosko & Tadelis, NBER Working Paper 20830 | — | peer-reviewed (NBER) | eBay Effective Percent Positive | secondary |
| Chen, Lee & Stevenson, *Psychological Science* | 1995 | peer-reviewed | cross-cultural extreme-response style | secondary |
| Consumer Reports, "Rating Methods" / Methodological Bulletin | — | company-self-reported | 5-year reliability window | primary |
| Luca & Luca, NBER Working Paper 25806 | rev. 2018 | peer-reviewed (NBER) | survivorship bias, Yelp exit correlation | secondary |
| arXiv, "The warm-start bias of Yelp ratings" | — | preprint | Yelp early-review inflation | secondary |
| SOCi, "The State of Google Reviews" | Jan 2015–Jul 2022 coverage | industry-report **(vendor-sourced, 53 client brands, not neutral — labelled as such in the file)** | Google rating drift | primary, but flagged non-neutral |
| Yelp, own 2025 Trust & Safety report | published 2026-02-25 | platform-first-party | 70%/17% recommended figures | primary |
| Trustpilot, 2025 Trust Report | published 2025-05-29 | platform-first-party | 7%/90% fake-review figures | primary |
| Google's own blog posts | ~2025-04-08, 2026-04-16 | platform-first-party | 240M+/292M+ removal figures | primary |
| Cochrane Handbook, Ch. 10 | current | industry-report / methodology standard | inverse-variance weighting | secondary |

## `fraud-signals.md`

| Source | Date | Type | Supports | Read-at-source |
| --- | --- | --- | --- | --- |
| Jindal & Liu, WSDM 2008 | 2008-02 | peer-reviewed | singleton/duplicate signal, 68%/8% figures | primary (author-hosted PDF) |
| Mukherjee, Venkataraman, Liu & Glance, ICWSM 2013 | 2013 | peer-reviewed | Yelp filter behavioural correlates | secondary |
| Luca & Zervas, *Management Science* 62(12) | 2016 | peer-reviewed | ~16% Yelp filter rate | primary (abstract) |
| Rayana & Akoglu, SpEagle, KDD 2015 | 2015 | peer-reviewed | collective detection | secondary |
| Xie, Wang, Lin & Yu, KDD 2012 | 2012 | peer-reviewed | temporal burstiness | secondary |
| He, Hollenbeck & Proserpio, *Marketing Science* 41(5) | 2022 | peer-reviewed | fake-review market, already-successful targets | abstract (publisher page 403'd on repeated attempts) |
| Ott, Choi, Cardie & Hancock, ACL-HLT 2011 | 2011 | peer-reviewed | ~90% deceptive-review classifier | primary |
| Meng et al., arXiv:2506.13313 | 2025-06-16 | preprint | LLM fake-review indistinguishability, 50.8% human accuracy | primary |
| BBB, Amazon brushing scam article | 2024 | industry-report | Amazon brushing mechanism | secondary |
| Amazon Vine programme, own policy | current | platform-first-party | mandatory Vine badge | secondary |
| Trustpilot, 2025 Trust Report | 2025-05-29 | platform-first-party | Trustpilot figures (duplicate of rating-forensics.md row) | primary |
| Google's Maps UGC policy + own blog posts | current / 2025-04-08 / 2026-04-16 | platform-first-party | review-gating ban, removal figures | primary |
| Yelp, "How We Approach Reviews," "Does Yelp recommend every review?," Trust & Safety pages | current | platform-first-party | recommendation software, ~70% figure | primary |
| Apple App Review Guidelines | current | platform-first-party | incentivised-review ban | primary |
| Google Play, "User Ratings, Reviews, and Installs" + 2017 policy post | current / 2017-06 | platform-first-party | incentivised-review ban, formalised 2017 | primary |
| Booking.com, "Guest reviews standards" + Partners help page | current / 2023-10 | platform-first-party | booking-gated review mechanism | primary |
| TrustRadius, "Content Integrity" + Terms of Use | current / 2016-07 | platform-first-party | incentive-legend disclosure | primary |
| Capterra, "Community Guidelines" | current | platform-first-party | incentive-disclosure rule (general) | primary |
| He et al., "Six Million (Suspected) Fake Stars on GitHub," ICSE 2026 / arXiv:2412.13459 | 2025-09 revision | peer-reviewed | StarScout, ~6M fake stars | primary |
| Tenable, "Download pumping..." | 2026-05 | industry-report (vendor security research) | npm download-count inflation | primary |
| Federal Register 2024-18519, 16 CFR Part 465 | published 2024-08-22, effective 2024-10-21 | regulator | FTC fake-review rule | primary |
| eCFR, 16 CFR Part 465 | current consolidated | regulator | rule text | primary |
| FTC, "Consumer Reviews and Testimonials Rule: Q&A" | 2025-05 | regulator | rule Q&A | primary |
| eCFR, 16 CFR 255.5 | current | regulator | Endorsement Guides | primary |
| FTC press release, Fashion Nova settlement | 2022-01 | regulator | enforcement precedent | primary |
| FTC press release, Fashion Nova refunds | 2025-01 | regulator | enforcement precedent, refund follow-up | primary |
| FTC, Sunday Riley matter reference | 2019 | regulator | enforcement precedent | secondary (docket page located, not full text) |
| FTC, Roomster press release | 2022-08 | regulator | enforcement precedent | primary |
| Directive (EU) 2019/2161, EUR-Lex | adopted 2019-11, applicable 2022-05-28 | regulator | Omnibus Directive | primary |
| European Commission, UCPD summary page | current | regulator | UCPD context | primary |
| DSA official text, Regulation (EU) 2022/2065, Articles 27 & 30 | applicable since 2024-02-17 | regulator | DSA marketplace/recommender obligations | primary |
| Freshfields, "DSA decoded #9" | 2025 | industry-report (law firm) | DSA interpretation | secondary |
| UK DMCC Act 2024, Schedule 20, legislation.gov.uk | current consolidated | regulator | UK fake-review blacklist | primary |
| CMA208 guidance PDF | 2025-04-04 | regulator | UK enforcement guidance | primary |
| AFNOR, NF Z74-501 standard listing | current | vendor-methodology (standards body) | French voluntary certification | primary |
| DGCCRF, "Avis en ligne: attention aux faux commentaires!" | 2024-03-27 | regulator | DGCCRF enforcement | primary |
| Mozilla, "Investing in what moves the internet forward" | 2025-05-22 | company-self-reported | Fakespot shutdown | primary |
| MacRumors, Fakespot shutdown coverage | 2025-05-22 | industry-report | Fakespot shutdown, corroborating dates | primary |
| TheReviewIndex, own About page | checked 2026-08-19 | company-self-reported | permanent shutdown | primary |
| RateBud/FakeFind/Yahoo Tech, ReviewMeta status | 2026 | industry-report (secondary, some with commercial incentive) | ReviewMeta likely offline, `?` status | secondary, explicitly flagged low-confidence |
| Springer, *Quality & Quantity*, review-bombing case study | 2024-09 | peer-reviewed | review bombing definition | secondary |
| arXiv:2405.06306, NLP review-bombing study | 2024-05 | preprint | review bombing detection | secondary |

## `primary-sources.md`

36 sources; ledger entries condensed to type + read-at-source, since each source's URL, what-it-proves
and access marker already appear in the reference file itself and are not repeated here.

| # (per primary-sources.md) | Type | Read-at-source |
| --- | --- | --- |
| 1 Backblaze Drive Stats | industry-report | primary (URL-verified live 2026-08-19) |
| 2 Puget Systems | industry-report | primary (URL-verified live) |
| 3 Stiftung Warentest | industry-report | secondary (paywalled full articles; headline figures from secondary summary) |
| 4 Which? UK car survey | industry-report | secondary (paywalled) |
| 5 TÜV-Report | regulator-adjacent | secondary (full report paywalled; press release read) |
| 6 ADAC Pannenstatistik | industry-report | primary (methodology page) |
| 7 JD Power IQS/VDS | industry-report | secondary (press releases + TrueDelta critique) |
| 8 NHTSA | regulator | primary (URL-verified live) |
| 9 RappelConso / EU Safety Gate / CPSC / RASFF | regulator | primary (RappelConso URL-verified live, actively updated) |
| 10 iFixit teardowns/Repairability Score | vendor-methodology | primary (URL-verified live) |
| 11 Warranty length signalling | peer-reviewed | secondary (paywalled journal articles) |
| 12 Class-action dockets | court-record | primary (CourtListener URL-verified live) |
| 13 EPREL | regulator | primary (URL-verified live) |
| 14 EU Energy Label rescaling | regulator | primary |
| 15 EU tyre label | regulator | secondary |
| 16 France réparabilité/durabilité | regulator | primary (URL-verified live) |
| 17 EU Ecodesign spare-parts | regulator | secondary |
| 18 ENERGY STAR | regulator | primary (URL live, deep-link path noted) |
| 19 FCC ID search | regulator | primary (URL-verified live via headless fetch) |
| 20 UL Product iQ | vendor-methodology (quasi-regulator NRTL) | primary (URL-verified live) |
| 21 EU Ecolabel Catalogue | regulator | primary (URL-verified live) |
| 22 EU Cyber Resilience Act | regulator | primary (URL-verified live; dates re-derived during hardening, see Verification record in the plan) |
| 23 endoflife.date | industry-report (community) | primary (URL-verified live) |
| 24 NVD/CVE/CVSS | regulator/standards-adjacent | secondary |
| 25 OpenSSF Scorecard | industry-report (foundation) | primary (URL-verified live) |
| 26 deps.dev | industry-report (vendor tool) | primary (URL-verified live) |
| 27 Status pages/postmortems | industry-report | secondary (example sources, not one canonical page) |
| 28 SOC 2/ISO 27001 verification | industry-report | secondary |
| 29 GitHub stars/npm downloads manipulation | peer-reviewed + industry-report | primary (StarScout, Tenable — duplicates fraud-signals.md rows) |
| 30 Abandoned-project checklist | peer-reviewed (arXiv) + industry-report | secondary |
| 31 Resale/depreciation methodology | industry-report | secondary |
| 32 Total cost of ownership (printer ink) | industry-report | secondary |
| 33 California CSLB | regulator | primary (URL-verified live via headless fetch) |
| 34 Companies House + The Gazette | regulator | primary (URL-verified live) |
| 35 Pappers/BODACC/INPI | industry-report + regulator | primary (URL-verified live) |
| 36 CourtListener/RECAP/Justia/PACER | court-record | primary (URL-verified live) |

## Rejected sources

Kept so the next agent doesn't re-search a dead end.

- **RTINGS "$714,000 / 618 products per year" figure.** Traces only to secondary aggregator blogs
  (Back2Gaming, jawa.gg); does not appear in RTINGS' own primary post. Rejected; replaced with
  RTINGS' own live figures (4,837 cumulative products, >40 TVs/year).
- **"UL/3DMark delisted Samsung devices over GOS in 2018/2022."** Conflates the real 2013 Samsung
  delisting (unrelated to GOS) with the 2022 GOS controversy, which UL/3DMark took no action on at
  all — the 2022 delisting was Geekbench's, a separate company. Rejected as stated; corrected
  attribution used in `evidence-tiers.md`.
- **"EIG sent FTC-compliance emails to JustHost (2011) and iPage (2012)."** These were EIG's own
  internal notices to its affiliates, not an FTC-issued action; no FTC enforcement action against
  EIG/JustHost/iPage exists in the FTC's legal library. Rejected; EIG/Newfold kept only as an
  unadjudicated ownership pattern.
- **Norwegian Consumer Council "16% of hotel reviews show inauthenticity" figure (Booking.com).**
  Located only via a secondary marketing-content aggregator (alibaba.com), not the Consumer
  Council's own publication. Not cited in the shipped file.
- **G2 ~$100 / Capterra ~$25 incentive-cap figures.** Traced only to comparison/marketing blogs, not
  the platforms' own current policy pages. Not cited with specific numbers in the shipped file.
- **App-store "48–72 hour" fraud-removal recovery claim.** Traces to an SEO/ASO blog, not a primary
  Apple/Google disclosure. Not cited in the shipped file.

## Open questions

Carried from the four research files; still open as of 2026-08-19.

- Askalidis, Kim & Malthouse (2017), "Understanding and Overcoming Biases in Customer Reviews,"
  *Decision Support Systems* — only located via a secondary summary; needs direct DOI/journal-page
  verification before any specific figure from it is cited.
- Google's own primary "Trust and Safety Report" (as opposed to its blog posts, which were used
  here) — the blog posts are platform-first-party and were read directly, but a more formal report,
  if one exists, was not located.
- A direct, on-record NYT/Wirecutter statement on the specific editorial/business firewall mechanism
  — only secondary/aggregator sourcing found; `evidence-tiers.md` flags the firewall claim as
  "moderately sourced" for this reason.
- Whether a live, dated, publicly accessible retailer-level GPU/component RMA/return-rate dataset
  exists anywhere in the EU or US as of 2026 (successor to the historical Mindfactory pattern) — not
  found; the routing table in `primary-sources.md` omits this lead entirely rather than pointing to
  a dead end.
- A single canonical, cross-programme-operator entry point for Environmental Product Declaration
  (EPD) lookups — not resolved; flagged as fragmented across programme operators.
- Whether EU CRA enforcement (post-2026-09-11 reporting deadline) will surface a consumer-visible,
  centrally searchable support-period disclosure, or only per-product documentation — too new to
  observe as of this ledger's compilation date.
- ReviewMeta's precise shutdown date and reason — no primary announcement exists; see the Rejected
  sources note above and the `?`-flagged entry in `fraud-signals.md`.
