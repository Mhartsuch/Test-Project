/* interval.h -- rigorous interval arithmetic over IEEE-754 binary64.
 *
 * Invariant for every iv value v: the mathematically exact quantity it
 * represents lies in the closed interval [v.lo, v.hi].  Every operation
 * below preserves that invariant.
 *
 * Rounding strategy.  Rather than switching the FPU rounding mode (fragile
 * under optimisation and hard to audit), we exploit the IEEE-754 guarantee
 * that +, -, *, / and sqrt are *correctly rounded to nearest*: if r is the
 * computed result then the exact result lies within half an ulp of r, hence
 * certainly within [pred(r), succ(r)].  So we compute round-to-nearest and
 * widen by one ulp in each direction.  This costs at most one extra ulp of
 * width per operation and is valid regardless of the ambient rounding mode.
 *
 * REQUIREMENT: build with -ffp-contract=off so the compiler cannot fuse
 * a*b+c into an fma and invalidate the "each written operation is correctly
 * rounded" premise.  iv_self_test() checks this at runtime.
 */
#ifndef ZETA_INTERVAL_H
#define ZETA_INTERVAL_H

#include <math.h>
#include <string.h>
#include <stdint.h>
#include "dd.h"

typedef struct { double lo, hi; } iv;

/* ---- next/previous representable double (fast, branch-light) ------------ */

static inline double iv_succ(double x) {
    if (!(x == x)) return x;                     /* NaN */
    if (x == INFINITY) return x;
    if (x == 0.0) return 0x1p-1074;              /* smallest positive subnormal */
    uint64_t u; memcpy(&u, &x, 8);
    if (x > 0.0) u += 1; else u -= 1;
    double r; memcpy(&r, &u, 8); return r;
}

static inline double iv_pred(double x) {
    if (!(x == x)) return x;
    if (x == -INFINITY) return x;
    if (x == 0.0) return -0x1p-1074;
    uint64_t u; memcpy(&u, &x, 8);
    if (x > 0.0) u -= 1; else u += 1;
    double r; memcpy(&r, &u, 8); return r;
}

/* ---- construction ------------------------------------------------------- */

static inline iv iv_mk(double lo, double hi) { iv r; r.lo = lo; r.hi = hi; return r; }
static inline iv iv_pt(double x)             { return iv_mk(x, x); }
static inline iv iv_empty(void)              { return iv_mk(NAN, NAN); }
static inline iv iv_all(void)                { return iv_mk(-INFINITY, INFINITY); }

/* An enclosure of the dd value x, widened by an absolute error bound err
 * (use err = 0 when x is exact, e.g. a small integer). */
static inline iv iv_of_dd(dd x, double err) {
    double c = x.hi + x.lo;                      /* one rounding */
    double slop = iv_succ(fabs(c)) - fabs(c);    /* >= 1 ulp of c */
    double e = err + slop + fabs((x.hi - c) + x.lo);
    return iv_mk(iv_pred(c - e), iv_succ(c + e));
}

/* ---- queries ------------------------------------------------------------ */

static inline double iv_mid(iv a)   { return 0.5 * (a.lo + a.hi); }
static inline double iv_rad(iv a)   { return iv_succ(0.5 * (a.hi - a.lo)); }
static inline double iv_wid(iv a)   { return iv_succ(a.hi - a.lo); }
static inline int iv_has0(iv a)     { return a.lo <= 0.0 && 0.0 <= a.hi; }
static inline int iv_pos(iv a)      { return a.lo > 0.0; }
static inline int iv_neg(iv a)      { return a.hi < 0.0; }
static inline int iv_nan(iv a)      { return !(a.lo == a.lo) || !(a.hi == a.hi); }
/* Sign, but only when it is rigorously determined: +1, -1, or 0 = unknown. */
static inline int iv_sign(iv a)     { return iv_pos(a) ? 1 : (iv_neg(a) ? -1 : 0); }

static inline iv iv_hull(iv a, iv b) {
    return iv_mk(a.lo < b.lo ? a.lo : b.lo, a.hi > b.hi ? a.hi : b.hi);
}

/* ---- arithmetic --------------------------------------------------------- */

