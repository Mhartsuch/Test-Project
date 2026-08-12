/* dd.h -- double-double arithmetic (~106 bit significand, ~31 decimal digits).
 *
 * Why this exists: at height t = 10^15 the Riemann-Siegel main sum needs the
 * phase t*log(k) reduced mod 2*pi.  That product is of size ~1.6e16, so an
 * absolute phase accuracy of 1e-13 demands ~30 significant digits.  IEEE
 * double (~16 digits) is roughly 14 digits short; double-double clears it
 * with margin.
 *
 * Algorithms are the standard error-free transformations (Dekker, Knuth,
 * Shewchuk) as packaged in Bailey's QD library.  Every routine here assumes
 * IEEE-754 binary64 with round-to-nearest-even and *no* FMA contraction of
 * the expressions written below (build with -ffp-contract=off).  The explicit
 * fma() call in two_prod is intentional and required.
 */
#ifndef ZETA_DD_H
#define ZETA_DD_H

#include <math.h>

typedef struct { double hi, lo; } dd;

static inline dd dd_mk(double hi, double lo) { dd r; r.hi = hi; r.lo = lo; return r; }
static inline dd dd_of(double a)             { return dd_mk(a, 0.0); }
static inline double dd_d(dd a)              { return a.hi; }

/* ---- error-free transformations ---------------------------------------- */

/* exact: a + b = s + e, no assumption on magnitudes */
static inline dd dd_two_sum(double a, double b) {
    double s  = a + b;
    double bb = s - a;
    double e  = (a - (s - bb)) + (b - bb);
    return dd_mk(s, e);
}

/* exact: a + b = s + e, requires |a| >= |b| (or a == 0) */
static inline dd dd_quick_two_sum(double a, double b) {
    double s = a + b;
    double e = b - (s - a);
    return dd_mk(s, e);
}

/* exact: a * b = p + e  (needs a correctly-rounded fma) */
static inline dd dd_two_prod(double a, double b) {
    double p = a * b;
    double e = fma(a, b, -p);
    return dd_mk(p, e);
}

/* ---- arithmetic --------------------------------------------------------- */

static inline dd dd_neg(dd a) { return dd_mk(-a.hi, -a.lo); }

static inline dd dd_add(dd a, dd b) {
    dd s = dd_two_sum(a.hi, b.hi);
    dd t = dd_two_sum(a.lo, b.lo);
    s.lo += t.hi;
    s = dd_quick_two_sum(s.hi, s.lo);
    s.lo += t.lo;
    s = dd_quick_two_sum(s.hi, s.lo);
    return s;
}

static inline dd dd_add_d(dd a, double b) {
    dd s = dd_two_sum(a.hi, b);
    s.lo += a.lo;
    return dd_quick_two_sum(s.hi, s.lo);
}

static inline dd dd_sub(dd a, dd b)      { return dd_add(a, dd_neg(b)); }
static inline dd dd_sub_d(dd a, double b){ return dd_add_d(a, -b); }

static inline dd dd_mul(dd a, dd b) {
    dd p = dd_two_prod(a.hi, b.hi);
    p.lo += a.hi * b.lo + a.lo * b.hi;
    return dd_quick_two_sum(p.hi, p.lo);
}

static inline dd dd_mul_d(dd a, double b) {
    dd p = dd_two_prod(a.hi, b);
    p.lo += a.lo * b;
    return dd_quick_two_sum(p.hi, p.lo);
}

static inline dd dd_div(dd a, dd b) {
    double q1 = a.hi / b.hi;
    dd r = dd_sub(a, dd_mul_d(b, q1));
    double q2 = r.hi / b.hi;
    r = dd_sub(r, dd_mul_d(b, q2));
    double q3 = r.hi / b.hi;
    dd q = dd_quick_two_sum(q1, q2);
    return dd_add_d(q, q3);
}

static inline dd dd_div_d(dd a, double b) { return dd_div(a, dd_of(b)); }

