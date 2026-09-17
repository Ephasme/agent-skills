#!/usr/bin/env python3
"""Rating-bounds: compute honest lower bounds on a rating, not a naive mean.

Requires python3 (stdlib only, no third-party import) — see
references/rating-forensics.md for the same formulas done by hand when
python3 is unavailable.

Three independent computations, each usable on its own:

1. Dirichlet-multinomial credible-interval lower bound for a K-star histogram
   (--hist). This is the correct analogue of Wilson's bound for star data —
   Wilson's own formula does NOT apply to a star mean (see the Dead-ends
   section of references/rating-forensics.md). Source: Evan Miller, "Ranking
   Items With Star Ratings: An Approximate Bayesian Approach" (2014-09-16),
   https://www.evanmiller.org/ranking-items-with-star-ratings.html

   With N = sum(n_k), K = number of star levels, s_k = k:

     S = sum_k s_k*(n_k+1)/(N+K)
         - z * sqrt( ( sum_k s_k^2*(n_k+1)/(N+K)
                        - ( sum_k s_k*(n_k+1)/(N+K) )^2 ) / (N+K+1) )

2. Wilson score interval lower bound for a binary (positive, n) signal
   (--binary). Source: Wilson (1927), popularised by Evan Miller (2009).
   Binary data only — do not pass a star mean here.

3. Bayesian / IMDb-style shrinkage average toward a category prior
   (--prior mean,strength), using IMDb's own published form:
     WR = (v/(v+m))*R + (m/(v+m))*C
   where R is the item's own raw mean, v its own vote count, m the prior
   strength, C the prior mean. Source: IMDb's own ratings FAQ (updated
   2026-02-09), https://help.imdb.com/article/imdb/track-movies-tv/ratings-faq/G67Y87TFYYP6TWAV
   — current m = 25,000; the widely copied m = 1,300 is stale.

Self-test: run with --selftest to reproduce the two worked examples from
research-b F3 (Dirichlet bound) and F2 (Wilson ranking), using a numeric
tolerance rather than string comparison (float formatting differs across
interpreter versions).

Usage:
  python3 rating-bounds.py --hist n1,n2,n3,n4,n5 [--z 1.96]
  python3 rating-bounds.py --binary positive,n [--z 1.96]
  python3 rating-bounds.py --hist n1,n2,n3,n4,n5 --prior mean,strength
  python3 rating-bounds.py --selftest
"""

import argparse
import math
import sys


def dirichlet_lower_bound(hist, z=1.96):
    """Dirichlet-multinomial credible-interval lower bound for a K-star
    histogram. `hist` is a sequence of counts for star levels 1..K, in
    order (hist[0] = count of 1-star ratings, ..., hist[-1] = count of
    K-star ratings). Returns (raw_mean, shrunk_mean, variance, lower_bound).
    """
    k_levels = len(hist)
    n_total = sum(hist)
    if n_total == 0:
        raise ValueError("histogram is empty (n=0)")
    denom = n_total + k_levels

    raw_mean = sum((k + 1) * count for k, count in enumerate(hist)) / n_total

    e_s = sum((k + 1) * (count + 1) for k, count in enumerate(hist)) / denom
    e_s2 = sum(((k + 1) ** 2) * (count + 1) for k, count in enumerate(hist)) / denom
    variance = (e_s2 - e_s ** 2) / (denom + 1)
    lower = e_s - z * math.sqrt(variance)
    return raw_mean, e_s, variance, lower


def wilson_lower_bound(positive, n, z=1.96):
    """Wilson score interval lower bound for a binary (positive, n) signal.
    Binary data only — never pass a star-rating mean here."""
    if n == 0:
        raise ValueError("n=0")
    p_hat = positive / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p_hat + z2 / (2 * n)) / denom
    adj = z * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) / denom
    return center - adj


def shrinkage_average(item_mean, item_n, prior_mean, prior_strength):
    """IMDb-form Bayesian shrinkage: WR = (v/(v+m))*R + (m/(v+m))*C."""
    v, m = item_n, prior_strength
    return (v / (v + m)) * item_mean + (m / (v + m)) * prior_mean


def _parse_counts(text, expect_len=None):
    parts = [int(x.strip()) for x in text.split(",")]
    if expect_len is not None and len(parts) != expect_len:
        raise ValueError(f"expected {expect_len} comma-separated values, got {len(parts)}")
    return parts


