"""Montgomery-Odlyzko: compare zero statistics against random matrix theory.

Usage:  python scripts/gue_statistics.py [ZEROS_JSON]
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann.statistics import (  # noqa: E402
    ascii_histogram,
    pair_correlation_histogram,
    spacing_histogram,
    spacing_moments,
    unfold,
)
from riemann.zeros import lehmer_pairs  # noqa: E402


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "results/zeros_74921.json"
    with open(path) as fh:
        data = json.load(fh)
    zeros = data["zeros"]
    print(f"{len(zeros)} zeros up to t = {data['t_max']:g}")
    print(f"complete (verified against argument principle): {data['complete']}")
    print()

    w = unfold(zeros)

    # ---- nearest-neighbour spacings -------------------------------------
    hist = spacing_histogram(w, bins=40, s_max=3.0, already_unfolded=True)
    print("=" * 78)
    print("NEAREST-NEIGHBOUR SPACING DENSITY")
    print("=" * 78)
    print("  'o' = observed zeta zeros    'g' = GUE (Wigner surmise)    "
          "'p' = Poisson (no repulsion)")
    print()
    print(ascii_histogram(
        hist["centres"],
        {"o": hist["observed"], "g": hist["gue"], "p": hist["poisson"]},
    ))
    print()
    print("  The observed curve tracks GUE, not Poisson.  Near s = 0 the")
    print("  Poisson density is 1 while both GUE and the zeros go to 0 like s^2:")
    print("  the zeros REPEL each other.  That is the signature of eigenvalues")
    print("  of a random Hermitian matrix, not of an arbitrary increasing")
    print("  sequence with the right density.")
    print()

    err_gue = sum(abs(a - b) for a, b in zip(hist["observed"], hist["gue"]))
    err_poi = sum(abs(a - b) for a, b in zip(hist["observed"], hist["poisson"]))
    print(f"  total absolute deviation from GUE:     {err_gue * hist['bin_width']:.5f}")
    print(f"  total absolute deviation from Poisson: {err_poi * hist['bin_width']:.5f}")
    print(f"  GUE fits better by a factor of {err_poi / err_gue:.1f}")
    print()

    # ---- moments ---------------------------------------------------------
    mom = spacing_moments(w, already_unfolded=True)
    print("=" * 78)
    print("SPACING MOMENTS")
    print("=" * 78)
    print(f"{'moment':>8} {'observed':>14} {'GUE':>14} {'Poisson':>14}")
    for k in (1, 2, 3, 4):
        print(f"{'<s^%d>' % k:>8} {mom['observed'][k]:14.6f} "
              f"{mom['gue'][k]:14.6f} {mom['poisson'][k]:14.6f}")
    print(f"{'var':>8} {mom['variance_observed']:14.6f} "
          f"{mom['variance_gue']:14.6f} {1.0:14.6f}")
    print()

    # ---- pair correlation ------------------------------------------------
    pc = pair_correlation_histogram(w, bins=40, r_max=3.0, already_unfolded=True)
    print("=" * 78)
    print("PAIR CORRELATION   (Montgomery 1972 / Dyson)")
    print("=" * 78)
    print("  'o' = observed    'g' = 1 - (sin(pi r)/(pi r))^2")
    print()
    print(ascii_histogram(pc["centres"], {"o": pc["observed"], "g": pc["gue"]}))
    print()
    dev = sum(abs(a - b) for a, b in zip(pc["observed"], pc["gue"])) / len(pc["gue"])
    print(f"  mean absolute deviation from the Montgomery-Dyson form: {dev:.5f}")
    print()

    # ---- close pairs -----------------------------------------------------
    lp = lehmer_pairs(zeros, 0.05)
    print("=" * 78)
    print("CLOSEST PAIRS (Lehmer phenomenon)")
    print("=" * 78)
    print("  Close pairs are where a counterexample to RH would have to begin:")
    print("  for two zeros to leave the critical line they must first collide.")
    print()
    for d in sorted(lp, key=lambda d: d["normalised_gap"])[:10]:
        print(f"    t = {d['t_lo']:.6f} .. {d['t_hi']:.6f}   "
              f"normalised gap {d['normalised_gap']:.5f}")
    print()

    out = "results/gue_statistics.json"
    with open(out, "w") as fh:
        json.dump({"spacing": hist, "pair_correlation": pc, "moments": mom,
                   "n_zeros": len(zeros), "t_max": data["t_max"]}, fh)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
