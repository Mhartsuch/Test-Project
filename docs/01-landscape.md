# The Riemann Hypothesis: a map of the problem

*This document summarises known mathematics. Nothing in it is original. Its
purpose is to lay out the terrain accurately enough that the next document —
on why the attacks have failed — can be precise about where each one breaks.*

---

## 1. The statement

The Riemann zeta function is defined for `Re(s) > 1` by

$$\zeta(s) = \sum_{n=1}^{\infty} n^{-s} = \prod_{p \text{ prime}} \left(1 - p^{-s}\right)^{-1}$$

The two expressions being equal *is* the fundamental theorem of arithmetic,
written analytically. That is the whole reason zeta knows anything about primes.

Zeta continues meromorphically to the whole plane with a single simple pole at
`s = 1`, and satisfies the functional equation

$$\pi^{-s/2}\Gamma(s/2)\zeta(s) = \pi^{-(1-s)/2}\Gamma((1-s)/2)\zeta(1-s)$$

which is the statement that the completed function `ξ(s) = ½s(s−1)π^{−s/2}Γ(s/2)ζ(s)`
satisfies `ξ(s) = ξ(1−s)`.

The functional equation forces "trivial" zeros at `s = −2, −4, −6, …`. All other
zeros lie in the *critical strip* `0 ≤ Re(s) ≤ 1`, and are symmetric about both
the real axis and the *critical line* `Re(s) = ½`.

> **Riemann Hypothesis (1859).** Every non-trivial zero has `Re(s) = ½`.

## 2. Why anyone cares

Von Mangoldt's explicit formula makes the connection exact. With
`ψ(x) = Σ_{p^k ≤ x} log p`,

$$\psi_0(x) = x - \sum_{\rho} \frac{x^{\rho}}{\rho} - \log 2\pi - \tfrac12 \log(1 - x^{-2})$$

Every zero `ρ` contributes an oscillation of magnitude `x^{Re(ρ)}`. So the real
parts of the zeros directly control how far the primes stray from their expected
density. RH is exactly equivalent to

$$\psi(x) = x + O\!\left(x^{1/2} \log^2 x\right)$$

and this is the **best possible** error term: since zeros exist with `Re(ρ) = ½`,
the error genuinely is `Ω(x^{1/2})` — it cannot be improved.

This is the point most popular accounts get backwards. RH does not say the primes
are randomly distributed. It says they are **as regular as they could possibly
be** — that the error term is exactly at its theoretical floor, with no excess.

`scripts/explicit_formula_demo.py` in this repository performs this
reconstruction numerically: feeding 5000 computed zero ordinates into the
formula reproduces the prime-power staircase with RMS error 0.077, and every one
of the twelve steepest rises lands on a prime power.

## 3. What is actually known

**Proved:**

| Result | Who, when |
|---|---|
| Zeros exist; `N(T) ~ (T/2π)log(T/2πe)` | Riemann 1859 / von Mangoldt 1905 |
| No zeros on `Re(s) = 1` (⟹ prime number theorem) | Hadamard, de la Vallée Poussin 1896 |
| Infinitely many zeros on the critical line | Hardy 1914 |
| A positive proportion of zeros on the line | Selberg 1942 |
| At least ⅓ of zeros on the line | Levinson 1974 |
| At least ⅖ of zeros on the line | Conrey 1989 |
| Just over 41% | Pratt–Robles–Zaharescu–Zeindler 2020 |
| Zero-free region `σ > 1 − c/(log t)^{2/3}(log log t)^{1/3}` | Vinogradov–Korobov 1958 |
| RH for curves over finite fields | Weil 1948 |
| The full Weil conjectures | Deligne 1974 |
| `Λ ≥ 0` for the de Bruijn–Newman constant | Rodgers–Tao 2018 |

**Verified numerically:** the first 10¹³ zeros (Gourdon 2004), plus rigorous
verification to height 3.06 × 10¹⁰ (Platt). All on the line.

Note the shape of the "proportion" results carefully. They come from Levinson's
mollifier method, and the obstruction to pushing them further is the length of
the Dirichlet polynomial one can control — a limitation coming from exponential
sum estimates and the large sieve. Going from 41% to 100% is not a matter of
grinding harder; and even 100% would not *be* RH, which asserts something about
every zero, not almost every zero.

## 4. Equivalent formulations

RH has an unusual number of elementary-looking equivalents. Several are
implemented in `riemann/equivalences.py`.

**Prime counting.** `π(x) = li(x) + O(√x log x)`.

**Mertens function.** `M(x) = Σ_{n≤x} μ(n) = O(x^{1/2+ε})` for every `ε > 0`.

**Robin's criterion (1984).** For every `n > 5040`,
`σ(n) < e^γ n log log n`, where `σ` is the sum of divisors.

**Lagarias (2002).** For every `n ≥ 1`,
`σ(n) ≤ H_n + exp(H_n) log(H_n)`, with equality only at `n = 1`.
An entirely elementary statement, equivalent to RH.

**Li's criterion (1997).** `λ_n ≥ 0` for every `n ≥ 1`, where
`λ_n = Σ_ρ [1 − (1 − 1/ρ)^n]`.

**Nyman–Beurling (1950/55).** RH holds iff the span of certain dilation
functions is dense in `L²(0,1)`. Sharpened by Báez-Duarte (2003) to a
concrete approximation problem in terms of `Σ μ(n)/n`.

**de Bruijn–Newman.** `Λ ≤ 0`. Combined with Rodgers–Tao, RH ⟺ `Λ = 0`.

**Weil positivity.** RH holds iff a certain explicit quadratic form is positive
semidefinite.

The abundance of equivalents is seductive and should be treated with suspicion.
Each is a *restatement*, not a foothold: an equivalent form of a hard problem is
exactly as hard. `docs/03-strength-of-evidence.md` measures how little the
checkable ones actually check.

## 5. The one place the analogue is a theorem

For a smooth projective curve `C` of genus `g` over the finite field `F_q`, the
zeta function

$$Z(C, T) = \exp\left(\sum_{n \ge 1} \#C(\mathbb{F}_{q^n}) \frac{T^n}{n}\right)$$

is a rational function whose numerator has degree `2g`, and **Weil proved** that
all its inverse roots have absolute value exactly `q^{1/2}` — precisely the
analogue of RH.

This is the single strongest reason to believe RH. It is also, as the next
document explains, the most instructive failure: the proof uses a geometric
object that has no known counterpart over the integers, and sixty years of
effort to construct one has not succeeded.

---

*Continue to [`02-failure-modes.md`](02-failure-modes.md) — the attacks, and
precisely where each one breaks.*
