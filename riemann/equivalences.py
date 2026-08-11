"""Statements equivalent to the Riemann Hypothesis, made computable.

RH has an unusually large number of elementary-looking equivalent forms.  That
is part of its fascination and part of its danger: several of them look like
things one could plausibly *check*, and checking them feels like evidence.  This
module implements the main ones so that the checking can actually be done -- and
so that the next document can measure how little the checking proves.

Implemented here
----------------
``Mertens``  ``M(x) = sum_{n<=x} mu(n)``.  RH is equivalent to
    ``M(x) = O(x^{1/2+eps})`` for every ``eps > 0``.

``Robin``    For ``n > 5040``, ``sigma(n) < e^gamma n log log n``.  Robin (1984)
    proved this is equivalent to RH.

``Lagarias`` ``sigma(n) <= H_n + exp(H_n) log(H_n)`` for all ``n >= 1``, with
    equality only at ``n = 1``.  Equivalent to RH (Lagarias 2002); an
    elementary restatement of Robin's criterion.

``Li``       ``lambda_n = sum_rho [1 - (1 - 1/rho)^n] >= 0`` for all ``n >= 1``.
    Equivalent to RH (Li 1997, Bombieri-Lagarias 1999).

A fact worth knowing before trusting any of them
------------------------------------------------
On the critical line ``|1 - 1/rho| = 1`` *exactly*: for ``rho = 1/2 + i gamma``
we have ``|rho - 1| = |-1/2 + i gamma| = |1/2 + i gamma| = |rho|``.  So every
term of Li's sum stays on the unit circle, and ``lambda_n`` grows only
polynomially.  A zero off the line breaks the symmetry: it comes in a quadruple
``rho, bar rho, 1-rho, 1-bar rho``, and whichever of the pair has
``Re < 1/2`` gives ``|1 - 1/rho| > 1``, so its contribution grows like
``|1-1/rho|^n``.  That *is* why Li's criterion detects RH failure -- but the
growth rate for a near-miss is close to ``1``, so the detection only bites at
enormous ``n``.  :mod:`scripts.evidence_strength` measures exactly how large.
"""

from __future__ import annotations

import math

__all__ = [
    "mobius_sieve",
    "mertens",
    "mertens_ratio",
    "divisor_sigma_sieve",
    "robin_ratio",
    "check_robin",
    "colossally_abundant_candidates",
    "harmonic",
    "check_lagarias",
    "li_coefficients",
    "li_coefficient_exact_first",
    "EULER_GAMMA",
]

EULER_GAMMA = 0.5772156649015328606


# ---------------------------------------------------------------------------
# Mertens function
# ---------------------------------------------------------------------------

def mobius_sieve(limit: int) -> list:
    """``mu(n)`` for ``n <= limit`` by a linear-ish sieve of smallest factors."""
    mu = [1] * (limit + 1)
    primes = []
    smallest = [0] * (limit + 1)
    for i in range(2, limit + 1):
        if smallest[i] == 0:
            smallest[i] = i
            primes.append(i)
            mu[i] = -1
        for p in primes:
            if p > smallest[i] or i * p > limit:
                break
            smallest[i * p] = p
            mu[i * p] = 0 if p == smallest[i] else -mu[i]
    mu[0] = 0
    return mu


def mertens(limit: int) -> list:
    """Cumulative ``M(n) = sum_{k<=n} mu(k)`` for ``n <= limit``."""
    mu = mobius_sieve(limit)
    out = [0] * (limit + 1)
    run = 0
    for n in range(1, limit + 1):
        run += mu[n]
        out[n] = run
    return out


