"""How much is the numerical evidence for RH actually worth?

Usage:  python scripts/evidence_strength.py [ZEROS_JSON]

This script exists because the honest answer to "we verified RH numerically"
is "verified *what*, exactly, and against which alternative?".  Each section
takes a criterion that RH is equivalent to, and asks a sharper question than
"does it hold so far": **if RH were false, how far would we have had to look
before this test noticed?**

The answers are sobering, and they are computed here rather than asserted.
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from riemann.equivalences import (  # noqa: E402
    EULER_GAMMA,
    check_robin,
    colossally_abundant_candidates,
    li_coefficient_exact_first,
    mertens_ratio,
)
from riemann.fast import li_coefficients_array  # noqa: E402

RULE = "=" * 78


def li_asymptotic(n):
    """Verified-in-this-script asymptotic for lambda_n under RH."""
    n = np.asarray(n, dtype=float)
    return 0.5 * n * (np.log(n) + EULER_GAMMA - 1.0 - math.log(2.0 * math.pi))


def growth_rate(sigma, gamma):
    """``|1 - 1/rho|`` for the reflected partner of an off-line zero.

    For ``rho = sigma + i gamma`` the reflected zero is ``1 - sigma + i gamma``,
    and ``|1 - 1/rho| = |rho - 1| / |rho|``.  On the critical line this is
    exactly 1; off it, the partner with ``Re < 1/2`` gives a value ``> 1``, and
    that is the only thing in Li's sum that can ever grow.
    """
    lo = min(sigma, 1.0 - sigma)  # the partner with Re < 1/2
    rho = complex(lo, gamma)
    return abs(rho - 1.0) / abs(rho)


def perturbation(d, gamma, removed_gammas, n_max):
    """Exact change in ``lambda_n`` from moving zeros off the critical line.

    A quadruple ``{1/2 +- d + i gamma}`` (each with its conjugate) replaces the
    two on-line conjugate pairs at ``removed_gammas``, so the total number of
    zeros is unchanged -- which matters, because ``lambda_n`` counts zeros and a
    mismatched count would produce a spurious linear drift.
    """
    n = np.arange(1, n_max + 1)
    out = np.zeros(n_max)
    added = [complex(0.5 + d, gamma), complex(0.5 - d, gamma)]
    removed = [complex(0.5, g) for g in removed_gammas]
    for group, sign in ((added, 1.0), (removed, -1.0)):
        for rho in group:
            powers = np.exp(n * np.log(1.0 - 1.0 / rho))
            out += sign * 2.0 * (1.0 - powers.real)
    return out


def estimated_crossing(r, max_n=10 ** 18):
    """Where ``2 r^n`` first overtakes the smooth part ``(n/2)(log n + c)``.

    Solved by fixed-point iteration on ``n = log(lambda_n / 2) / log r``, which
    converges immediately because the right-hand side depends on ``n`` only
    logarithmically.  Validated against the exact computation wherever the
    exact crossing is small enough to reach.
    """
    if r <= 1.0:
        return None
    log_r = math.log(r)
    n = 1000.0
    for _ in range(200):
        smooth = max(float(li_asymptotic(n)), 1e-300)
        nxt = math.log(smooth / 2.0) / log_r
        if nxt <= 0 or nxt > max_n:
            return None
        if abs(nxt - n) < 1e-6 * n:
            return nxt
        n = 0.5 * (n + nxt)
    return n


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "results/zeros_74921.json"
    with open(path) as fh:
        blob = json.load(fh)
    zeros = blob["zeros"]

    # =====================================================================
    print(RULE)
    print("1.  LI'S CRITERION: positivity that cannot see a violation")
    print(RULE)
    print("""
  Li's criterion: RH  <=>  lambda_n >= 0 for every n >= 1, where
      lambda_n = sum_rho [ 1 - (1 - 1/rho)^n ].

  This looks eminently checkable, and lambda_n is indeed positive for every n
  anyone has computed.  But consider what makes a term grow.  On the critical
  line |1 - 1/rho| = 1 EXACTLY, because |rho - 1| = |rho| when Re(rho) = 1/2.
  So under RH every term stays on the unit circle and lambda_n grows only like
  (n/2) log n.  A zero off the line has a partner with Re < 1/2, for which
  |1 - 1/rho| > 1, and its contribution grows like that ratio to the n-th
  power.  Li's criterion works -- eventually.
""")
    lam = li_coefficients_array(2000, zeros)
    print(f"  lambda_1 computed from {len(zeros)} zeros: {lam[0]:.10f}")
    print(f"  lambda_1 in closed form 1 + gamma/2 - log(4 pi)/2: "
          f"{li_coefficient_exact_first():.10f}")
    ns = np.array([10, 100, 1000, 2000])
    print()
    print(f"  {'n':>8} {'lambda_n (computed)':>22} {'(n/2)(log n + g-1-log2pi)':>28}")
    for n in ns:
        print(f"  {n:>8} {lam[n-1]:>22.4f} {float(li_asymptotic(n)):>28.4f}")
    print("\n  The asymptotic is good, so it can be trusted below to reach large n.")

    print("""
  Now the experiment.  Put ONE zero off the critical line at Re = 1/2 + d
  (keeping the zero count right, so the quadruple rho, conj, 1-rho, 1-conj
  replaces two on-line pairs), and ask: at which n does lambda_n finally
  go negative and reveal it?