def run_selftest():
    """Reproduce research-b F3 (Dirichlet) and F2 (Wilson ranking) to a
    numeric tolerance. Exits non-zero on any mismatch."""
    tolerance = 5e-4
    failures = []

    # F3, Item A: n=23, histogram (1..5 star) = 0,0,0,2,21
    _, _, _, bound_a = dirichlet_lower_bound([0, 0, 0, 2, 21], z=1.96)
    if abs(bound_a - 4.215) > tolerance:
        failures.append(f"Item A lower bound: got {bound_a:.4f}, want 4.215 (+/-{tolerance})")

    # F3, Item B: n=4100, histogram (1..5 star) = 82,123,246,779,2870
    _, _, _, bound_b = dirichlet_lower_bound([82, 123, 246, 779, 2870], z=1.96)
    if abs(bound_b - 4.491) > tolerance:
        failures.append(f"Item B lower bound: got {bound_b:.4f}, want 4.491 (+/-{tolerance})")

    if not (bound_b > bound_a):
        failures.append(
            f"naive-ranking reversal not reproduced: bound_b={bound_b:.4f} should exceed "
            f"bound_a={bound_a:.4f} despite A's higher raw mean"
        )

    # F2: 2-of-2 vs 100-of-101 — the smaller, perfect sample must NOT outrank
    # the larger, near-perfect one once uncertainty is accounted for.
    small_perfect = wilson_lower_bound(2, 2, z=1.96)
    large_near_perfect = wilson_lower_bound(100, 101, z=1.96)
    if not (large_near_perfect > small_perfect):
        failures.append(
            f"Wilson ranking not reproduced: 100/101 bound={large_near_perfect:.4f} should "
            f"exceed 2/2 bound={small_perfect:.4f}"
        )

    if failures:
        print("SELFTEST FAILED:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        sys.exit(1)

    print("SELFTEST PASSED")
    print(f"  Item A (n=23):    raw mean 4.913, lower bound {bound_a:.3f} (want 4.215)")
    print(f"  Item B (n=4,100): raw mean 4.520, lower bound {bound_b:.3f} (want 4.491)")
    print(f"  2-of-2 Wilson lower bound:     {small_perfect:.4f}")
    print(f"  100-of-101 Wilson lower bound: {large_near_perfect:.4f} (ranks higher, correctly)")


def main():
    parser = argparse.ArgumentParser(
        description="Compute honest rating lower bounds (Dirichlet, Wilson, shrinkage). "
        "Requires python3 stdlib only.",
    )
    parser.add_argument(
        "--hist",
        help="comma-separated star-histogram counts, 1-star first (e.g. 82,123,246,779,2870)",
    )
    parser.add_argument(
        "--binary",
        help="comma-separated positive,n for a binary signal (e.g. 100,101)",
    )
    parser.add_argument(
        "--prior",
        help="comma-separated mean,strength for Bayesian shrinkage (e.g. 4.2,25000); "
        "requires --hist or --binary to supply the item's own mean and n",
    )
    parser.add_argument("--z", type=float, default=1.96, help="one-sided z (default 1.96 = 95%%)")
    parser.add_argument("--selftest", action="store_true", help="run the pinned regression checks")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return

    if not args.hist and not args.binary:
        parser.error("supply --hist, --binary, or --selftest")

    item_mean = None
    item_n = None

    if args.hist:
        hist = _parse_counts(args.hist)
        raw_mean, shrunk_mean, variance, lower = dirichlet_lower_bound(hist, z=args.z)
        n_total = sum(hist)
        print(f"Dirichlet-multinomial bound (n={n_total}, z={args.z}):")
        print(f"  raw mean:          {raw_mean:.4f}")
        print(f"  shrunk mean:       {shrunk_mean:.4f}")
        print(f"  variance:          {variance:.6f}")
        print(f"  lower bound:       {lower:.2f}   <-- rank/compare on this, not the raw mean")
        item_mean, item_n = raw_mean, n_total

    if args.binary:
        positive, n = _parse_counts(args.binary, expect_len=2)
        lower = wilson_lower_bound(positive, n, z=args.z)
        print(f"Wilson score lower bound (positive={positive}, n={n}, z={args.z}):")
        print(f"  p_hat:             {positive / n:.4f}")
        print(f"  lower bound:       {lower:.4f}   <-- rank/compare on this, not the raw fraction")
        item_mean, item_n = positive / n, n

    if args.prior:
        if item_mean is None:
            parser.error("--prior requires --hist or --binary to supply the item's own mean and n")
        prior_mean, prior_strength = (float(x) for x in args.prior.split(","))
        wr = shrinkage_average(item_mean, item_n, prior_mean, prior_strength)
        print(f"IMDb-form shrinkage (prior mean={prior_mean}, strength={prior_strength}):")
        print(f"  WR = (v/(v+m))*R + (m/(v+m))*C = {wr:.4f}")


if __name__ == "__main__":
    main()
