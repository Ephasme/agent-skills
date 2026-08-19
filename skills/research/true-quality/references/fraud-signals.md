# Fraud and manipulation signals

## Contents

1. [Detection signals, strongest first](#detection-signals-strongest-first)
2. [The LLM erosion](#the-llm-erosion)
3. [Platform mechanics and first-party artifacts](#platform-mechanics-and-first-party-artifacts)
4. [Regulation as artifact generator](#regulation-as-artifact-generator)
5. [Dead tools — do not use](#dead-tools--do-not-use)
6. [Review bombing — a negative control](#review-bombing--a-negative-control)
7. [Query patterns](#query-patterns)
8. [Myths](#myths)

## Detection signals, strongest first

Behavioural and network signals beat purely linguistic ones — all approximable from a public page
by reading reviewer profiles and the review timeline, not just review text.

1. **Singletons and duplicate text.** Jindal & Liu (WSDM 2008): 68% of reviewers wrote exactly one
   review, only 8% wrote five or more; duplicate/near-duplicate text across different accounts
   (labelled at Jaccard similarity ≥ 0.9) is a strong positive spam signal, since genuine reviewers
   essentially never copy another reviewer's wording. *Check: sample several reviews' text for
   shared distinctive phrasing across accounts on the same listing.*
2. **Behavioural features over language.** Mukherjee, Venkataraman, Liu & Glance (ICWSM 2013)
   reverse-engineered Yelp's filter and found it correlates with reviewing frequency, account
   age/recency, geographic clustering of a reviewer's other reviews, and the share of extremely
   positive reviews — more than with text. *Check: click a reviewer's profile; a new account, a
   review history clustered in one city/window, or an almost-entirely-5★ history are the visible
   proxies.*
3. **Fraud incentive peaks at weak or recently damaged reputation.** Luca & Zervas (*Management
   Science* 62(12):3412–3427, 2016): roughly 16% of Yelp restaurant reviews were filtered as
   suspicious; a business is more likely to buy fake reviews when it has few reviews or recently
   received bad ones. *Check: a low-review-count listing, or one with a sudden wave of very
   positive reviews right after a visible negative event, matches the predicted pattern.*
4. **Collective detection beats any single signal.** Rayana & Akoglu's SpEagle (KDD 2015) combines
   text, metadata and the reviewer–product graph and outperforms single-signal baselines at scale.
   *Check: do a handful of reviewers on the target listing also touch a suspiciously narrow,
   unrelated set of other products in the same short window (visible via reviewer-history links)?*
5. **Temporal burstiness correlated with rating direction.** Xie, Wang, Lin & Yu (KDD 2012): genuine
   arrival patterns are stable and uncorrelated with rating; spam campaigns produce short-window
   bursts correlated with rating direction. *Check: if dates are exposed, a sharp spike — especially
   skewed to one star value — clustered in a narrow window is the operational signature. Before
   calling it fraud, check it isn't a dated public controversy (review-bombing, below) or an organic
   event (press feature, sale).*
6. **Purchased reviews move ratings, then decay — and target already-successful listings too.**
   He, Hollenbeck & Proserpio (*Marketing Science* 41(5):896–921, 2022; confirmed from its abstract,
   publisher page returns 403) hand-collected data from private Facebook groups selling fake Amazon
   reviews: a significant but short-lived rating/count bump, and a wide range of products buy fake
   reviews — **including products that already have many reviews and high ratings**, not just
   cold-start sellers. *A review-count or rating discontinuity at a specific date, not explained by
   a product update or press coverage, is the tell.*

## The LLM erosion

Ott, Choi, Cardie & Hancock (ACL-HLT 2011, 309–319) reached "nearly 90%" accuracy distinguishing
deceptive from genuine hotel reviews with a bigram+LIWC classifier, on the finding that deceptive
reviews skew imaginative/narrative and genuine reviews skew concrete/informative. **This signal is
now substantially weakened.** A 2025 preprint, Meng et al., "Large Language Models as 'Hidden
Persuaders': Fake Product Reviews are Indistinguishable to Humans and Machines" (arXiv:2506.13313,
2025-06-16), found human raters averaged 50.8% accuracy — chance level — on LLM-written fake
reviews, with LLM judges performing equivalently or worse. **Consequence: fluency and specificity
are no longer evidence of authenticity.** Fall back on the behavioural/graph/temporal signals above,
which don't depend on writing style, and watch for repeated paragraph *structure* (not wording)
across a batch — a tell of shared-template generation that survives paraphrasing.

## Platform mechanics and first-party artifacts

**Amazon.** "Brushing" schemes place real, low-cost orders shipped to real people's addresses
without their consent, then post a review from the same fake account — Amazon labels it "Verified
Purchase" because a real transaction genuinely occurred. **No page-level signal distinguishes a
brushed Verified Purchase from a genuine one** — this is exactly why the badge cannot be treated as
sufficient evidence, only as raising the cost of fraud relative to unverified reviews. Amazon Vine
reviews carry a mandatory, non-removable "Vine Customer Review of a Free Product" badge — read as
"free product, no purchase pressure," not identically to an organic review, and check whether a
listing's *early* reviews are disproportionately Vine-tagged. ASIN merging/hijacking imports an
unrelated review history onto a listing; watch for review text describing a visibly different
product than what's currently sold under that ASIN, or an implausibly large review history on a
recently created listing.

**Trustpilot.** Its own 2025 Trust Report: 4.5M fake reviews removed in 2024 (7% of that year's
submissions, 7.4% in the report's body text), 90% caught automatically before publication.
Business-initiated invitations are allowed but must be unbiased ("review gating" — inviting only
likely-happy customers — is the targeted abuse). Review cards indicate "verified" (invited-and-
confirmed) status where applicable.

**Google Business Profile.** Review gating is explicitly banned. Google's own reporting: 240M+
policy-violating reviews removed in 2024, 292M+ in 2025 against 1B+ **published** reviews. A visible
"reviews paused" banner on a profile is Google's own fraud-detection output surfaced to the
consumer — check for it before reconstructing the signal yourself.

**Yelp.** Recommendation software evaluates every review on "hundreds of signals"; about 70% of all
reviews platform-wide are currently recommended (down from 75% in 2022 — see `rating-forensics.md`'s
base-rate table), 17% "not currently recommended." Non-recommended reviews remain visible via a link
but don't count toward the star average or count — **check the gap between total and recommended,
and read what got filtered.** No Yelp employee can override the software's decision. Four labelled
Consumer Alert banner types exist for businesses with unusual activity patterns.

**App stores (Apple, Google Play).** Both explicitly ban incentivised ratings/reviews and
install-count manipulation, formalised publicly by Google in 2017 and still in force. Watch for a
rating spike immediately after a version update (both a legitimate re-baselining window and a window
fraudsters exploit), and for generic praise disconnected from any specific in-app feature. (A
commonly cited "48–72 hours" fraud-removal figure traces only to an SEO/ASO blog, not a primary
Apple/Google source — do not repeat it as fact.)

**Booking.com.** Only a completed booking (not a completed *stay*) gates review eligibility — a
documented gap lets a cash-marked, never-fulfilled reservation produce a real review. No page-level
signal distinguishes this from a genuine stay; fall back on text/behavioural clustering across a
property's reviews. (A frequently cited "16% of hotel reviews show inauthenticity indicators"
Norwegian Consumer Council figure was only locatable via a secondary aggregator in this corpus'
research — treat as unconfirmed at primary source, not as a citable statistic.)

**G2 / Capterra / TrustRadius (B2B software).** All three permit disclosed, vendor-funded incentives
(gift cards, donations) for a review but ban payment contingent on sentiment. TrustRadius exposes an
explicit "incentive legend" tag on the review card. An incentive tag is a disclosed, legal,
*response-biased* signal (skews toward casual reviewers willing to spend a few minutes for a small
reward) — not evidence of fakery on its own. (Specific dollar caps circulating for G2/Capterra trace
only to comparison-blog secondary sources, not the platforms' own current policy pages — do not cite
a specific figure without checking the platform's current page.)

**GitHub.** He et al. (ICSE 2026 / arXiv:2412.13459), analysing 20TB of GitHub metadata, built the
open detector StarScout and flagged **~6M suspected fake stars** across ~18,600 repositories,
independently corroborated when GitHub's own enforcement subsequently deleted 90.42% of the flagged
repositories. Check the Stargazers list for accounts with default avatars, empty bios, no public
repos, and account-creation dates clustered tightly with many other stargazers — the StarScout
signature. A star count large relative to real usage evidence (issues, PRs, forks, dependent-package
counts) is the practical, no-API proxy.

**npm / package registries.** Tenable demonstrated npm's public download counter can be inflated by
repeated direct requests to a package's tarball URL — no account compromise needed, ~17,000 fake
downloads in about an hour from a standard laptop. Cross-check a reported download count against
independent adoption evidence (GitHub stars/forks/issues on the linked repo, whether major projects
list it as a dependency) rather than trusting the number alone.

## Regulation as artifact generator

Each rule matters here only because it forces an *observable artifact* onto the page.

- **US FTC 16 CFR Part 465** (effective 2024-10-21): bans fake reviews outright (§465.3), buying
  sentiment-contingent reviews (§465.4), undisclosed insider reviews (§465.5), and claiming
  completeness while suppressing reviews (§465.6). Civil penalties are **inflation-adjusted
  annually — $53,088 per violation as of 2025-01-17, unchanged for 2026 — state the mechanism and
  the as-of date, never a bare figure.** A proposed ban on "review hijacking" (ASIN/product-merge
  abuse) was **dropped from the final rule**; that conduct is still pursued case-by-case under the
  general FTC Act. *Check: does the site's negative-review section look functioning and unfiltered
  (a weak positive signal), and does any "this reflects all feedback" claim survive a spot-check
  against other public complaint volume?*
- **US FTC Endorsement Guides, 16 CFR Part 255** (updated 2023-06): requires disclosure of any
  connection that "might materially affect the weight or credibility" of an endorsement and that a
  reasonable audience wouldn't already expect. *Check: does an influencer/blog "review" carry an
  explicit disclosure where a material connection plausibly exists?*
- **Enforcement precedent, three shapes of violation:** Fashion Nova ($4.2M, 2022; refunded to
  ~600K consumers Jan 2025) — suppressing reviews under 4 stars while claiming displayed reviews
  reflect all feedback. Sunday Riley (2019) — a CEO directed employees to post fake positive reviews
  using alternate accounts; settled with a conduct order, no fine, no admission. Roomster (2022,
  FTC + 6 states, still cited in 2024–2026 coverage) — fake reviews plus fake underlying listings.
- **EU Omnibus Directive (2019/2161)**, applicable since 2022-05-28: adds fake/commissioned reviews
  to UCPD Annex I's automatic-unfair blacklist (no need to separately prove consumer harm), and
  amends UCPD Article 7 to require a trader disclose *whether and how* it verifies that published
  reviews come from people who actually used or bought the product. *Check: does an EU-facing review
  section carry an explicit verification-method statement (often in an FAQ)? Its absence is a
  documented compliance gap, not proof of fraud.*
- **EU Digital Services Act** (Regulation (EU) 2022/2065, applicable to all providers since
  2024-02-17): Article 30 requires marketplaces to collect/verify trader identity before listing;
  Article 27 requires disclosure of a recommender system's main ranking parameters — relevant where
  a "most helpful" review sort functions as one. **These support review integrity indirectly
  (trader accountability, ranking transparency) and are not a fake-review ban.**
- **UK DMCC Act 2024, Schedule 20** (fake-review provisions in force from April 2025; CMA guidance
  CMA208, published 2025-04-04): blacklists submitting/commissioning fake reviews, concealing paid
  incentives, misleading publication or lack of verification procedure, and — distinctively —
  offering services that *facilitate* any of the above, making review-farm brokers directly liable.
  *Check: does a UK-facing platform publish a stated fake-review prevention/removal policy, per
  CMA's recommended baseline?*
- **France: AFNOR NF Z74-501 → ISO 20488**, plus DGCCRF enforcement. A voluntary certification mark
  ("NF Service – Avis en Ligne") for review-collection processes — not a legal requirement.
  DGCCRF (France's consumer-fraud regulator) has specifically prosecuted businesses for *falsely
  claiming* this certification. *Check: if a French-facing site claims the mark, does it link to an
  actual AFNOR record? Absence of the mark means nothing (most sites don't have it); a false claim
  of it is a documented, prosecutable pattern.*

## Dead tools — do not use

**Fakespot** shut down completely 2025-07-01 (Firefox's Review Checker feature stopped 2025-06-10),
per Mozilla's own blog post. **TheReviewIndex**'s own About page states it is "permanently down due
to Amazon policy changes." **ReviewMeta**'s status is `?` — no primary shutdown announcement was
located; multiple independent secondary sources describe it as offline as of early 2026, but treat
the *fact* of non-functionality as likely and the *stated reasons* as unconfirmed. **Never instruct
anyone to check any of these three** — all citing sources describing them as functional predate
2025.

## Review bombing — a negative control

Distinct from fraud-for-profit review manipulation: coordinated posting of a disproportionate volume
of *genuine* but off-topic negative reviews, triggered by an external controversy rather than the
product itself (a political statement, a casting decision, a corporate action). An NLP study of
50,000+ Metacritic user-score aggregations (arXiv:2405.06306, 2024-05) and a case study of *The Last
of Us Part II* (*Quality & Quantity*, 2024-09) both identify the signature: a sharp negative spike
correlated with a datable public controversy, and review text referencing the controversy rather
than the product. **Do not classify a genuine, controversy-driven ratings collapse as fabricated
review fraud** — the correct response is to discount the *magnitude* of the swing, not to assume
every individual review is fake. Distinguish it from a commissioned fraud burst (which correlates
with a paid campaign, not a public news event) by a quick news search for the product/company name
around the spike's date.

## Query patterns

Replace `[product]`/`[brand]` with the actual item; run several per product, not just one — routes
around SEO-optimised affiliate content structurally, since none of the following venues/signals can
be faked at listicle scale.

1. `[product] site:reddit.com` — restricts to forum discussion, bypassing SEO domains.
2. `[product] site:reddit.com after:2024-01-01` — date-filters out a stale recommendation for a
   since-revised or discontinued product.
3. `[product] "stopped working" OR "broke after" OR "died after"` — failure-narrative language has
   near-zero SEO/affiliate value to write, so it routes around promotional content.
4. `[product] "returned it" OR "sent it back" OR "waste of money"` — same logic for dissatisfaction.
5. `[brand] recall OR lawsuit OR "class action"` — surfaces regulatory/legal pages no
   manufacturer-friendly listicle will link to.
6. `[product] teardown OR "torn down"` — component-level analysis verifying actual build/parts.
7. `[product] vs [competitor] site:rtings.com OR site:consumerreports.org OR site:which.co.uk` —
   restricts a head-to-head to Tier 0/1 domains, skipping the SEO layer entirely.
8. `[company] "who owns" OR "parent company" site:wikipedia.org` — fast ownership check (follow up
   by reading the infobox's own cited source, not just the summary).
9. `[product] "one year later" OR "six months later" OR "long term review"` — targets longevity
   reports, structurally absent from launch-week affiliate content.
10. `[product] complaint site:bbb.org OR site:trustpilot.com` — complaint-aggregator domains
    directly, rather than a site's own curated embedded widget.
11. `"[distinctive sentence fragment]"` (exact phrase, quoted) — checks whether prose is duplicated
    verbatim across nominally independent domains.
12. `[product] forum -site:reddit.com` — broadens to a differently-moderated community after
    checking Reddit, mitigating single-platform brigading/consensus risk.

Apply the Wayback Machine (`web.archive.org/web/*/[url]`) alongside these wherever a
ranking-changed-after-payment or ownership-tone-shift check (`evidence-tiers.md`) is relevant — none
of the above search patterns can see a page's edit history, only its current state. Two differently
moderated venues, minimum, before treating forum consensus as corroboration — forums are themselves
manipulable.

## Myths

1. **"A 5.0 average is inherently suspicious."** Not supported as a standalone rule — see
   `rating-forensics.md`'s J-shape section. What's anomalous is a *missing* complaint tail, not a
   high mean.
2. **"More reviews automatically means harder to fake."** Not unconditionally true — purchased-
   review campaigns specifically target already-successful, high-review-count listings too.
3. **"A 'Verified Purchase' badge means the review is genuine."** Not supported — brushing (Amazon)
   and cash-marked non-stays (Booking.com) both produce genuinely "verified" fake reviews.
4. **"Detailed, specific-sounding reviews are more trustworthy than short generic ones."** Defensible
   pre-2023, unreliable now — LLM-generated fake reviews can be prompted for exactly the concrete
   detail that used to distinguish genuine ones.
5. **"Third-party checkers like Fakespot/ReviewMeta will catch it."** All dead or non-functional as
   of 2025–2026 — see above.
6. **"Reading only the 1-star reviews reveals the truth."** Negative reviews are subject to the same
   selection dynamics as positive ones — under-reporting bias, competitor-commissioned fake-negative
   sabotage, and review-bombing all apply. Low ratings deserve the same scrutiny as high ones, not
   automatic trust.
7. **"No reviews, or very few, always means a new or bad product."** Low review count correlates
   with *higher fraud incentive*, not with badness — a legitimate niche or recently launched product
   can have few organic reviews. Raise scrutiny of what exists; don't assume a defect.
