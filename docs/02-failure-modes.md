# Why the attacks on RH have failed

*The interesting content of a 165-year-old open problem is not the list of
approaches — it is the list of reasons each one stops. Those reasons are sharp,
they are documented, and together they constrain what any future proof can look
like.*

---

## 0. The constraint every approach must satisfy

Before the individual failures, there is a general fact that kills a whole
class of arguments at once.

**A functional equation is not enough.** The Davenport–Heilbronn function is a
specific linear combination of two Dirichlet L-functions. It satisfies a
functional equation of exactly Riemann's type. It has infinitely many zeros off
the critical line — some even in `σ > 1`. Similarly, Epstein zeta functions of
quadratic forms in several variables satisfy Riemann-type functional equations
and can have zeros off the line.

This one is **verified in this repository rather than cited**
(`riemann/davenport_heilbronn.py`, `scripts/davenport_heilbronn_demo.py`). Built
from the character `χ` mod 5 with `χ(2) = i`, the construction requires a
constant `ξ` with `ε(χ) = η·Ā/A`, which is *derived* from the Gauss sum — and
admits two solutions, one per sign `η = ±1`:

| branch | ξ | \|a₂\| | functional equation verified to |
|---|---|---|---|
| `η = +1` | +0.2840790438 | 0.284 | 7.8 × 10⁻¹³ |
| `η = −1` | −3.5201470213 | 3.520 | 2.9 × 10⁻¹² |

Both are genuine Riemann-type functional equations. Both have zeros off the
critical line. The `η = −1` branch is the dramatic one: because `|a₂| > 1`, the
second term of its Dirichlet series can outweigh the first, and it has zeros at

`s = 2.3086 + 8.9184i`,  `1.9437 + 18.8994i`,  `2.0911 + 26.5450i`, …

with `|f| ~ 10⁻¹⁵`, while `|ζ|` at those same points is `1.16`, `1.26`, `1.20`.
Zeta *cannot* vanish there — `Re s > 1` is inside its Euler product's region of
convergence, where no factor is zero. The reflections `1 − ρ̄` at `Re s ≈ −1`
are zeros too, so this function has zeros straddling the critical line at the
maximum possible distance.

So the Euler product is not decoration; it is the whole content. The first test
to apply to any claimed proof of RH is: *where does this argument fail for
Davenport–Heilbronn?* If it does not fail, the argument is wrong, and that can
be determined before reading the details.

**An Euler product is not enough either.** Products can be built with
reasonable analytic behaviour and no critical-line property.

So any proof of RH must use the functional equation **and** the Euler product
**and** must combine them in a way that is not soft. This eliminates every
argument that only manipulates symmetry, growth, or order of magnitude. It is
the reason the problem cannot be settled by cleverness with contour integrals,
and it should be the first test applied to any claimed proof: *where does this
argument fail for Davenport–Heilbronn?* If the answer is "it doesn't", the
argument is wrong.

**And there is no margin.** De Bruijn and Newman showed there is a constant `Λ`
with RH ⟺ `Λ ≤ 0`. Newman conjectured `Λ ≥ 0`, remarking that this quantifies
the belief that RH, if true, is "only barely so". Rodgers and Tao **proved**
`Λ ≥ 0` in 2018. Therefore

> **RH ⟺ Λ = 0, exactly.**

RH is not true with room to spare. It sits exactly on the boundary of failure.
Any proof must be sharp enough to establish an equality, not an inequality with
slack — which rules out every averaging, smoothing, or perturbative method,
since none of them can distinguish `Λ = 0` from `Λ = 10⁻⁹`, and that distinction
is the entire problem.

---

## 1. The function field analogue: proved, and it does not transfer

**The approach.** Replace `Z` by `F_q[t]`. For a curve `C/F_q`, the analogue of
RH is a theorem (Weil 1948; Deligne 1974 in general). If we understood *why* it
is true there, perhaps we could port the argument.

**Why it works over function fields.** The proof is geometric, and the geometry
is essential:

1. The zeros of `Z(C,T)` are eigenvalues of the Frobenius endomorphism acting
   on the first cohomology of `C`.
2. To bound those eigenvalues, one works on the **surface** `C × C`, where
   Frobenius appears as a correspondence — a divisor class.
3. The bound then follows from a **positivity** statement about the
   intersection pairing on that surface: the Castelnuovo–Severi inequality, or
   equivalently the Hodge index theorem. The intersection form is negative
   definite on the relevant subspace, and that definiteness *is* the Riemann
   hypothesis for `C`.

The entire proof rests on having a two-dimensional object and a positive-definite
pairing on it.