def mertens_ratio(limit: int, samples: int = 40) -> dict:
    """``M(x)/sqrt(x)`` sampled up to ``limit``, with its running extremes.

    The *Mertens conjecture* was that ``|M(x)| < sqrt(x)`` for all ``x > 1``.
    It would have implied RH.  Odlyzko and te Riele disproved it in 1985 -- and
    that is the single most useful cautionary tale in this subject, because the
    conjecture had been checked to ``10^9`` and looked completely safe.  No
    explicit counterexample is known even now; the disproof shows only that
    ``limsup M(x)/sqrt(x) > 1.06``, and the first counterexample is believed to
    lie beyond ``10^{20}``.

    RH itself survives the disproof: it needs only ``M(x) = O(x^{1/2+eps})``,
    which is far weaker than the conjecture that died.
    """
    m = mertens(limit)
    rows = []
    peak = 0.0
    step = max(1, limit // samples)
    for x in range(step, limit + 1, step):
        r = m[x] / math.sqrt(x)
        peak = max(peak, abs(r))
        rows.append({"x": x, "M": m[x], "ratio": r, "running_max_abs": peak})
    return {"rows": rows, "limit": limit, "max_abs_ratio": peak}


# ---------------------------------------------------------------------------
# Robin / Lagarias
# ---------------------------------------------------------------------------

def divisor_sigma_sieve(limit: int) -> list:
    """``sigma(n)``, the sum of divisors, for ``n <= limit``."""
    sig = [0] * (limit + 1)
    for d in range(1, limit + 1):
        for multiple in range(d, limit + 1, d):
            sig[multiple] += d
    return sig


def robin_ratio(n: int, sigma_n: int) -> float:
    """``sigma(n) / (n log log n)``; RH says this stays below ``e^gamma`` past 5040."""
    ll = math.log(math.log(n))
    return sigma_n / (n * ll)


def check_robin(limit: int = 200000) -> dict:
    """Test Robin's inequality for ``5040 < n <= limit``.

    Returns the largest ratio found and any violations.  There are none, of
    course -- but the interesting output is *how close* the ratio gets, which is
    the quantity that decides whether this search could ever have found
    anything.
    """
    sig = divisor_sigma_sieve(limit)
    threshold = math.exp(EULER_GAMMA)
    best_n, best_ratio = 0, 0.0
    violations = []
    for n in range(5041, limit + 1):
        r = robin_ratio(n, sig[n])
        if r > best_ratio:
            best_n, best_ratio = n, r
        if r >= threshold:
            violations.append({"n": n, "ratio": r})
    return {
        "limit": limit,
        "e_gamma": threshold,
        "max_ratio": best_ratio,
        "argmax": best_n,
        "margin": threshold - best_ratio,
        "violations": violations,
    }


def _primes_up_to(limit: int) -> list:
    sieve = bytearray([1]) * (limit + 1)
    sieve[0:2] = b"\x00\x00"
    for p in range(2, int(limit ** 0.5) + 1):
        if sieve[p]:
            sieve[p * p::p] = bytearray(len(sieve[p * p::p]))
    return [i for i in range(2, limit + 1) if sieve[i]]


def _sigma_step(p: int, a: int) -> float:
    """``log(sigma(p^{a+1})/p^{a+1}) - log(sigma(p^a)/p^a)``, the gain from
    raising the exponent of ``p`` from ``a`` to ``a+1``."""
    cur = math.log((p ** (a + 1) - 1) / (p ** a * (p - 1)))
    nxt = math.log((p ** (a + 2) - 1) / (p ** (a + 1) * (p - 1)))
    return nxt - cur


def colossally_abundant_candidates(steps: int = 20000, prime_limit: int = 300000) -> list:
    """Products of primorials -- the numbers where Robin's ratio is largest.

    Robin's inequality is only ever near-tight on *colossally abundant* numbers,
    built by repeatedly multiplying in whichever prime raises ``sigma(n)/n`` most
    per unit of ``log n``.  Working entirely with ``log n`` and
    ``log(sigma(n)/n)`` keeps this in floating point even though ``n`` itself
    passes ``10^{100}`` within a few dozen steps.

    Gronwall's theorem says ``limsup sigma(n)/(n log log n) = e^gamma``, with the
    limsup attained along exactly these numbers, so the ratio must climb towards
    ``e^gamma``.  Getting that behaviour out of the computation requires having
    enough primes available: with a short prime list the greedy search exhausts
    it, is forced to keep raising exponents on primes it already has, and the
    ratio turns around and *falls* -- an artefact of the truncation, not
    arithmetic.  The selection is done with a heap so the prime list can be long
    enough for the asymptotics to show.
    """
    import heapq

    primes = _primes_up_to(prime_limit)
    exponents = {}
    heap = [(-_sigma_step(p, 0) / math.log(p), p) for p in primes[:1]]
    frontier = 1  # next unused prime index; primes enter the heap lazily

    out = []
    log_n = 0.0
    log_sigma_over_n = 0.0
    max_prime_used = 2

    for _ in range(steps):
        if frontier < len(primes):
            p_next = primes[frontier]
            heapq.heappush(heap, (-_sigma_step(p_next, 0) / math.log(p_next), p_next))
            frontier += 1
        if not heap:
            break
        neg_gain, p = heapq.heappop(heap)
        a = exponents.get(p, 0)
        log_sigma_over_n += _sigma_step(p, a)
        log_n += math.log(p)
        exponents[p] = a + 1
        max_prime_used = max(max_prime_used, p)
        heapq.heappush(heap, (-_sigma_step(p, a + 1) / math.log(p), p))

        if log_n > math.log(5040.0):  # Robin's inequality starts here
            ratio = math.exp(log_sigma_over_n) / math.log(log_n)
            out.append({
                "log_n": log_n,
                "digits": log_n / math.log(10.0),
                "robin_ratio": ratio,
                "margin": math.exp(EULER_GAMMA) - ratio,
                "largest_prime": max_prime_used,
                "prime_list_exhausted": frontier >= len(primes),
            })
    return out


def harmonic(n: int) -> float:
    """``H_n = sum_{k<=n} 1/k``."""
    return sum(1.0 / k for k in range(1, n + 1))


def check_lagarias(limit: int = 20000) -> dict:
    """Test ``sigma(n) <= H_n + exp(H_n) log(H_n)`` for ``n <= limit``."""
    sig = divisor_sigma_sieve(limit)
    worst_n, worst_slack = 0, math.inf
    h = 0.0
    for n in range(1, limit + 1):
        h += 1.0 / n
        bound = h + math.exp(h) * math.log(h) if h > 0 else 0.0
        slack = bound - sig[n]
        if n > 1 and slack < worst_slack:
            worst_n, worst_slack = n, slack
    return {"limit": limit, "tightest_n": worst_n, "smallest_slack": worst_slack,
            "holds": worst_slack >= 0.0}


# ---------------------------------------------------------------------------
# Li's criterion
# ---------------------------------------------------------------------------

def li_coefficients(n_max: int, gammas, sigmas=None) -> list:
    """``lambda_n`` for ``n = 1 .. n_max`` from a list of zero ordinates.

    Parameters
    ----------
    gammas:
        Positive imaginary parts of the zeros.
    sigmas:
        Optional matching real parts.  Defaults to ``1/2`` for every zero (i.e.
        assuming RH).  Supplying something else is how the sensitivity
        experiment in ``scripts/evidence_strength.py`` moves a zero off the
        line and asks whether ``lambda_n`` notices.

    Each zero is counted with its conjugate.  If a zero is given off the line,
    its reflection ``1 - rho`` is included too, since the functional equation
    forces zeros to come in quadruples ``{rho, bar rho, 1-rho, 1-bar rho}``.
    """
    if sigmas is None:
        sigmas = [0.5] * len(gammas)
    if len(sigmas) != len(gammas):
        raise ValueError("sigmas and gammas must have the same length")

    roots = []
    for sig, gam in zip(sigmas, gammas):
        roots.append(complex(sig, gam))
        if abs(sig - 0.5) > 1e-15:
            roots.append(complex(1.0 - sig, gam))  # the reflected partner

    out = []
    # w = 1 - 1/rho, accumulated by repeated multiplication rather than pow.
    powers = [1.0 + 0.0j] * len(roots)
    ws = [1.0 - 1.0 / r for r in roots]
    for _ in range(1, n_max + 1):
        total = 0.0
        for i, w in enumerate(ws):
            powers[i] *= w
            # rho and its conjugate contribute conjugate values; take 2*Re once.
            total += 2.0 * (1.0 - powers[i]).real
        out.append(total)
    return out


def li_coefficient_exact_first() -> float:
    """``lambda_1 = 1 + gamma/2 - (1/2) log(4 pi)``, in closed form.

    Used to check the zero-sum computation: the sum over zeros must reproduce
    this number, which is derived independently from the functional equation.
    """
    return 1.0 + EULER_GAMMA / 2.0 - 0.5 * math.log(4.0 * math.pi)