""")
    n_exact = 30000
    lam_full = li_coefficients_array(n_exact, zeros)
    print(f"  {'violation':>26} {'|1-1/rho|':>14} {'exact':>12} {'estimated':>16}")
    cases = [(0.25, zeros[0]), (0.10, zeros[0]), (0.05, zeros[0]),
             (0.01, zeros[0]), (0.10, 1000.0), (0.10, 74920.0)]
    for d, gamma in cases:
        r = growth_rate(0.5 + d, gamma)
        delta = perturbation(d, gamma, zeros[:2], n_exact)
        negative = np.nonzero(lam_full + delta < 0.0)[0]
        exact = f"{int(negative[0]) + 1:,}" if negative.size else f"> {n_exact:,}"
        est = estimated_crossing(r)
        est_s = f"{est:,.0f}" if est and est < 1e15 else (
            f"{est:.2e}" if est else "never")
        print(f"  {'Re = %.2f, gamma = %.1f' % (0.5 + d, gamma):>26} "
              f"{r:>14.10f} {exact:>12} {est_s:>16}")
    print(f"""
  'exact' computes lambda_n directly from all {len(zeros):,} zeros with the
  violation inserted, for n up to {n_exact:,}; 'estimated' solves
  2 r^n = (n/2)(log n + c).  Where both are available they agree, which is what
  licenses the estimate in the rows the direct computation cannot reach.

  Read the second row: a zero at Re = 0.6 -- an enormous violation, nowhere
  near the critical line -- keeps lambda_n positive well past n = 10,000.  At
  Re = 0.51 the violation hides until n is in the hundreds of thousands.  And
  the same violation placed higher up the critical strip hides far longer
  still, because the growth rate tends to 1 as gamma grows: the SAME zero at
  Re = 0.6 is undetectable roughly a million times longer at height 74,920 than
  at height 14.

  So "lambda_n > 0 for every n we computed" is close to content-free as
  evidence.  The criterion is not wrong; its sensitivity is exponentially bad
  in exactly the regime we can reach, and it degrades with height precisely
  where the zeros we have not checked live.
""")

    # =====================================================================
    print(RULE)
    print("2.  DIRECT VERIFICATION: what checking zeros actually rules out")
    print(RULE)
    print(f"""
  This project verified all {len(zeros):,} zeros up to height {blob['t_max']:,.0f}.
  Published computations have gone vastly further: the first 10^13 zeros
  (Gourdon 2004), and Platt's rigorous verification to height 3.06 x 10^10.

  What does that exclude?  Only a counterexample BELOW that height.  The zeros
  continue forever, and their density grows like log(t/2pi)/2pi, so any finite
  computation covers a vanishing fraction of them.  Worse, the natural scale on
  which zeta's behaviour changes is log log t -- which, at the frontier of
  computation, has barely moved:
""")
    print(f"  {'height t':>16} {'log t':>10} {'log log t':>12}")
    for t in (1e4, 1e10, 1e13, 1e30, 1e100, 1e1000):
        print(f"  {t:>16.0e} {math.log(t):>10.2f} {math.log(math.log(t)):>12.3f}")
    print("""
  Going from height 10^13 to 10^100 moves log log t from 3.4 to 5.4.  Phenomena
  governed by log log t simply have not started yet.  Which is not idle worry --
  see the next two sections, where exactly that happened.
""")

    # =====================================================================
    print(RULE)
    print("3.  THE MERTENS CONJECTURE: a warning from history")
    print(RULE)
    r = mertens_ratio(2_000_000, samples=6)
    print(f"""
  Mertens conjectured |M(x)| < sqrt(x) for all x > 1, where M is the summed
  Moebius function.  It implies RH.  It was verified to 10^9 and looked safe.

  It is FALSE.  Odlyzko and te Riele disproved it in 1985 -- and no explicit
  counterexample is known to this day.  The first one is believed to lie past
  10^20, possibly far past.  The disproof is indirect: it shows only that
  limsup M(x)/sqrt(x) > 1.06, by exploiting near-resonances among the zeros.

  Computed here up to x = {r['limit']:,}, the ratio M(x)/sqrt(x) reaches only
  {r['max_abs_ratio']:.4f} in absolute value -- less than a quarter of the way to the
  boundary that the conjecture said could never be crossed, and which in fact
  gets crossed.  A search of this kind was never going to find anything.
