"""Rebuild the prime-counting staircase from the zeros of zeta.

Usage:  python scripts/explicit_formula_demo.py [ZEROS_JSON]
"""

from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from riemann.explicit_formula import (  # noqa: E402
    psi_exact,
    psi_from_zeros,
    psi_from_zeros_array,
    von_mangoldt_sieve,
)


def staircase_plot(xs, exact, approx, width=68, height=26):
    lo = min(min(exact), min(approx))
    hi = max(max(exact), max(approx))
    span = hi - lo or 1.0
    grid = [[" "] * width for _ in range(height)]
    for i, x in enumerate(xs):
        col = int((x - xs[0]) / (xs[-1] - xs[0]) * (width - 1))
        for series, ch in ((exact, "#"), (approx, "o")):
            row = height - 1 - int((series[i] - lo) / span * (height - 1))
            row = max(0, min(height - 1, row))
            grid[row][col] = "*" if grid[row][col] not in (" ", ch) else ch
    out = [f"  psi(x) from {lo:.1f} to {hi:.1f}   '#' = true psi(x)   "
           f"'o' = rebuilt from zeros"]
    out += ["  |" + "".join(r) + "|" for r in grid]
    out.append(f"  +{'-' * width}+")
    out.append(f"   x = {xs[0]:.0f}{' ' * (width - 12)}x = {xs[-1]:.0f}")
    return "\n".join(out)


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "results/zeros_74921.json"
    with open(path) as fh:
        zeros = json.load(fh)["zeros"]

    x_max = 100
    xs = np.linspace(2.0, float(x_max), 700)
    exact_table = psi_exact(x_max + 1)
    exact = np.array([exact_table[int(math.floor(x))] for x in xs])

    print("=" * 78)
    print("THE EXPLICIT FORMULA: primes out of zeros")
    print("=" * 78)
    print("""
  psi(x) counts prime powers, weighted by log p.  Von Mangoldt's formula says
  it equals x, minus one wave per zero of zeta, minus two small constants:

      psi(x) = x - sum_rho x^rho/rho - log(2 pi) - (1/2) log(1 - x^-2)

  Each zero 1/2 + i*gamma contributes a wave of frequency gamma in log x and
  amplitude ~ sqrt(x)/gamma.  Adding more zeros sharpens the staircase.  The
  primes are the interference pattern of these waves.
""")

    for n_zeros in (10, 50, 500, 5000):
        approx = psi_from_zeros_array(xs, zeros[:n_zeros])
        rms = float(np.sqrt(np.mean((approx - exact) ** 2)))
        print()
        print(f"--- using the first {n_zeros} zeros "
              f"(gamma up to {zeros[n_zeros-1]:.1f}) --- RMS error {rms:.3f}")
        print(staircase_plot(xs.tolist(), exact.tolist(), approx.tolist()))

    # Where are the jumps?  Compare against prime powers.
    print()
    print("=" * 78)
    print("THE JUMPS LAND ON PRIME POWERS")
    print("=" * 78)
    lam = von_mangoldt_sieve(x_max)
    approx = psi_from_zeros_array(xs, zeros[:5000])
    d = np.diff(approx)
    peaks = np.argsort(d)[-12:]
    detected = sorted({int(round(xs[i])) for i in peaks})
    print(f"  steepest rises of the reconstruction: {detected}")
    print(f"  actual prime powers <= {x_max}:        "
          f"{[n for n in range(2, x_max + 1) if lam[n] > 0][:20]} ...")
    hits = [n for n in detected if lam[n] > 0 or lam[min(n + 1, x_max)] > 0]
    print(f"  of {len(detected)} detected jumps, {len(hits)} sit on a prime power")

    print()
    print("=" * 78)
    print("ERROR TERM AND WHY RH IS ABOUT ITS SIZE")
    print("=" * 78)
    print("""
  A zero at Re(rho) = sigma contributes an oscillation of size x^sigma.  So
  the size of psi(x) - x is decided entirely by how far right the zeros reach.
  RH says every sigma = 1/2, which is equivalent to

      psi(x) = x + O(x^{1/2} log^2 x)

  and this is the smallest error the oscillations could possibly permit -- a
  single zero off the line at sigma = 1/2 + d would force an error of size
  x^{1/2+d} infinitely often.  RH does not say the primes are random.  It says
  they are as regular as they can possibly be.
""")
    print(f"{'x':>8} {'psi(x)':>12} {'x':>12} {'psi(x)-x':>12} "
          f"{'(psi-x)/sqrt(x)':>18}")
    for x in (10, 100, 1000, 10000, 100000, 1000000):
        table = psi_exact(x)
        p = table[x]
        print(f"{x:>8} {p:12.3f} {float(x):12.3f} {p - x:12.3f} "
              f"{(p - x) / math.sqrt(x):18.4f}")
    print("""
  The last column stays small and shows no trend -- consistent with RH.  It is
  NOT evidence for RH in any strong sense: see docs/03-strength-of-evidence.md.
""")


if __name__ == "__main__":
    main()