**Where it breaks for `Z`.** `Spec(Z)` behaves like a curve, but a curve over
*what*? To imitate Weil we would need the surface `Spec(Z) × Spec(Z)` — a
product over some base field "beneath" the integers. No such base exists. The
fibre product of `Spec(Z)` with itself over `Spec(Z)` is just `Spec(Z)` again;
the construction collapses.

This is the origin of the search for "the field with one element" `F₁`, and of
Deninger's programme to realise the zeros as eigenvalues of a flow on an
infinite-dimensional cohomology, and of Arakelov geometry's attempt to compactify
`Spec(Z)` by adding an archimedean place. All are serious. None has produced the
missing object. Connes and Consani have built structures with some of the right
formal properties; the positivity input — the actual engine of Weil's proof — has
never been recovered.

**Status:** the most promising route, blocked for sixty years on a single missing
geometric object.

---

## 2. Hilbert–Pólya: the operator nobody can find

**The approach.** Suppose there is a self-adjoint operator `H` on some Hilbert
space whose eigenvalues are exactly the numbers `γ` with `½ + iγ` a zero.
Self-adjoint operators have real eigenvalues; therefore every `γ` is real;
therefore RH.

**Why it is taken seriously.** The evidence is genuinely striking and is
*statistical*. Montgomery (1973) computed the pair correlation of zero
ordinates and found `1 − (sin πr/πr)²`. Dyson recognised it instantly as the
pair correlation of eigenvalues of a random Hermitian matrix — the Gaussian
Unitary Ensemble. Odlyzko then verified the agreement numerically to
extraordinary precision near height 10²⁰.

This repository reproduces the phenomenon at modest height: with 999,998 zeros,
the nearest-neighbour spacing distribution fits GUE **17.3 times better** than
Poisson, and the pair correlation matches the Montgomery–Dyson curve to a mean
absolute deviation of 0.014 (`scripts/gue_statistics.py`). The zeros *repel*
each other, exactly as eigenvalues do and as independent points do not.

The fit improves with both sample size and height — 100,000 zeros to height
74,921 gave 12.8×; a million to height 600,269 gives 17.3×, with the second
spacing moment moving from 1.1607 to 1.1650 against the GUE value 1.1781. That
residual gap is the known slow convergence to the random-matrix limit, which is
why Odlyzko went to height 10²⁰ rather than 10⁶.

Statistics like these are extremely hard to explain unless the ordinates really
are a spectrum.

**Where it breaks.** Nobody can produce the operator.

- Berry and Keating proposed that the classical Hamiltonian is `H = xp`, whose
  semiclassical density of states reproduces the zero-counting function. But
  `xp` has continuous spectrum; obtaining discrete eigenvalues requires
  regularisation and boundary conditions, and the conditions that give the right
  answer have to be chosen to give the right answer. The counting function is
  put in by hand, so nothing is derived.

- **Connes (1999)** built the most serious version: an action on the adele class
  space in which the zeros appear naturally. Two problems. First, they appear as
  an *absorption* spectrum — gaps in a continuous spectrum, not eigenvalues of a
  self-adjoint operator, so real-eigenvalue arguments do not directly apply.
  Second, and decisively, the trace formula he obtains is **equivalent** to RH
  rather than a proof of it: establishing the required trace identity is
  precisely as hard as Weil's positivity. The argument is a beautiful
  reformulation that returns you to where you started.

**Status:** the strongest *evidence* for RH, and a complete non-starter as a
*proof*, because every construction so far either assumes what it needs or
restates the problem.

---

## 3. Weil positivity: exact, and circular in practice

**The approach.** Weil's explicit formula turns RH into positivity of a
quadratic form built from a test function. RH holds iff that form is positive
semidefinite on a suitable space.

**Where it breaks.** This is a genuine equivalence and a genuinely useful
organising principle — Bombieri has developed it extensively. But no independent
handle on the positivity has been found. Over function fields, the corresponding
positivity comes from the Hodge index theorem on a surface. Over `Q`, we are
back to §1: no surface, no index theorem, no positivity.

Every "positivity criterion" for RH — Weil's, Li's, Bombieri–Lagarias, the
Xian-Jin Li quadratic forms — shares this structure. They are exact and they are
inert. And there is a quantitative version of their inertness: `docs/03` shows
that Li's criterion, checked to any `n` a computer can reach, would fail to
detect a zero sitting at `Re(ρ) = 0.6`.

---

## 4. Zero-free regions: shrinking to nothing

**The approach.** Prove no zeros in `σ > 1 − δ` for successively larger `δ`,
and hope to reach `δ = ½`.

**What is known.** The classical de la Vallée Poussin region is
`σ > 1 − c/log t`. Vinogradov and Korobov improved it to
`σ > 1 − c/(log t)^{2/3}(log log t)^{1/3}`, and there it has essentially stood
since 1958.