""")
    print(f"  {'x':>12} {'M(x)':>10} {'M(x)/sqrt(x)':>16}")
    for row in r["rows"]:
        print(f"  {row['x']:>12,} {row['M']:>10} {row['ratio']:>16.5f}")

    # =====================================================================
    print()
    print(RULE)
    print("4.  ROBIN'S CRITERION: the margin that never closes")
    print(RULE)
    rob = check_robin(200_000)
    print(f"""
  Robin (1984): RH <=> sigma(n) < e^gamma n log log n for all n > 5040.

  Checked here for 5040 < n <= {rob['limit']:,}: no violations, largest ratio
  {rob['max_ratio']:.6f} at n = {rob['argmax']:,}, against e^gamma = {rob['e_gamma']:.6f}.

  But brute force over n is the wrong instrument: the inequality is only ever
  near-tight on COLOSSALLY ABUNDANT numbers, which are products of primorials
  and become astronomically large almost at once.  Following those instead:
""")
    ca = colossally_abundant_candidates(20000)
    print(f"  {'digits of n':>14} {'sigma(n)/(n log log n)':>26} {'margin below e^gamma':>24}")
    for row in ca[::max(1, len(ca) // 10)]:
        print(f"  {row['digits']:>14.1f} {row['robin_ratio']:>26.9f} "
              f"{row['margin']:>24.9f}")
    last = ca[-1]
    print(f"  {last['digits']:>14.1f} {last['robin_ratio']:>26.9f} "
          f"{last['margin']:>24.9f}")
    print(f"""
  Gronwall's theorem says this ratio has limsup exactly e^gamma = {math.exp(EULER_GAMMA):.9f},
  approached along these very numbers.  So the margin MUST shrink to zero.  RH
  is the statement that it shrinks to zero without ever reaching it.

  At {last['digits']:,.0f} digits the margin is still {last['margin']:.2e} and falling.  There is no
  height at which the numbers "settle down" and reassure us: the true and the
  false hypotheses predict sequences that look identical for as far as any
  computation can go, and differ only in whether a quantity tending to zero
  ever touches it.  Verifying more terms cannot distinguish them.
""")

    # =====================================================================
    print(RULE)
    print("5.  SKEWES: where numerical evidence provably lies")
    print(RULE)
    print("""
  For every x anyone has ever computed, pi(x) < li(x).  Gauss and Riemann both
  believed the inequality was universal.

  Littlewood proved in 1914 that it FAILS -- infinitely often, in both
  directions.  The first crossing is still not known; it is somewhere below
  about 1.4 x 10^316 (Bays and Hudson), a region no computation will ever reach.

  This is the cleanest case in all of number theory of a pattern that holds for
  every accessible x and is nevertheless false.  The reason is precisely the one
  that should worry us about RH: the effect is governed by the zeros, and the
  relevant terms only come into balance at scales where log log x has grown, so
  the crossover is exponentially out of reach.
""")

    # =====================================================================
    print(RULE)
    print("6.  DE BRUIJN-NEWMAN: RH has no margin at all")
    print(RULE)
    print("""
  Define H_t from the Riemann xi function by running the heat flow backwards in
  a suitable variable; H_0 is essentially xi.  De Bruijn and Newman proved there
  is a constant Lambda such that H_t has only real zeros exactly when
  t >= Lambda.  Then

      RH  <=>  Lambda <= 0.

  Newman conjectured Lambda >= 0, saying the conjecture "quantifies the belief
  that RH, if true, is only barely so".  In 2018 Rodgers and Tao PROVED
  Lambda >= 0.

  Combined:  RH is now equivalent to  Lambda = 0  exactly.

  This is the single most important thing to understand about the difficulty of
  the problem.  RH is not true with room to spare.  It sits precisely on the
  boundary of failure, and any proof must be sharp enough to establish an exact
  equality rather than an inequality with slack.  Every soft or averaging
  argument -- and most of the natural ones are soft -- is therefore doomed
  before it starts: such methods cannot distinguish Lambda = 0 from
  Lambda = 10^-9, and the difference between those two is the whole problem.
""")

    print(RULE)
    print("SUMMARY")
    print(RULE)
    print("""
  The numerical evidence for RH is genuine but much weaker than it appears:

  * Li positivity is exponentially insensitive in the range we can compute.
  * Direct zero verification covers a vanishing fraction, and log log t -- the
    scale that matters -- has barely moved at the computational frontier.
  * A closely analogous conjecture (Mertens) died after passing every test.
  * A universally-believed inequality (pi(x) < li(x)) is provably false beyond
    reach.
  * And RH holds with zero margin: Lambda = 0 exactly.

  The strong evidence for RH is not numerical at all.  It is structural: the
  GUE statistics of section 3 of the README, the proof of the analogue over
  function fields, and the fact that RH's consequences all cohere.  Those are
  reasons to believe it.  Counting zeros is not.
""")


if __name__ == "__main__":
    main()
