"""Interval arithmetic: results that come with a proof attached.

What a bound is worth
---------------------
The rest of this package reports errors.  This module reports *enclosures*: an
:class:`Interval` is a pair of doubles ``[lo, hi]`` together with the promise
that the exact real number it stands for lies between them.  Every operation
preserves that promise.  So when :mod:`riemann.rigorous` says ``Z(t) < 0`` it is
not saying "the computed value was negative and the error is probably smaller";
it is saying the true value of ``Z(t)`` lies in an interval whose upper end is
negative.

Directed rounding
-----------------
IEEE-754 round-to-nearest commits an error of at most half an ulp, so widening a
computed result by one ulp in each direction certainly contains the exact one.
:func:`math.nextafter` does exactly that, which is why no processor rounding-mode
control is needed -- a real advantage in Python, where there is none.  The cost
is intervals about twice as wide as with true directed rounding, which for the
quantities here is irrelevant.

Where the elementary functions come from
----------------------------------------
An interval library is only as rigorous as its ``exp`` and ``log``.  Using the
platform's libm would forfeit the whole point: the C standard makes no accuracy
promise whatever about them, and "everybody knows it is under an ulp" is exactly
the sort of claim this package exists to not make.  So:

* ``exp``, ``log`` and ``sqrt`` come from :mod:`decimal`, whose documentation
  guarantees *correctly rounded* results at the working precision.  Computing at
  60 digits and widening by one unit in the last place of that gives an
  enclosure valid to ``10^{-59}``, far tighter than a double can express.
* ``sin`` and ``cos`` are not in :mod:`decimal`.  They are built here: reduce
  modulo ``pi/2`` against a high-precision ``pi``, then sum the Taylor series,
  which is *alternating with decreasing terms* on the reduced range, so the
  truncation error is bounded by the first omitted term -- a rigorous bound with
  nothing hidden in it.
* ``pi`` itself is computed from Machin's formula
  ``pi/4 = 4 arctan(1/5) - arctan(1/239)`` in exact integer arithmetic.  Both
  arctan series alternate, so again the tail is bounded by the first dropped
  term, and the result is provably correct to the requested number of digits.
  Nothing is quoted from memory.

The residual assumptions are: IEEE-754 binary64 with round-to-nearest, a correct
:mod:`decimal`, and correct integer arithmetic.
"""

from __future__ import annotations

import math
from decimal import Decimal, localcontext
from functools import lru_cache

__all__ = [
    "Interval",
    "machin_pi",
    "PI",
    "TWO_PI",
    "HALF_PI",
    "LOG_2",
]

_INF = math.inf


def _down(x: float) -> float:
    """The next double below ``x``."""
    return math.nextafter(x, -_INF)


def _up(x: float) -> float:
    """The next double above ``x``."""
    return math.nextafter(x, _INF)


# ---------------------------------------------------------------------------
# pi, from integer arithmetic
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def machin_pi(digits: int = 60) -> Decimal:
    """``pi`` to ``digits`` correct decimal places, by Machin's formula.

    ``arctan(1/x) = sum_k (-1)^k / ((2k+1) x^{2k+1})`` is alternating with
    strictly decreasing terms for ``x >= 2``, so stopping when a term reaches
    zero in scaled integer arithmetic leaves an error below one unit in the last
    scaled place.  Four such units of slack are carried, then the result is
    truncated to ``digits``.
    """
    guard = digits + 15
    scale = 10 ** guard

    def arctan_inv(x: int) -> int:
        """``scale * arctan(1/x)`` to within a couple of units."""
        total = term = scale // x
        x2 = x * x
        k = 1
        while term:
            term //= x2
            total += -term // (2 * k + 1) if k % 2 else term // (2 * k + 1)
            k += 1
        return total

    pi_scaled = 4 * (4 * arctan_inv(5) - arctan_inv(239))
    with localcontext() as ctx:
        ctx.prec = guard + 5
        value = Decimal(pi_scaled) / Decimal(scale)
    with localcontext() as ctx:
        ctx.prec = digits
        return +value


@lru_cache(maxsize=None)
def _constants(prec: int = 60):
    with localcontext() as ctx:
        ctx.prec = prec
        pi = machin_pi(prec)
        return {"pi": pi, "two_pi": +(2 * pi), "half_pi": +(pi / 2),
                "log2": Decimal(2).ln()}


# ---------------------------------------------------------------------------
# the interval type
# ---------------------------------------------------------------------------

