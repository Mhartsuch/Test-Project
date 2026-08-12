#!/usr/bin/env python3
"""Calibrate the Riemann-Siegel truncation constants K_J used by
rs_trunc_bound() in src/rs.c.

    sup_p |Z(t) - RS_J(t)| <= K_J * tau^{-(2J+3)/2},   tau = sqrt(t/2pi)

Measures the observed supremum against mpmath over a range of heights.  The
values shipped in rs.c carry a safety factor of ~100 over what this prints.
See docs/RIGOR.md for why this is tier-C (calibrated, not proved) and why the
result is insensitive at the heights that matter.

Usage:  python3 scripts/calibrate_rs.py [n_samples]
"""
import sys, random
from mpmath import mp, mpf, pi, log, sqrt, cos, floor, siegeltheta, siegelz, diff

mp.dps = 30

def Psi(p):
    return cos(2*pi*(p*p - p - mpf(1)/16)) / cos(2*pi*p)

def C(j, p):
    d = lambda n: diff(Psi, p, n)
    return [Psi(p),
            -d(3)/(96*pi**2),
            d(6)/(18432*pi**4) + d(2)/(64*pi**2),
            -d(9)/(5308416*pi**6) - d(5)/(3840*pi**4) - d(1)/(64*pi**2)][j]

def RS(t, J):
    t = mpf(t)
    tau = sqrt(t/(2*pi)); N = int(floor(tau)); p = tau - N
    th = siegeltheta(t)
    s = 2*sum(cos(th - t*log(k))/sqrt(mpf(k)) for k in range(1, N+1))
    return s + (-1)**(N-1) * tau**mpf(-0.5) * sum(C(j, p)/tau**j for j in range(J+1))

def main():
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 105
    random.seed(7)
    ts = []
    for lo, hi, k in [(100, 1000, n*4//10), (1000, 20000, n*4//10),
                      (20000, 200000, n - 2*(n*4//10))]:
        ts += [lo + (hi-lo)*random.random() for _ in range(k)]
    best = {0: 0, 1: 0, 2: 0, 3: 0}
    for i, t in enumerate(ts):
        ex = siegelz(mpf(t)); tau = sqrt(mpf(t)/(2*pi))
        for J in range(4):
            r = abs(RS(t, J) - ex) / tau**mpf(-(2*J+3)/2.0)
            best[J] = max(best[J], r)
        if (i+1) % 20 == 0:
            print(f"  ... {i+1}/{len(ts)}", file=sys.stderr)
    print(f"heights sampled: {len(ts)} in [100, 2e5]")
    for J in range(4):
        print(f"J={J}: observed sup |Z-RS_J| / tau^-((2J+3)/2) = {float(best[J]):.4g}"
              f"   (rs.c uses {[3.0,0.6,0.05,0.05][J]})")

if __name__ == "__main__":
    main()