static inline dd dd_sqrt(dd a) {
    if (a.hi <= 0.0) return dd_of(0.0);
    /* Newton step on x = 1/sqrt(a), then multiply -- avoids a dd division. */
    double x = 1.0 / sqrt(a.hi);
    double ax = a.hi * x;
    dd t = dd_sub(a, dd_two_prod(ax, ax));
    return dd_add_d(dd_of(ax), t.hi * x * 0.5);
}

/* ---- rounding / comparison ---------------------------------------------- */

static inline double dd_nint_d(double d) {
    double f = floor(d + 0.5);
    if (f - d == 0.5 && fmod(f, 2.0) != 0.0) f -= 1.0;   /* ties to even */
    return f;
}

static inline dd dd_nint(dd a) {
    double hi = dd_nint_d(a.hi), lo = 0.0;
    if (hi == a.hi) {                    /* hi is exact, round lo */
        lo = dd_nint_d(a.lo);
        return dd_quick_two_sum(hi, lo);
    }
    if (fabs(hi - a.hi) == 0.5 && a.lo < 0.0) hi -= 1.0;
    return dd_mk(hi, 0.0);
}

static inline dd dd_floor(dd a) {
    double hi = floor(a.hi);
    if (hi == a.hi) return dd_quick_two_sum(hi, floor(a.lo));
    return dd_mk(hi, 0.0);
}

static inline int dd_cmp(dd a, dd b) {
    if (a.hi < b.hi) return -1;
    if (a.hi > b.hi) return  1;
    if (a.lo < b.lo) return -1;
    if (a.lo > b.lo) return  1;
    return 0;
}
static inline dd dd_abs(dd a) { return (a.hi < 0.0) ? dd_neg(a) : a; }

/* ---- constants (correctly rounded to dd; low word is the residual) ------- */
/* These are verified at startup against independently computed rigorous
 * interval enclosures -- see iv_check_constants() in interval.c. */
#define DD_PI       dd_mk( 3.141592653589793116e+00,  1.224646799147353207e-16)
#define DD_2PI      dd_mk( 6.283185307179586232e+00,  2.449293598294706414e-16)
#define DD_PI_2     dd_mk( 1.570796326794896558e+00,  6.123233995736766036e-17)
#define DD_PI_4     dd_mk( 7.853981633974482790e-01,  3.061616997868383018e-17)
#define DD_INV_2PI  dd_mk( 1.591549430918953456e-01, -9.839338337591242941e-18)
#define DD_LOG2     dd_mk( 6.931471805599452862e-01,  2.319046813846299558e-17)
#define DD_LOG2PI   dd_mk( 1.837877066409345561e+00, -7.756588316134482900e-17)
#define DD_E        dd_mk( 2.718281828459045091e+00,  1.445646891729250158e-16)
#define DD_SQRT2PI  dd_mk( 2.506628274631000686e+00, -1.832857998045916677e-16)

/* ---- transcendentals ---------------------------------------------------- */

/* exp(a).  Argument reduction a = m*log2 + r with |r| <= log2/2, then r is
 * halved DD_EXP_SQ times so |r'| <= log2/2^(DD_EXP_SQ+1) ~ 1.4e-3 and the
 * Taylor series converges in ~9 terms; finally square back up. */
#define DD_EXP_SQ 8

