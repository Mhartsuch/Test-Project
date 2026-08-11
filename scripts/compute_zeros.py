"""Compute and cache zero ordinates.

Usage:  python scripts/compute_zeros.py [T_MAX] [OUTFILE]

Every run re-verifies the tally against the argument-principle count, so a
cache file that exists is a cache file whose contents are complete: for the
range it covers, the zeros listed are *all* the zeros of zeta in the strip.
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from riemann.counting import N  # noqa: E402
from riemann.zeros import find_zeros, normalised_gaps  # noqa: E402


def main() -> None:
    t_max = float(sys.argv[1]) if len(sys.argv) > 1 else 10000.0
    out = sys.argv[2] if len(sys.argv) > 2 else f"results/zeros_{int(t_max)}.json"

    print(f"computing zeros of zeta(1/2 + it) for 14 < t <= {t_max:g}")
    expected, residual = N(t_max)
    print(f"argument principle: N({t_max:g}) = {expected}  (residual {residual:.1e})")

    start = time.time()
    zeros = find_zeros(14.0, t_max, verbose=True)
    elapsed = time.time() - start

    gaps = normalised_gaps(zeros)
    print(f"found {len(zeros)} zeros in {elapsed:.1f}s")
    print(f"all accounted for: {len(zeros) == expected}")
    print(f"mean normalised gap: {sum(gaps)/len(gaps):.8f}  (exact value should tend to 1)")
    print(f"min normalised gap:  {min(gaps):.6f}")

    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w") as fh:
        json.dump(
            {
                "t_max": t_max,
                "count": len(zeros),
                "expected_from_argument_principle": expected,
                "complete": len(zeros) == expected,
                "seconds": elapsed,
                "zeros": zeros,
            },
            fh,
        )
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