static inline iv iv_neg_(iv a) { return iv_mk(-a.hi, -a.lo); }

static inline iv iv_add(iv a, iv b) {
    return iv_mk(iv_pred(a.lo + b.lo), iv_succ(a.hi + b.hi));
}
static inline iv iv_sub(iv a, iv b) {
    return iv_mk(iv_pred(a.lo - b.hi), iv_succ(a.hi - b.lo));
}
static inline iv iv_add_d(iv a, double b) {
    return iv_mk(iv_pred(a.lo + b), iv_succ(a.hi + b));
}

static inline iv iv_mul(iv a, iv b) {
    double p1 = a.lo * b.lo, p2 = a.lo * b.hi, p3 = a.hi * b.lo, p4 = a.hi * b.hi;
    double lo = p1, hi = p1;
    if (p2 < lo) lo = p2;
    if (p2 > hi) hi = p2;
    if (p3 < lo) lo = p3;
    if (p3 > hi) hi = p3;
    if (p4 < lo) lo = p4;
    if (p4 > hi) hi = p4;
    return iv_mk(iv_pred(lo), iv_succ(hi));
}

static inline iv iv_mul_d(iv a, double b) {
    double p1 = a.lo * b, p2 = a.hi * b;
    return (p1 <= p2) ? iv_mk(iv_pred(p1), iv_succ(p2))
                      : iv_mk(iv_pred(p2), iv_succ(p1));
}

static inline iv iv_div(iv a, iv b) {
    if (iv_has0(b)) return iv_all();
    double p1 = a.lo / b.lo, p2 = a.lo / b.hi, p3 = a.hi / b.lo, p4 = a.hi / b.hi;
    double lo = p1, hi = p1;
    if (p2 < lo) lo = p2;
    if (p2 > hi) hi = p2;
    if (p3 < lo) lo = p3;
    if (p3 > hi) hi = p3;
    if (p4 < lo) lo = p4;
    if (p4 > hi) hi = p4;
    return iv_mk(iv_pred(lo), iv_succ(hi));
}

static inline iv iv_sqr(iv a) {
    if (a.lo >= 0.0) return iv_mk(iv_pred(a.lo * a.lo), iv_succ(a.hi * a.hi));
    if (a.hi <= 0.0) return iv_mk(iv_pred(a.hi * a.hi), iv_succ(a.lo * a.lo));
    double m = fabs(a.lo) > fabs(a.hi) ? fabs(a.lo) : fabs(a.hi);
    return iv_mk(0.0, iv_succ(m * m));
}

static inline iv iv_sqrt(iv a) {
    if (a.hi < 0.0) return iv_empty();
    double lo = a.lo > 0.0 ? sqrt(a.lo) : 0.0;
    return iv_mk(iv_pred(lo), iv_succ(sqrt(a.hi)));
}

static inline iv iv_abs(iv a) {
    if (a.lo >= 0.0) return a;
    if (a.hi <= 0.0) return iv_neg_(a);
    double m = fabs(a.lo) > fabs(a.hi) ? fabs(a.lo) : fabs(a.hi);
    return iv_mk(0.0, m);
}

/* ---- rigorous constants (computed once, see interval.c) ----------------- */
extern iv IV_PI, IV_2PI, IV_PI_2, IV_PI_4, IV_INV_2PI, IV_LOG2, IV_LOG2PI;
void iv_init_constants(void);
int  iv_self_test(void);       /* returns 0 on success */

/* ---- rigorous elementary functions (interval.c) -------------------------- */
iv iv_exp(iv x);
iv iv_log(iv x);               /* requires x.lo > 0 */
iv iv_atan_recip(long n);      /* atan(1/n), n >= 1 integer -- used for pi */
void iv_sincos(iv x, iv *s, iv *c);
iv iv_sin(iv x);
iv iv_cos(iv x);
iv iv_pow_d(iv x, double p);   /* x^p for x.lo > 0 */

/* Rigorous reduction of a dd phase modulo 2*pi into an enclosure of the
 * residue in [-pi, pi].  `err` is a bound on the absolute error already
 * present in `x` relative to the exact phase it stands for. */
iv iv_reduce_2pi(dd x, double err);

#endif /* ZETA_INTERVAL_H */
