# Rating forensics: what a star average actually measures

## Contents

1. [The starting intuition, corrected](#the-starting-intuition-corrected)
2. [Why a mean is not an estimate](#why-a-mean-is-not-an-estimate)
3. [The three lower-bound formulas](#the-three-lower-bound-formulas)
4. [Combining heterogeneous evidence](#combining-heterogeneous-evidence)
5. [Why real rating distributions are J-shaped](#why-real-rating-distributions-are-j-shaped)
6. [Systematic biases in who rates at all](#systematic-biases-in-who-rates-at-all)
7. [Platform base-rate table](#platform-base-rate-table)
8. [Dead ends and myths](#dead-ends-and-myths)

## The starting intuition, corrected

"A 5.0 average is very often bad data" is half right. Rating distributions are structurally
J-shaped — heavy at 5★, a smaller spike at 1★, thin in the middle — with **zero fraud required**;
this is the honest, default shape (see below). A 5.0 is not inherently suspicious. What *is*
load-bearing: a 5.0 built on a small `n` is *uninformative*, not excellent, and a rating quoted
without its platform's own base rate is close to meaningless. This file teaches the sequence:
`n` → lower bound → distribution shape → platform base rate → timing → reviewer behaviour — never
the mean on its own.

## Why a mean is not an estimate

A raw average is a point estimate with no uncertainty attached. Sorting or trusting by
`positive − negative` or by raw mean both produce absurd rankings once sample size varies: a
2-of-2 perfect score should not outrank a 100-of-101 near-perfect one, but the raw fraction says it
does (1.00 > 0.990). The fix is a **lower confidence/credible bound**, computed and compared — never
"more stars wins," and never "higher average wins" without looking at `n`.

## The three lower-bound formulas

All three are implemented in `../scripts/rating-bounds.py` (stdlib `python3`, no third-party
import; state this dependency once and move on — if `python3` is unavailable, every formula below
is stated in full so it can be computed by hand).

**1. Wilson score lower bound — binary signals only (helpful/not, recommend/don't, thumbs).**
With `p̂ = positive/n`, `z` = the one-sided normal quantile (`z = 1.96` for 95%, the value this
skill uses everywhere so runs stay comparable):

```
denom  = 1 + z²/n
center = (p̂ + z²/(2n)) / denom
adj    = z · sqrt( p̂(1−p̂)/n + z²/(4n²) ) / denom
lower  = center − adj
```

**Scope prohibition, stated because it is the error people actually make: never apply this formula
to a star-rating mean.** A 5-star mean is not a Bernoulli proportion. `python3 rating-bounds.py
--binary 100,101` gives `0.9460`; the same call for `2,2` gives `0.3424` — the 100-of-101 item
correctly ranks higher despite the lower raw fraction.

**2. Dirichlet-multinomial credible-interval lower bound — the correct analogue for a K-star
histogram.** Put a flat Dirichlet(1,...,1) prior over the probability vector of a rater giving each
star level; the posterior after observing counts `(n_1,...,n_K)` is Dirichlet(`n_1+1,...,n_K+1`).
With `N = Σ n_k`, `K` star levels, `s_k = k`:

```
S = Σ_k s_k·(n_k+1)/(N+K)
    − z · sqrt( ( Σ_k s_k²·(n_k+1)/(N+K) − ( Σ_k s_k·(n_k+1)/(N+K) )² ) / (N+K+1) )
```

The first term is the shrunk (Bayes-adjusted) mean; the subtracted term is `z` times the estimated
standard deviation of that mean. Rank/compare on `S`, never the raw mean. Assumption worth stating:
the flat prior is conservative, not maximally efficient, since the true empirical prior for online
reviews is J-shaped, not uniform (see below) — so `S` is, if anything, an under-estimate.

**Worked example (Evan Miller, "Ranking Items With Star Ratings: An Approximate Bayesian Approach",
2014-09-16, evanmiller.org/ranking-items-with-star-ratings.html), reproduced by
`rating-bounds.py --selftest`:**

| Item | n | histogram (1★..5★) | raw mean | shrunk mean | variance | lower bound `S` |
| --- | --- | --- | --- | --- | --- | --- |
| A | 23 | 0,0,0,2,21 | 4.913 | 4.571 | 0.0331 | **4.215** |
| B | 4,100 | 82,123,246,779,2870 | 4.520 | 4.518 | 0.000193 | **4.491** |

Despite A's higher raw average, **B has the higher, defensible lower bound and should rank/be
trusted above A.** (The histograms are illustrative constructions consistent with the stated `n`
and mean, not scraped real data — build the actual histogram from the page you're reading, don't
assume one.) Number-of-ratings-needed scales **quadratically** with target interval width when
ratings are spread out, but only **linearly** when they already agree — a handful of ratings is
"enough" only when they closely agree, not merely because there are many of them.

Reported precision: an answer states the bound to **two** decimals; `--selftest` checks to three,
to catch an implementation error rather than because the third decimal is meaningful.

Two related interval forms, same practical behaviour as Wilson: **Jeffreys** (Bayesian, Beta(1/2,1/2)
prior, posterior Beta(`x+1/2, n−x+1/2`)) and **Agresti–Coull** (`ñ = n+z²`, `p̃ = (x+z²/2)/ñ`, then
the ordinary normal interval) — for a 95% interval this reduces to the well-known
`p̃ = (x+2)/(n+4)`.

**3. Bayesian / shrinkage average toward a category prior.** The simplest form is Laplace/add-one
smoothing (a flat Beta(1,1) prior). The general form, used by IMDb's own published Top-250 formula:

```
WR = (v/(v+m))·R + (m/(v+m))·C
```

`R` = the item's own raw mean, `v` = its own vote count, `m` = prior strength, `C` = the prior mean
across the eligible pool. IMDb's own help page (updated 2026-02-09) states the current minimum-votes
threshold `m = 25,000` — **the widely copied `m = 1,300` is stale and should not be cited.** `m` is
a modelling choice, not a universal constant: a category-level shrinkage for, say, dehumidifiers
should use a category-appropriate `m` (tens, not tens of thousands), never IMDb's own number
transplanted into an unrelated domain.

**James–Stein / empirical-Bayes shrinkage, in one paragraph.** When estimating many related
quantities at once (every seller's true return rate, every SKU's true defect rate), shrinking each
individual estimate toward the group mean provably reduces total estimation error once there are
three or more groups — Stein's paradox. Basic form: `estimate_i = x̄ + c·(x_i − x̄)`, `c < 1`
data-driven. Relevant here only when comparing many items of the same category at once, not for a
single item in isolation.

## Combining heterogeneous evidence

**Inverse-variance weighting** (the standard fixed-effect meta-analysis pooling formula, Cochrane
Handbook Ch. 10) is the principled way to combine independent estimates of the *same* quantity:

```
w_i = 1/v_i     Ŷ = (Σ_i w_i·Y_i) / (Σ_i w_i)     pooled SE = √(1/Σ_i w_i)
```

Worked example — a lab spec vs. a crowd-rating-derived estimate of the same real-world quantity
("actual battery life in hours"): lab (n=5 bench tests) mean 10.2h, SE 0.3h, variance 0.09; crowd
(large but noisy) mean 9.0h, SE 1.5h, variance 2.25. Weights `w_lab ≈ 11.11`, `w_crowd ≈ 0.44`;
pooled estimate `≈ 10.15h`, with the small, precise lab measurement carrying ~96% of the weight
despite far fewer data points.

**The caveat that matters more than the formula: inverse-variance weighting only accounts for
random sampling variance, never systematic bias.** A biased source's standard error can shrink
arbitrarily with more ratings while its *bias* stays constant — naively weighting a huge, precise,
but structurally biased crowd average produces a confidently wrong pooled estimate. Before pooling,
diagnose: (1) are the two sources measuring the same construct (a lab dB reading and a crowd's
"quiet enough" feeling are related, not identical)? (2) does a documented bias mechanism from the
sections below explain a disagreement — if so, discount or exclude that source rather than pool it
at face value; (3) if no bias mechanism explains a persistent gap between two low-variance sources,
treat the disagreement itself as informative (the lab conditions may not reflect real use).

Consumer Reports is a working exemplar of doing this at scale: 63 in-house labs plus a separate,
large-sample Annual Reliability Survey, kept as **two labeled streams** rather than blended
invisibly, with the survey specifically targeting the multi-year failure window (below) rather than
first-week sentiment.

## Why real rating distributions are J-shaped

Hu, Pavlou & Zhang, "On Self-Selection Biases in Online Product Reviews," *MIS Quarterly* 41(2):
449–471 (2017) — building on Hu, **Zhang** & Pavlou, "Overcoming the J-Shaped Distribution of
Product Reviews," *Communications of the ACM* 52(10):144–147 (2009; note the reversed author order
and that this earlier paper calls the same mechanism *purchasing* bias where the 2017 paper calls it
*acquisition* bias — do not mix the labels) — show almost all products exhibit an asymmetric,
bimodal ("J-shaped") rating distribution from two **legitimate** self-selection mechanisms, with
**no fraud invoked in either paper**:

1. **Acquisition/purchasing bias** — buyers already had a favourable predisposition before they
   ever used the product, so the pool of people who try it skews positive from the start.
2. **Under-reporting ("brag-or-moan") bias** — among people who did try it, those with *extreme*
   reactions are disproportionately likely to bother writing a review at all.

**Consequence: a J-shaped histogram (mostly 5★, a real 1★ spike, thin middle) is the expected,
honest baseline — not evidence of manipulation.** What genuinely differs from this baseline —
stated as an inference, since no study here puts a numeric threshold on it — is a histogram with
the 1–3★ complaint tail **missing entirely**: near-total 5★ with almost nothing else is harder to
produce organically and is more consistent with review-gating or fabrication than with a normal
J-shape. Ship this as reasoning, never as a cutoff percentage — no source supports one.

**Separately, average ratings correlate weakly with independently measured quality.** de Langhe,
Fernbach & Lichtenstein, "Navigating by the Stars," *Journal of Consumer Research* 42(6):817–833
(2016), analysing 1,272 products across 120 categories, found average online ratings (1) do not
converge with Consumer Reports quality scores, (2) are frequently based on too few reviews to be
informative, (3) do not predict resale price, and (4) are systematically higher for expensive,
premium-branded products even after controlling for measured quality. **Do not use a raw star
average as a quality estimate on its own** — treat it as one input alongside count, distribution
shape, and independent test data, and explicitly downweight it when comparing a premium item to a
cheaper one (brand halo inflates ratings independent of quality).

## Systematic biases in who rates at all

**Herding — a single early vote measurably inflates the aggregate.** Muchnik, Aral & Taylor,
*Science* 341(6146):647–651 (2013-08-09), a randomized field experiment: an artificial early
positive vote raised the likelihood a later rater also rated positively by **32%**, and produced
accumulating herding that raised the final aggregate score by **25%** on average. **Keep these two
figures distinct — they measure different things (a per-rater probability shift vs. a final-score
shift) and must never be compressed into "a 25–32% effect."** The effect is asymmetric: an
artificial early *negative* vote gets self-corrected by later raters; an early positive one does
not. Operational rule: a young listing's *early* rating history deserves more scepticism than its
later history, and single-digit-`n` items are especially exposed.

**Reciprocity and retaliation bias in two-sided marketplaces.** When both parties rate each other
(host↔guest, buyer↔seller), fear of retaliation and desire to reciprocate inflate ratings well above
a one-sided system. Zervas, Proserpio & Byers, "A First Look at Online Reputation on Airbnb, Where
Every Stay is Above Average," *Marketing Letters* 32(1):1–16 (online 2020-11-04): **~95% of Airbnb
listings sit at 4.5 or 5.0 stars**, essentially none below 3.5; by contrast TripAdvisor hotels
average **3.8★** and B&Bs **4.1★**, with far more variance, and TripAdvisor's own vacation-rental
ratings (same asset type as Airbnb) show only ~85% at 4.5–5★ — still lower than Airbnb's ~95%. A
randomized field experiment (Fradkin, Grewal & Holtz, "Reciprocity and Unveiling in Two-Sided
Reputation Systems," *Marketing Science*, 2021) found hiding each side's review from the other
until both submit **increases total reviewing and lowers (more honest) ratings** by removing the
ability to retaliate strategically.

eBay's naive "percent positive" hides that only ~65% of transactions receive any feedback at all
(Nosko & Tadelis, NBER Working Paper 20830). The corrected metric, **Effective Percent Positive**,
divides by *all* transactions, not just reviewed ones: `EPP = positive_transactions / all_transactions`.
Worked example: Seller A (120 transactions, 99 positive, 1 negative, 20 silent) and Seller B (150
transactions, 99 positive, 1 negative, 50 silent) both show naive "99% positive" — but
`EPP_A ≈ 83%` and `EPP_B ≈ 66%`. The seller with more silent (plausibly worse) transactions looks
meaningfully worse once missing data isn't just discarded. **Consequence — this mechanism is
specific to two-sided markets where both parties rate each other; do not over-generalise it to a
one-directional product review.**

**Rating inflation over time, and platforms differ from each other.** A rating is only meaningful
relative to its own platform's norm and era — see the base-rate table below.

**Culture affects scale use.** "Extreme response style" — picking scale endpoints over the midpoint
— is not culturally universal. Chen, Lee & Stevenson, *Psychological Science* (1995), a classic
cross-cultural study (later replicated across 26 countries): US respondents picked extreme values
~41% more often than Japanese respondents (19.2% vs. 13.6%), while Japanese respondents picked the
midpoint ~33% more often. These are Likert-survey findings, not e-commerce widget data directly —
transfer is plausible, not independently confirmed — and a rater's own country is usually invisible
to an agent anyway; the operational use is aggregate-level caution when a rater base is known to
skew toward one cultural extreme.

**The review window is early; the failure window is late.** Nothing about day-one satisfaction
constrains year-three reliability. Consumer Reports' own methodology explicitly targets this: its
"Predicted [Brand] Reliability" ratings are "based on a statistical model that estimates problem
rates within the first five years of ownership (first two years for smartphones)" —
data.consumerreports.org/rating-methods/ — a purpose-built long-horizon instrument, distinct from a
review-site star average. (A specific "30/60/90-day honeymoon period" framing circulates in
practitioner blogs with no peer-reviewed or regulator source — usable as intuition, never cited as
established fact.) **Operational rule: seek a source explicitly designed to measure the multi-year
window (see `primary-sources.md`) rather than inferring durability from a review-date-agnostic
average.**

**Survivorship bias.** The listings still visible today are not a random sample of everything that
ever existed on the platform — poorly rated businesses are disproportionately delisted, closed or
discontinued. Luca & Luca, NBER Working Paper 25806, find lower-Yelp-rated restaurants are
systematically closer to the margin of exit (a cost shock raised the exit likelihood of a
Yelp-median 3.5-star restaurant by ~10%, with no discernible effect on 5-star restaurants) —
restaurant-specific data, but illustrating a domain-general mechanism. **A listing that has survived
N years with a good rating is not thereby proven reliable: many similarly-rated newcomers may
already have failed and vanished from the comparison set.** Where a platform preserves delisted or
closed entries, prefer that view over a live-listings-only search.

## Platform base-rate table

Compare a rating to its own platform's norm, never to a fixed absolute scale — and note the year,
since these move.

| Platform | Base rate | Year / source |
| --- | --- | --- |
| Airbnb | ~95% of listings at 4.5–5.0★ | 2021 (Zervas, Proserpio & Byers) |
| TripAdvisor (hotels) | 3.8★ average, far more variance | same 2021 paper |
| TripAdvisor (vacation rentals) | ~85% at 4.5–5★ | same 2021 paper |
| Yelp | 70% of reviews "recommended", 17% "not recommended" (down from 75%/— in 2022) | Yelp's own 2025 Trust & Safety report, published 2026-02-25 |
| Yelp | first review of a listing averages 4.1★; settles to ~3.69★ by the 20th review ("warm-start bias") | arXiv empirical analysis, arxiv.org/pdf/1202.5713 — moderate strength, not a confirmed peer-reviewed venue |
| Trustpilot | 7% of 2024 reviews removed as fake (7.4% in report body text, up from 6.1% in 2023); 90% caught automatically before publication | Trustpilot's own Trust Report, published 2025-05-29 |
| Google Business Profile | 240M+ policy-violating reviews removed in 2024; 292M+ removed in 2025 alongside 1B+ **published** (not "submitted") reviews | Google's own blog posts, ~2025-04-08 and 2026-04-16 |
| Google Business Profile (average rating over time) | reported rise from 3.74★ (Jan 2015) to 4.11★ (Jul 2022) | **Vendor research, not independent**: SOCi, a reputation-management SaaS company, over 53 of its own client brands (31,326 profiles) — cite only as a directional, vendor-sourced claim, never as a neutral study |

## Dead ends and myths

- **"A 5.0/5.0 average is the best possible signal of quality."** Not supported — a perfect small-`n`
  average is exactly the case this file says to be most sceptical of; in two-sided marketplaces,
  near-5★ is the *typical*, uninformative outcome for the large majority of listings, not a
  distinguishing signal.
- **"Just plug a star-rating percentage into the Wilson formula."** Wrong application. Wilson is
  derived for binary Bernoulli data; use the Dirichlet-multinomial bound for star histograms.
- **"A missing complaint tail means fraud, full stop."** Overclaimed. It is an anomaly worth
  investigating (see `fraud-signals.md` and `evidence-tiers.md`'s artifact table), not proof on its
  own — legal review-gating produces the same shape as fabrication.
- **"There's a sourced threshold for the 5★:4★ ratio, or for what percentage counts as anomalous."**
  No source in this file's research establishes one. Any number offered as such is invented — refuse
  to state one.
- **Benford's-law digit analysis on star ratings.** Not established. The one study located examined
  **word-count** distributions of review *text*, not star values, and even there found word counts do
  not generally obey Benford's law, with conformance weaker in emerging markets. Do not apply digit
  analysis to a star rating.
- **"More reviews always means harder to fake, so trust it more."** Directionally reasonable but not
  unconditional — purchased-review campaigns specifically target already-successful, high-review-count
  listings too (see `fraud-signals.md`), and volume alone says nothing about the distribution shape.
