"""Statistics of the zeros: the Montgomery-Odlyzko phenomenon.

This module computes the single most striking *empirical* fact about the zeta
zeros, and the one piece of evidence for RH that is genuinely structural rather
than merely numerical.

The story
---------
In 1972 Hugh Montgomery, studying the pair correlation of zeta zeros, proved
(assuming RH, and for a restricted range of test functions) that the correlation
between normalised zero heights behaves like

.. math::  R_2(r) = 1 - \\left(\\frac{\\sin \\pi r}{\\pi r}\\right)^2.

Over tea at the Institute for Advanced Study he mentioned the formula to Freeman
Dyson, who recognised it immediately: it is the pair correlation function of
eigenvalues of a large random Hermitian matrix -- the Gaussian Unitary Ensemble.
Odlyzko later computed billions of zeros near height ``10^{20}`` and found the
agreement essentially perfect.

Why it matters
--------------
Zeros of ``zeta`` *repel* each other.  For independent random points (a Poisson
process) the density of nearest-neighbour spacings at ``s = 0`` is ``1``: points
happily coincide.  For GUE eigenvalues the density vanishes like ``s^2``.  The
zeta zeros do the latter.  That is very hard to explain unless the ordinates are
eigenvalues of *something* self-adjoint -- which is precisely the Hilbert-Polya
conjecture, and would give RH immediately.  See ``docs/02-failure-modes.md`` for
why nobody has been able to produce the operator.

Unfolding
---------
Zeros get denser with height, so raw spacings are not stationary and cannot be
compared to a fixed distribution.  The right normalisation is *not* the local
density approximation but the exact counting function: since
``N(t) = theta(t)/pi + 1 + S(t)`` with ``S`` small and mean zero,

.. math::  w_n = \\theta(\\gamma_n)/\\pi

has unit mean spacing by construction, with no error from treating the density
as locally constant.  :func:`unfold` uses this.
"""

from __future__ import annotations

import math

from .riemann_siegel import theta

__all__ = [
    "unfold",
    "spacings",
    "gue_spacing_density",
    "poisson_spacing_density",
    "gue_pair_correlation",
    "spacing_histogram",
    "pair_correlation_histogram",
    "spacing_moments",
    "ascii_histogram",
]


# ---------------------------------------------------------------------------
# unfolding
# ---------------------------------------------------------------------------

def unfold(zeros) -> list:
    """Map ordinates to a sequence of unit mean spacing via ``w = theta(t)/pi``."""
    return [theta(t) / math.pi for t in zeros]


def spacings(zeros, already_unfolded: bool = False) -> list:
    """Consecutive spacings of the unfolded ordinates (mean ``1``)."""
    w = zeros if already_unfolded else unfold(zeros)
    return [b - a for a, b in zip(w, w[1:])]


# ---------------------------------------------------------------------------
# the reference distributions
# ---------------------------------------------------------------------------

def gue_spacing_density(s: float) -> float:
    """Wigner surmise for the GUE nearest-neighbour spacing density.

    .. math::  p(s) = \\frac{32}{\\pi^2}\\,s^2 e^{-4s^2/\\pi}

    Normalised to unit mean.  This is the *surmise*, not the exact answer: the
    true GUE spacing density is a Fredholm determinant of the sine kernel,
    expressible via a Painleve V transcendent.  The surmise differs from it by
    well under one percent everywhere, which is far below the sampling noise of
    the zero counts used here, so the distinction is not material -- but it is
    real, and pretending otherwise would misrepresent what the agreement shows.
    """
    return (32.0 / math.pi ** 2) * s * s * math.exp(-4.0 * s * s / math.pi)


def poisson_spacing_density(s: float) -> float:
    """Spacing density ``e^{-s}`` for a Poisson process of unit intensity.

    Included as the null hypothesis.  If the zeros were "just some increasing
    sequence" with the right density, this is what the histogram would look
    like; the contrast at small ``s`` is the entire point.
    """
    return math.exp(-s)


def gue_pair_correlation(r: float) -> float:
    """Montgomery-Dyson pair correlation ``1 - (sin(pi r)/(pi r))^2``."""
    if r == 0.0:
        return 0.0
    x = math.pi * r
    return 1.0 - (math.sin(x) / x) ** 2


# ---------------------------------------------------------------------------
# empirical histograms
# ---------------------------------------------------------------------------