static inline dd dd_exp(dd a) {
    if (a.hi <= -745.2) return dd_of(0.0);
    if (a.hi >=  709.8) return dd_of(INFINITY);
    if (a.hi == 0.0 && a.lo == 0.0) return dd_of(1.0);

    double m = floor(a.hi / DD_LOG2.hi + 0.5);
    dd r = dd_sub(a, dd_mul_d(DD_LOG2, m));
    r = dd_mul_d(r, ldexp(1.0, -DD_EXP_SQ));

    /* Taylor: sum r^k/k!  (|r| <= 1.36e-3 => 9 terms give < 1e-34 relative) */
    dd s = r, term = r;
    for (int k = 2; k <= 10; k++) {
        term = dd_mul(term, r);
        term = dd_div_d(term, (double)k);
        s = dd_add(s, term);
        if (fabs(term.hi) < 1e-36 * fabs(s.hi) + 1e-320) break;
    }
    /* s = expm1(r); square up: expm1(2x) = 2*expm1(x) + expm1(x)^2 */
    for (int i = 0; i < DD_EXP_SQ; i++)
        s = dd_add(dd_mul_d(s, 2.0), dd_mul(s, s));
    s = dd_add_d(s, 1.0);

    return dd_mk(ldexp(s.hi, (int)m), ldexp(s.lo, (int)m));
}

/* log(a) by one Newton step on the double approximation, iterated twice:
 *   y <- y + a*exp(-y) - 1
 * Each step squares the error, so 16 digits -> 32 digits -> converged. */
static inline dd dd_log(dd a) {
    if (a.hi <= 0.0) return dd_of(NAN);
    if (a.hi == 1.0 && a.lo == 0.0) return dd_of(0.0);
    dd y = dd_of(log(a.hi));
    for (int i = 0; i < 2; i++) {
        dd e = dd_exp(dd_neg(y));
        y = dd_add(y, dd_sub_d(dd_mul(a, e), 1.0));
    }
    return y;
}

/* sin/cos for |a| <= pi/4 by direct Taylor (alternating, fast). */
static inline void dd_sincos_small(dd a, dd *s, dd *c) {
    dd a2 = dd_mul(a, a);
    dd t = a, sum = a;
    for (int k = 3; k <= 25; k += 2) {                 /* sin */
        t = dd_mul(t, a2);
        t = dd_div_d(t, (double)(k * (k - 1)));
        t = dd_neg(t);
        sum = dd_add(sum, t);
        if (fabs(t.hi) < 1e-36) break;
    }
    *s = sum;
    /* cos from sin to keep the Pythagorean identity tight */
    dd c2 = dd_sub_d(dd_mul(sum, sum), 1.0);           /* sin^2 - 1 */
    *c = dd_sqrt(dd_neg(c2));
}

/* sin/cos of an arbitrary dd angle: reduce mod 2*pi, then by octant. */
static inline void dd_sincos(dd a, dd *sr, dd *cr) {
    dd q = dd_nint(dd_mul(a, DD_INV_2PI));
    dd r = dd_sub(a, dd_mul(DD_2PI, q));               /* |r| <= pi */

    /* fold into |r| <= pi/4 recording the octant */
    int neg_s = 0, neg_c = 0, swap = 0;
    if (r.hi < 0) { r = dd_neg(r); neg_s = 1; }        /* r in [0, pi] */
    if (dd_cmp(r, DD_PI_2) > 0) { r = dd_sub(DD_PI, r); neg_c = 1; }  /* [0, pi/2] */
    if (dd_cmp(r, DD_PI_4) > 0) { r = dd_sub(DD_PI_2, r); swap = 1; } /* [0, pi/4] */

    dd s, c;
    dd_sincos_small(r, &s, &c);
    if (swap)  { dd tmp = s; s = c; c = tmp; }
    if (neg_c) { c = dd_neg(c); }
    if (neg_s) { s = dd_neg(s); }
    *sr = s; *cr = c;
}

/* Reduce x mod 2*pi into [-pi, pi] and return it as a plain double.
 * This is the workhorse for Riemann-Siegel phases: x may be ~1e16 while the
 * result must be accurate to ~1e-16 absolute. */
static inline double dd_mod_2pi(dd x) {
    dd q = dd_nint(dd_mul(x, DD_INV_2PI));
    dd r = dd_sub(x, dd_mul(DD_2PI, q));
    return r.hi + r.lo;
}

#endif /* ZETA_DD_H */