class Interval:
    """A closed real interval ``[lo, hi]`` that provably contains its value."""

    __slots__ = ("lo", "hi")

    def __init__(self, lo, hi=None):
        if hi is None:
            hi = lo
        self.lo = float(lo)
        self.hi = float(hi)
        if not (self.lo <= self.hi):
            raise ValueError(f"empty or invalid interval [{lo}, {hi}]")

    # -- constructors ------------------------------------------------------
    @classmethod
    def from_decimal(cls, value: Decimal, error: Decimal = Decimal(0)) -> "Interval":
        """Tightest double interval containing ``value +- error``."""
        return cls(_widen(value, error, False, 60), _widen(value, error, True, 60))

    @classmethod
    def hull(cls, *items) -> "Interval":
        los = [x.lo if isinstance(x, Interval) else float(x) for x in items]
        his = [x.hi if isinstance(x, Interval) else float(x) for x in items]
        return cls(min(los), max(his))

    # -- inspection --------------------------------------------------------
    @property
    def mid(self) -> float:
        return 0.5 * (self.lo + self.hi)

    @property
    def width(self) -> float:
        return _up(self.hi - self.lo)

    @property
    def rad(self) -> float:
        return _up(0.5 * self.width)

    def contains(self, x) -> bool:
        return self.lo <= float(x) <= self.hi

    def is_positive(self) -> bool:
        """True only if *every* point of the interval is positive."""
        return self.lo > 0.0

    def is_negative(self) -> bool:
        return self.hi < 0.0

    def sign(self) -> int:
        """``+1``/``-1`` if the sign is certain, ``0`` if the interval straddles."""
        if self.lo > 0.0:
            return 1
        if self.hi < 0.0:
            return -1
        return 0

    def __repr__(self) -> str:
        return f"Interval({self.lo!r}, {self.hi!r})"

    def __str__(self) -> str:
        return f"[{self.lo:.17g}, {self.hi:.17g}]"

    # -- arithmetic --------------------------------------------------------
    @staticmethod
    def _coerce(other):
        return other if isinstance(other, Interval) else Interval(other)

    def __neg__(self) -> "Interval":
        return Interval(-self.hi, -self.lo)

    def __add__(self, other) -> "Interval":
        o = self._coerce(other)
        return Interval(_down(self.lo + o.lo), _up(self.hi + o.hi))

    __radd__ = __add__

    def __sub__(self, other) -> "Interval":
        o = self._coerce(other)
        return Interval(_down(self.lo - o.hi), _up(self.hi - o.lo))

    def __rsub__(self, other):
        return self._coerce(other) - self

    def __mul__(self, other) -> "Interval":
        o = self._coerce(other)
        products = (self.lo * o.lo, self.lo * o.hi, self.hi * o.lo, self.hi * o.hi)
        return Interval(_down(min(products)), _up(max(products)))

    __rmul__ = __mul__

    def __truediv__(self, other) -> "Interval":
        o = self._coerce(other)
        if o.lo <= 0.0 <= o.hi:
            raise ZeroDivisionError("interval divisor straddles zero")
        quotients = (self.lo / o.lo, self.lo / o.hi, self.hi / o.lo, self.hi / o.hi)
        return Interval(_down(min(quotients)), _up(max(quotients)))

    def __rtruediv__(self, other):
        return self._coerce(other) / self

    def __pow__(self, n: int) -> "Interval":
        if not isinstance(n, int) or n < 0:
            raise ValueError("only non-negative integer powers")
        result = Interval(1.0)
        base = self
        while n:
            if n & 1:
                result = result * base
            base = base * base
            n >>= 1
        return result

    def abs(self) -> "Interval":
        if self.lo >= 0.0:
            return self
        if self.hi <= 0.0:
            return -self
        return Interval(0.0, max(-self.lo, self.hi))

    # -- elementary functions ---------------------------------------------
    def sqrt(self) -> "Interval":
        if self.lo < 0.0:
            raise ValueError("sqrt of a interval containing negatives")
        return Interval(_down(_decimal_unary(self.lo, "sqrt", False)),
                        _up(_decimal_unary(self.hi, "sqrt", True)))

    def exp(self) -> "Interval":
        return Interval(_down(_decimal_unary(self.lo, "exp", False)),
                        _up(_decimal_unary(self.hi, "exp", True)))

    def log(self) -> "Interval":
        if self.lo <= 0.0:
            raise ValueError("log of an interval reaching zero")
        return Interval(_down(_decimal_unary(self.lo, "ln", False)),
                        _up(_decimal_unary(self.hi, "ln", True)))

    def cos(self) -> "Interval":
        return _trig(self, sine=False)

    def sin(self) -> "Interval":
        return _trig(self, sine=True)


# ---------------------------------------------------------------------------
# decimal-backed monotone functions
# ---------------------------------------------------------------------------