def spacing_histogram(zeros, bins: int = 50, s_max: float = 3.0,
                      already_unfolded: bool = False) -> dict:
    """Empirical nearest-neighbour spacing density, against GUE and Poisson."""
    s = spacings(zeros, already_unfolded)
    width = s_max / bins
    counts = [0] * bins
    for v in s:
        k = int(v / width)
        if 0 <= k < bins:
            counts[k] += 1
    n = len(s)
    centres, observed, gue, poisson = [], [], [], []
    for k in range(bins):
        c = (k + 0.5) * width
        centres.append(c)
        observed.append(counts[k] / (n * width))
        gue.append(gue_spacing_density(c))
        poisson.append(poisson_spacing_density(c))
    return {
        "centres": centres,
        "observed": observed,
        "gue": gue,
        "poisson": poisson,
        "counts": counts,
        "n_spacings": n,
        "bin_width": width,
    }


def pair_correlation_histogram(zeros, bins: int = 60, r_max: float = 3.0,
                               already_unfolded: bool = False) -> dict:
    """Empirical pair correlation of the unfolded ordinates.

    Counts all pairs (not just consecutive ones) whose unfolded separation lies
    in ``(0, r_max]``, normalised so that a Poisson process would give a flat
    density of ``1``.  Because the unfolded sequence is increasing, the inner
    loop can stop as soon as the separation exceeds ``r_max``, making this
    ``O(n * r_max)`` rather than ``O(n^2)``.
    """
    w = zeros if already_unfolded else unfold(zeros)
    n = len(w)
    width = r_max / bins
    counts = [0] * bins
    for i in range(n):
        wi = w[i]
        j = i + 1
        while j < n and w[j] - wi <= r_max:
            k = int((w[j] - wi) / width)
            if 0 <= k < bins:
                counts[k] += 1
            j += 1

    # A unit-density Poisson process on a window of length L contributes
    # (n-1) * width expected pairs per bin, counting each pair once.
    span = w[-1] - w[0]
    expected_per_bin = (n - 1) * (n / span) * width / 1.0
    centres, observed, gue = [], [], []
    for k in range(bins):
        c = (k + 0.5) * width
        centres.append(c)
        observed.append(counts[k] / expected_per_bin if expected_per_bin else 0.0)
        gue.append(gue_pair_correlation(c))
    return {
        "centres": centres,
        "observed": observed,
        "gue": gue,
        "counts": counts,
        "n_zeros": n,
        "bin_width": width,
    }


def spacing_moments(zeros, already_unfolded: bool = False) -> dict:
    """Moments of the spacing distribution against their GUE values.

    The GUE (Wigner surmise) moments are
    ``<s> = 1``, ``<s^2> = 3 pi / 8 = 1.1781``, ``<s^3> = pi^{3/2}/2 ... ``;
    they are computed here by quadrature rather than quoted, so the comparison
    does not depend on a remembered constant.
    """
    s = spacings(zeros, already_unfolded)
    n = len(s)
    obs = {k: sum(v ** k for v in s) / n for k in (1, 2, 3, 4)}

    # Numerically integrate the surmise for the reference moments.
    steps, upper = 200000, 12.0
    h = upper / steps
    ref = {k: 0.0 for k in (1, 2, 3, 4)}
    for i in range(steps):
        x = (i + 0.5) * h
        p = gue_spacing_density(x)
        for k in ref:
            ref[k] += x ** k * p * h

    poisson_ref = {1: 1.0, 2: 2.0, 3: 6.0, 4: 24.0}
    return {
        "n_spacings": n,
        "observed": obs,
        "gue": ref,
        "poisson": poisson_ref,
        "variance_observed": obs[2] - obs[1] ** 2,
        "variance_gue": ref[2] - ref[1] ** 2,
    }


# ---------------------------------------------------------------------------
# display
# ---------------------------------------------------------------------------

def ascii_histogram(centres, series: dict, width: int = 62, height_scale=None) -> str:
    """Render overlaid curves as text, so results are visible without plotting.

    ``series`` maps a one-character label to a list of values.
    """
    all_vals = [v for vals in series.values() for v in vals]
    top = height_scale or (max(all_vals) * 1.05 if all_vals else 1.0)
    lines = []
    for i, c in enumerate(centres):
        row = [" "] * width
        for label, vals in series.items():
            pos = int(vals[i] / top * (width - 1)) if top > 0 else 0
            pos = max(0, min(width - 1, pos))
            row[pos] = label if row[pos] == " " else "*"
        lines.append(f"{c:5.2f} |{''.join(row)}|")
    legend = "  ".join(f"'{k}'" for k in series)
    lines.append(f"      +{'-' * width}+   0 .. {top:.3f}   series: {legend}")
    return "\n".join(lines)
