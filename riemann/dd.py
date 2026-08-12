"""Double-double arithmetic: ~32 significant digits out of pairs of float64.

Why this exists
---------------
The cost of Riemann-Siegel is not the obstruction to going high -- precision is.
Every term of the main sum is ``cos(theta(t) - t log n)``, and at ``t = 10^15``
the angle ``theta(t)`` is about ``1.6 x 10^16``.  A double carries 16 digits, so
the *integer part alone* exhausts the format: the fractional part of the angle,
which is the only part that matters, is gone before a single cosine is
evaluated.

:mod:`riemann.highprec` solved this at ``t = 10^10`` by reducing ``t0 log n``
modulo ``2 pi`` once per window with :mod:`mpmath`.  That works, but it puts a
third-party library inside the library rather than in the tests, and at
``t = 10^15`` there are 12.6 million values of ``n`` to reduce, which is far too
slow one number at a time.

A double-double -- an unevaluated sum ``hi + lo`` of two non-overlapping
doubles -- carries about 32 digits, is vectorisable, and needs no dependency
beyond numpy.  32 digits is exactly the right size: reducing ``t log n`` with
``t = 10^15`` costs 17 of them and leaves 15.

The primitives
--------------
All of this rests on two exact transformations, due to Knuth and Dekker:

* ``two_sum(a, b)`` returns ``(s, e)`` with ``s = fl(a + b)`` and ``a + b = s + e``
  *exactly*.  The rounding error of a floating-point addition is itself a
  floating-point number, and these six operations find it.
* ``two_prod(a, b)`` does the same for multiplication, by splitting each operand
  into two 26-bit halves (``2^27 + 1 = 134217729`` is the splitting constant) so
  that all four partial products are exact.

Neither is an approximation: they are identities of IEEE-754 arithmetic in
round-to-nearest.  They fail only if a fused multiply-add contracts the
expressions, which numpy does not do.

The logarithm
-------------
``log n`` is needed to 32 digits for every ``n`` up to ``sqrt(t / 2 pi)``.  It is
built from an exactly-representable table rather than from a Newton iteration:
write ``n = m 2^e`` with ``m in [1/2, 1)`` (that is ``frexp``, exact), pick the
nearest table point ``c = (4096 + i)/8192``, and use

.. math::  \\log n = e\\log 2 + \\log c + 2\\,\\operatorname{atanh}(z),
           \\qquad z = \\frac{m - c}{m + c}.

Two things make this cheap.  ``m - c`` is *exact* by Sterbenz' lemma (the two
are within a factor of two of each other), and ``|z| < 2^{-13}``, so the atanh
series needs only four terms to reach ``10^{-36}``.  The table of 4096 values of
``log c`` is generated once from :mod:`decimal` -- standard library, so the
package still has no third-party dependency outside numpy.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from functools import lru_cache

import numpy as np

__all__ = [
    "two_sum",
    "quick_two_sum",
    "two_prod",
    "add",
    "sub",
    "mul",
    "mul_d",
    "div",
    "sqr",
    "log",
    "mul_mod_2pi",
    "mul_mod_2pi_dd",
    "theta_mod_2pi",
    "theta_over_pi",
    "mean_gap",
    "to_float",
    "from_decimal",
    "pi_decimal",
    "theta_decimal",
    "PI",
    "TWO_PI",
    "LOG2",
    "EPS",
]

EPS = 2.0 ** -53          # unit roundoff for binary64
_SPLITTER = 134217729.0   # 2^27 + 1


# ---------------------------------------------------------------------------
# error-free transformations
# ---------------------------------------------------------------------------

def two_sum(a, b):
    """``(s, e)`` with ``s = fl(a+b)`` and ``a + b = s + e`` exactly."""
    s = a + b
    bb = s - a
    return s, (a - (s - bb)) + (b - bb)


def quick_two_sum(a, b):
    """As :func:`two_sum` but valid only when ``|a| >= |b|``; three ops instead of six."""
    s = a + b
    return s, b - (s - a)


def two_prod(a, b):
    """``(p, e)`` with ``p = fl(a*b)`` and ``a * b = p + e`` exactly (Dekker)."""
    p = a * b
    ca = _SPLITTER * a
    ah = ca - (ca - a)
    al = a - ah
    cb = _SPLITTER * b
    bh = cb - (cb - b)
    bl = b - bh
    return p, ((ah * bh - p) + ah * bl + al * bh) + al * bl


# ---------------------------------------------------------------------------
# double-double operations.  A dd number is a pair (hi, lo) of floats or of
# numpy arrays; the two are non-overlapping, so hi + lo carries ~106 bits.
# ---------------------------------------------------------------------------

def add(a, b):
    """Sum of two double-doubles."""
    s, e = two_sum(a[0], b[0])
    e = e + (a[1] + b[1])
    return quick_two_sum(s, e)


def sub(a, b):
    return add(a, (-b[0], -b[1]))


def add_d(a, b):
    """Double-double plus plain double."""
    s, e = two_sum(a[0], b)
    return quick_two_sum(s, e + a[1])


def mul(a, b):
    """Product of two double-doubles."""
    p, e = two_prod(a[0], b[0])
    e = e + (a[0] * b[1] + a[1] * b[0])
    return quick_two_sum(p, e)


def mul_d(a, b):
    """Double-double times plain double."""
    p, e = two_prod(a[0], b)
    e = e + a[1] * b
    return quick_two_sum(p, e)


def sqr(a):
    return mul(a, a)


def div(a, b):
    """Quotient of two double-doubles (one Newton correction on the quotient)."""
    q1 = a[0] / b[0]
    r = sub(a, mul_d(b, q1))
    q2 = r[0] / b[0]
    r = sub(r, mul_d(b, q2))
    q3 = r[0] / b[0]
    s, e = quick_two_sum(q1, q2)
    return quick_two_sum(s, e + q3)


def div_d(a, b):
    """Double-double divided by a plain double."""
    return div(a, (b, 0.0 * b))


def to_float(a):
    """Collapse a double-double to the nearest double."""
    return a[0] + a[1]


# ---------------------------------------------------------------------------
# high-precision constants, generated from the standard library
# ---------------------------------------------------------------------------

def pi_decimal(prec: int = 60) -> Decimal:
    """``pi`` to ``prec`` digits by the Chudnovsky-style series of the
    :mod:`decimal` documentation (Gosper's acceleration of Ramanujan's)."""
    with localcontext() as ctx:
        ctx.prec = prec + 10
        three = Decimal(3)
        lasts, t, s, n, na, d, da = Decimal(0), three, Decimal(3), 1, 0, 0, 24
        while s != lasts:
            lasts = s
            n, na = n + na, na + 8
            d, da = d + da, da + 32
            t = (t * n) / d
            s += t
    with localcontext() as ctx:
        ctx.prec = prec
        return +s


def from_decimal(d: Decimal):
    """Split a :class:`~decimal.Decimal` into a double-double ``(hi, lo)``."""
    hi = float(d)
    return hi, float(d - Decimal(hi))


@lru_cache(maxsize=1)
def _constants():
    with localcontext() as ctx:
        ctx.prec = 60
        pi = pi_decimal(60)
        return {
            "PI": from_decimal(pi),
            "TWO_PI": from_decimal(2 * pi),
            "LOG2": from_decimal(Decimal(2).ln()),
        }


class _LazyConst:
    """A double-double constant that materialises on first subscript."""

    def __init__(self, name):
        self._name = name

    def __getitem__(self, i):
        return _constants()[self._name][i]

    def __iter__(self):
        return iter(_constants()[self._name])

    def __repr__(self):  # pragma: no cover - debugging aid
        hi, lo = _constants()[self._name]
        return f"dd.{self._name}({hi!r} + {lo!r})"


PI = _LazyConst("PI")
TWO_PI = _LazyConst("TWO_PI")
LOG2 = _LazyConst("LOG2")


# ---------------------------------------------------------------------------
# logarithm
# ---------------------------------------------------------------------------

_TABLE_BITS = 12
_TABLE_N = 1 << _TABLE_BITS


@lru_cache(maxsize=1)
def _log_table():
    """``log c`` as a double-double for the 4096 points ``c = (4096+i)/8192``.

    Every ``c`` is an exact binary fraction, so ``m - c`` below is exact and the
    only inexactness in the reduction is the one division.
    """
    hi = np.empty(_TABLE_N, dtype=float)
    lo = np.empty(_TABLE_N, dtype=float)
    with localcontext() as ctx:
        ctx.prec = 50
        for i in range(_TABLE_N):
            value = (Decimal(_TABLE_N + i) / Decimal(2 * _TABLE_N)).ln()
            hi[i], lo[i] = from_decimal(value)
    return hi, lo


def _log_chunk(x):
    m, e = np.frexp(x)                       # x = m * 2^e, m in [0.5, 1), exact
    idx = ((m - 0.5) * (2 * _TABLE_N)).astype(np.int64)
    idx = np.clip(idx, 0, _TABLE_N - 1)
    c = (_TABLE_N + idx) / (2.0 * _TABLE_N)  # exact binary fraction

    num = m - c                              # exact: Sterbenz, since c <= m < 2c
    den = two_sum(m, c)

    # z = num / den, to ~32 digits.  One Newton correction suffices: num is
    # exact and |z| < 2^-13, so the series below only needs z to 28 digits.
    q1 = num / den[0]
    p, err = two_prod(q1, den[0])
    r = ((num - p) - err) - q1 * den[1]
    z = quick_two_sum(q1, r / den[0])

    u = sqr(z)
    # 2 atanh(z) = 2z (1 + u/3 + u^2/5 + u^3/7 + ...);  u < 1.5e-8, so from the
    # u^2 term onward plain doubles carry far more digits than are needed.
    tail = u[0] * u[0] * (0.2 + u[0] * (1.0 / 7.0))
    b = add_d(div_d(u, 3.0), tail)
    b = add_d(b, 1.0)
    series = mul((z[0] + z[0], z[1] + z[1]), b)   # doubling is exact

    table_hi, table_lo = _log_table()
    result = add(mul_d(_constants()["LOG2"], e.astype(float)),
                 (table_hi[idx], table_lo[idx]))
    return add(result, series)


def log(x, chunk: int = 1 << 20):
    """``log x`` as a double-double, for positive ``x`` (scalar or array).

    Accurate to about ``10^{-32}`` relative; :mod:`tests.test_dd` checks this
    against :mod:`decimal` at 45 digits.  Long inputs are processed in chunks so
    that the working set of the ten-odd temporaries stays in cache.
    """
    x = np.asarray(x, dtype=float)
    if np.any(x <= 0.0):
        raise ValueError("log requires strictly positive arguments")
    if x.ndim == 0 or x.size <= chunk:
        return _log_chunk(x)

    hi = np.empty(x.shape, dtype=float)
    lo = np.empty(x.shape, dtype=float)
    for start in range(0, x.size, chunk):
        piece = _log_chunk(x[start:start + chunk])
        hi[start:start + chunk] = piece[0]
        lo[start:start + chunk] = piece[1]
    return hi, lo


# ---------------------------------------------------------------------------
# the reduction that makes height 10^15 possible
# ---------------------------------------------------------------------------

def _mul_mod_2pi_chunk(t: float, x):
    """``(t * x) mod 2 pi`` as a *double-double*, for a double-double ``x``.

    Keeping the low word matters more than it looks.  The fast path evaluates
    ``exp(-i k x_n)`` for mode indices ``|k|`` up to a few thousand, and the
    rounding error of collapsing ``x_n`` to one double -- half an ulp of ``pi``,
    about ``2 x 10^{-16}`` -- is multiplied by ``k``.  At ``k = 4096`` that is
    ``10^{-12}`` per term and ``6 x 10^{-9}`` once summed against
    ``sum n^{-1/2} = 7100``, which would swamp everything.  The low word is what
    :func:`riemann.odlyzko_schonhage.nufft_type1` uses to correct it.
    """
    p = mul_d(x, float(t))
    two_pi = _constants()["TWO_PI"]
    q = np.round(p[0] / two_pi[0])
    if np.any(np.abs(q) >= 2.0 ** 53):
        raise ValueError("argument reduction would lose the integer quotient")
    return sub(p, mul_d(two_pi, q))


def mul_mod_2pi_dd(t: float, x, chunk: int = 1 << 18):
    """Chunked :func:`_mul_mod_2pi_chunk`.

    Each double-double operation writes a fresh temporary, and at
    ``N = 1.3 x 10^7`` every one of those is 100 MB.  Thirty of them in flight
    is three gigabytes of memory traffic for what is arithmetically a few
    hundred million flops, and the whole computation runs at the speed of RAM.
    Slicing the work into 256k-element pieces keeps the temporaries in cache and
    is worth a factor of five.
    """
    hi, lo = np.asarray(x[0]), np.asarray(x[1])
    if hi.ndim == 0 or hi.size <= chunk:
        return _mul_mod_2pi_chunk(t, (hi, lo))
    out_hi = np.empty(hi.shape, dtype=float)
    out_lo = np.empty(hi.shape, dtype=float)
    for start in range(0, hi.size, chunk):
        stop = start + chunk
        piece = _mul_mod_2pi_chunk(t, (hi[start:stop], lo[start:stop]))
        out_hi[start:stop] = piece[0]
        out_lo[start:stop] = piece[1]
    return out_hi, out_lo


def mul_mod_2pi(t: float, x):
    """``(t * x) mod 2 pi`` in ``[-pi, pi]``, for a double-double ``x``.

    ``t`` must be an exactly-representable double (any integer below ``2^53``
    qualifies, as does any height this package uses).  The product is formed in
    double-double, the integer quotient is exact, and the subtraction of
    ``q * 2 pi`` is again double-double, so the surviving absolute error is set
    by the 32-digit representation of a number of size ``t log n``:

    .. math:: \\varepsilon \\approx 10^{-32} \\cdot t\\log n
              \\approx 2\\times10^{-16} \\text{ at } t = 10^{15}.

    That is 15 digits below a radian at a height where the naive computation has
    none at all.
    """
    return to_float(mul_mod_2pi_dd(t, x))


# ---------------------------------------------------------------------------
# scalar quantities at full precision (one per window, so decimal is affordable)
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def theta_series_coefficients(terms: int) -> tuple:
    """The exact rational coefficients ``a_k`` of the ``theta`` expansion.

    .. math::
       \\theta(t) = \\frac t2\\log\\frac t{2\\pi} - \\frac t2 - \\frac\\pi8
                  + \\sum_{k\\ge1} \\frac{a_k}{t^{2k-1}},
       \\qquad a_k = \\frac{2^{2k-1}-1}{2^{2k}}\\,
                     \\frac{|B_{2k}|}{2k(2k-1)}.

    Textbooks print the first four -- ``1/48``, ``7/5760``, ``31/80640``,
    ``127/430080`` -- and stop, which is why every implementation in sight stops
    there too and then has no way to bound what it dropped.  The closed form
    above reproduces all four exactly (:mod:`tests.test_dd` checks it), and the
    package already computes ``B_{2k}`` exactly in :mod:`riemann.special`, so
    there is no reason to quote anything: ask for ten terms and the truncation
    error at ``t = 200`` falls from ``8 x 10^{-25}`` to ``7 x 10^{-41}``.
    """
    from fractions import Fraction

    from .special import bernoulli_exact
    return tuple(
        Fraction(2 ** (2 * k - 1) - 1, 2 ** (2 * k))
        * abs(bernoulli_exact(2 * k)) / (2 * k * (2 * k - 1))
        for k in range(1, terms + 1)
    )


def theta_decimal(t, prec: int = 60, terms: int = 8) -> Decimal:
    """Riemann-Siegel ``theta(t)`` as a :class:`~decimal.Decimal`.

    The asymptotic series is summed to ``terms`` terms with the exact
    coefficients of :func:`theta_series_coefficients`.  It is an asymptotic
    series, so more terms is not unconditionally better -- it eventually
    diverges, at around ``2k = t`` -- but for every height this package touches
    (``t >= 200``) eight terms are far inside the useful range, and the first
    omitted term is ``7 x 10^{-41}`` at ``t = 200`` and ``10^{-236}`` at
    ``t = 10^15``.

    ``t`` may be a :class:`~decimal.Decimal`, which is how callers pass
    ``t0 + d`` without rounding it to the float64 lattice first.
    """
    if t <= 0:
        raise ValueError("theta_decimal requires t > 0")
    with localcontext() as ctx:
        ctx.prec = prec + 15
        # Decimal(float) is exact; Decimal(repr(float)) is not, and near 10^15
        # the difference is up to 0.0625 -- a third of the gap between zeros.
        td = t if isinstance(t, Decimal) else Decimal(float(t))
        pi = pi_decimal(prec + 15)
        result = td / 2 * (td / (2 * pi)).ln() - td / 2 - pi / 8
        inv2 = 1 / (td * td)
        term = 1 / td
        for coefficient in theta_series_coefficients(terms):
            result += Decimal(coefficient.numerator) / coefficient.denominator * term
            term *= inv2
    with localcontext() as ctx:
        ctx.prec = prec
        return +result


def theta_truncation_bound(t: float, terms: int = 8) -> Decimal:
    """A bound on what :func:`theta_decimal` dropped.

    Twice the first omitted term.  The tail is not *proved* here to be
    enveloping -- that is the one loose thread in this module -- but successive
    terms fall by a factor of about ``t^2/4``, so at ``t = 200`` the whole tail
    exceeds its leading term by 6 parts in ``10^5``, and a factor of two is not
    a close-run thing.  The quantity being bounded is ``7 x 10^{-41}`` at the
    very worst height used anywhere in this package, which is twenty orders of
    magnitude below the next smallest entry in any error budget here.
    """
    k = terms + 1
    coefficient = theta_series_coefficients(k)[-1]
    with localcontext() as ctx:
        ctx.prec = 40
        value = (Decimal(coefficient.numerator) / coefficient.denominator
                 / Decimal(float(t)) ** (2 * k - 1))
        return 2 * value


def theta_mod_2pi(t: float, prec: int = 60) -> float:
    """``theta(t)`` reduced modulo ``2 pi``, as a double."""
    with localcontext() as ctx:
        ctx.prec = prec
        th = theta_decimal(t, prec)
        two_pi = 2 * pi_decimal(prec)
        return float(th - two_pi * (th / two_pi).to_integral_value(rounding="ROUND_FLOOR"))


def theta_over_pi(t: float, prec: int = 60) -> Decimal:
    """``theta(t) / pi`` -- the smooth part of the zero count, to ``prec`` digits.

    At ``t = 10^15`` this is about ``5 x 10^{15}``, so a double cannot even hold
    its integer part; Turing's method needs it to a few units in the last place
    of *that*, which is why it is returned as a :class:`~decimal.Decimal`.
    """
    with localcontext() as ctx:
        ctx.prec = prec
        return theta_decimal(t, prec) / pi_decimal(prec)


def mean_gap(t: float) -> float:
    """Average spacing of zero ordinates near ``t``: ``2 pi / log(t / 2 pi)``."""
    return 2.0 * math.pi / math.log(t / (2.0 * math.pi))