def _round_out(value: Decimal, up: bool) -> float:
    """Nearest double on the required side of an exact decimal.

    The comparison ``Decimal(f) <> value`` is exact -- :mod:`decimal` compares
    without rounding -- so this is the tightest correct answer.  Any *arithmetic*
    on decimals must be done by the caller inside a context wide enough to hold
    the result: the default context is 28 digits, which silently rounds
    ``1 - 2 x 10^{-33}`` to ``1`` and would turn a valid enclosure into a false
    one.
    """
    f = float(value)
    if math.isinf(f):
        return f
    d = Decimal(f)
    if up and d < value:
        return _up(f)
    if not up and d > value:
        return _down(f)
    return f


def _widen(value: Decimal, error: Decimal, up: bool, prec: int) -> float:
    """``value +- error``, rounded out to a double, at a safe working precision."""
    with localcontext() as ctx:
        ctx.prec = prec + 10
        shifted = value + error if up else value - error
    return _round_out(shifted, up=up)


def _decimal_unary(x: float, name: str, up: bool, prec: int = 50) -> float:
    """``sqrt``/``exp``/``ln`` of a double, correctly rounded then widened.

    :mod:`decimal` promises a correctly rounded result at the working precision,
    so the exact value differs from the returned one by under one unit in the
    last of ``prec`` digits.  Widening by that much and then rounding out to a
    double is a valid enclosure; at ``prec = 50`` the widening is far below a
    double's resolution and the enclosure is as tight as binary64 permits.
    """
    with localcontext() as ctx:
        ctx.prec = prec
        value = getattr(Decimal(x), name)()
        slack = value.scaleb(-(prec - 2)).copy_abs()
    return _widen(value, slack, up, prec)


# ---------------------------------------------------------------------------
# sine and cosine
# ---------------------------------------------------------------------------

def _sin_cos_decimal(x: Decimal, sine: bool, prec: int):
    """``sin``/``cos`` of a decimal, with a rigorous error bound.

    The argument is reduced modulo ``pi/2`` -- the reduction is exact bar the
    error in ``pi``, which is carried explicitly -- and the Taylor series on
    ``|r| <= pi/4`` alternates with strictly decreasing terms, so truncating it
    leaves an error below the first omitted term.
    """
    with localcontext() as ctx:
        ctx.prec = prec + 10
        half_pi = _constants(prec + 10)["half_pi"]
        k = int((x / half_pi).to_integral_value(rounding="ROUND_HALF_EVEN"))
        r = x - k * half_pi
        # error in pi propagates as |k| * (error in pi/2); pi is good to
        # 10^-(prec+10), so this is utterly negligible but is carried anyway.
        pi_error = Decimal(10) ** (-(prec + 8)) * abs(k)

        quadrant = k % 4
        if sine:
            quadrant = (quadrant + 3) % 4          # sin(x) = cos(x - pi/2)
        want_cos = quadrant % 2 == 0
        negate = quadrant in (1, 2)

        total = Decimal(1) if want_cos else r
        term = total
        r2 = r * r
        n = 1
        start = 2 if want_cos else 3
        i = start
        while True:
            term = -term * r2 / (i * (i - 1))
            total += term
            if abs(term) < Decimal(10) ** (-(prec + 6)):
                break
            i += 2
            n += 1
        bound = abs(term) + pi_error
        if negate:
            total = -total
    return total, bound


def _trig(x: Interval, sine: bool, prec: int = 50) -> Interval:
    """Enclosure of ``sin``/``cos`` over an interval.

    Both functions are 1-Lipschitz, so an interval of width ``w`` maps into one
    of width at most ``w``; the endpoints are enclosed exactly and the interval
    is grown by ``w`` to cover every interior extremum.  Crude, but these
    intervals are always narrow where it matters, and crude-and-correct beats
    sharp-and-hopeful.
    """
    lo_val, lo_err = _sin_cos_decimal(Decimal(x.lo), sine, prec)
    if x.lo == x.hi:
        return Interval(max(-1.0, _widen(lo_val, lo_err, False, prec)),
                        min(1.0, _widen(lo_val, lo_err, True, prec)))
    hi_val, hi_err = _sin_cos_decimal(Decimal(x.hi), sine, prec)
    with localcontext() as ctx:
        ctx.prec = prec + 10
        spread = Decimal(x.hi) - Decimal(x.lo)
        lo = min(lo_val - lo_err, hi_val - hi_err) - spread
        hi = max(lo_val + lo_err, hi_val + hi_err) + spread
    return Interval(max(-1.0, _round_out(lo, False)),
                    min(1.0, _round_out(hi, True)))


# ---------------------------------------------------------------------------
# constants as intervals
# ---------------------------------------------------------------------------

def _const_interval(name: str) -> Interval:
    value = _constants(60)[name]
    return Interval.from_decimal(value, Decimal(10) ** -58)


PI = _const_interval("pi")
TWO_PI = _const_interval("two_pi")
HALF_PI = _const_interval("half_pi")
LOG_2 = _const_interval("log2")