**Where it breaks.** Look at the shape. Every known zero-free region **narrows
to zero width as `t → ∞`**. Nobody has proved a zero-free region of the form
`σ > 1 − δ` for any *fixed* `δ > 0` — not `δ = 0.001`. There is no known method
that produces one. The gap between "width shrinking like `1/(log t)^{2/3}`" and
"width `½`" is not a quantitative gap to be closed by sharper estimates; it is
the difference between having a method and not having one.

This is worth stating plainly because it is easy to misread the progress: 125
years of work on zero-free regions has not moved `δ` off zero.

---

## 5. Mollifiers and proportions: a real method with a hard ceiling

**The approach.** Levinson's method: multiply zeta by a Dirichlet polynomial
(a "mollifier") chosen to tame its oscillation, then count sign changes. This
gives *unconditional* lower bounds on the proportion of zeros on the line —
⅓ (Levinson 1974), ⅖ (Conrey 1989), just over 41% today.

**Where it breaks.** The proportion obtained is governed by the length of
mollifier one can control, and controlling longer mollifiers requires estimates
for exponential sums and mean values beyond anything currently available. The
returns have been brutally diminishing: 1974 to now, roughly 33% to 41%.

More importantly, **the method cannot reach the target even in principle**.
Proving 100% of zeros lie on the line would still not prove RH, which is a
statement about every zero without exception. A single exceptional zero is
invisible to any density-of-zeros argument. This is a method that approaches
a wall that is not the finish line.

---

## 6. The parity obstruction

**The approach.** Sieve methods are the workhorse of analytic number theory.
Could a sufficiently refined sieve control `μ(n)` or `Λ(n)` well enough to give
RH?

**Where it breaks.** No — and this is a *theorem*, not a difficulty. Selberg's
parity obstruction says sieve methods cannot distinguish integers with an even
number of prime factors from those with an odd number. RH is equivalent to
cancellation in `Σ μ(n)`, and `μ` is *precisely* the parity function. A method
provably blind to parity cannot detect the cancellation.

Parity can be broken, but only by injecting non-sieve input — Friedlander and
Iwaniec's work on `x² + y⁴` is the model. Nothing of that kind is remotely
strong enough for RH.

**Status:** a proved no-go theorem against an entire toolkit.

---

## 7. Approaches that were tried and died

These are worth listing because they show the problem killing specific,
reasonable ideas.

**Turán's partial sums.** Turán showed that if the partial sums
`Σ_{n≤N} n^{-s}` had no zeros in `σ > 1` for suitable `N`, RH would follow.
Montgomery (1983) showed those partial sums *do* have zeros in `σ > 1`. The
approach is dead, not merely stuck.

**The Mertens conjecture.** `|M(x)| < √x` would have implied RH. It had been
verified to 10⁹ and was widely believed. Odlyzko and te Riele **disproved** it
in 1985. No explicit counterexample is known even now; the first is thought to
lie beyond 10²⁰. See `docs/03` — this is the cautionary tale of the subject.

**de Branges.** Louis de Branges — who proved the Bieberbach conjecture, so this
is not a crank — has announced proofs of RH repeatedly since the 1980s using
Hilbert spaces of entire functions. Conrey and Li (2000) showed that the
positivity conditions the approach requires are false in the relevant setting.
The approach has not recovered.

**Purely computational verification.** 10¹³ zeros checked, all on the line. This
proves nothing about zero 10¹³+1, and §3 of `docs/03` quantifies how weak the
inference is.

---

## 8. What the failures collectively imply

Assembling the constraints, a proof of RH must:

1. use the Euler product *and* the functional equation, in a way that visibly
   fails for Davenport–Heilbronn (§0);
2. be sharp rather than soft, since `Λ = 0` exactly and no averaging argument
   can see that (§0);
3. avoid pure sieve methods, which are provably parity-blind (§6);
4. not be a density or proportion argument, which cannot reach "every zero" (§5);
5. supply the positivity that Weil's proof gets from the Hodge index theorem on
   a surface — from somewhere else entirely, since the surface does not exist
   over `Z` (§1, §3).

Item 5 is the crux. Every serious modern programme — Connes–Consani, Deninger,
`F₁` geometry, Arakelov theory — is an attempt to manufacture the missing
geometric object. That is where the problem actually lives.

It is also why the honest assessment is pessimistic in the short term. The
obstruction is not a missing estimate or an unnoticed trick. It is a missing
mathematical *world*, and building one is a generational undertaking whose
completion nobody can currently see.

---

*Continue to [`03-strength-of-evidence.md`](03-strength-of-evidence.md) — how
much the numerical evidence is actually worth, computed rather than asserted.*
