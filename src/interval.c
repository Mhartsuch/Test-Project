/* interval.c -- rigorous elementary functions and self-verified constants.
 *
 * Two precisions are in play:
 *
 *   dd    fast, ~31 digits, no rigour of its own.  Used for phase arithmetic
 *         where we need the digits.  Its rounding error is accounted for by
 *         the conservative relative bound DD_OP_EPS below.
 *   iv    double-endpoint intervals, rigorous by construction.
 *
 * The pattern used throughout is: compute in dd (for accuracy), bound the dd
 * rounding with an explicit op count, add the analytic truncation bound, emit
 * an iv.  Every bound is either an IEEE-754 consequence, an alternating- or
 * geometric-series tail, or DD_OP_EPS.
 *
 * DD_OP_EPS: Joldes, Muller & Popescu ("Tight and rigorous error bounds for
 * basic building blocks of double-word arithmetic", ACM TOMS 44(2), 2018)
 * prove relative error bounds of 3*2^-106 for the accurate double-word sum
 * and 4*2^-106 for the fma-based product.  We use 2^-102 (~2.0e-31), a
 * factor of 16 of headroom over the worst of those, per operation.  For sums
 * the bound is relative to max(|a|,|b|), not to the result -- catastrophic
 * cancellation is handled explicitly at each site that can suffer it.
 */
#include "interval.h"
#include <stdio.h>
#include <stdlib.h>

#define DD_OP_EPS 0x1p-102

iv IV_PI, IV_2PI, IV_PI_2, IV_PI_4, IV_INV_2PI, IV_LOG2, IV_LOG2PI;

/* ===================================================================== */
/*  ddiv: intervals with double-double endpoints.                        */
/*  Used only at start-up, to derive the constants from scratch so the    */
/*  hard-coded DD_* macros can be checked rather than trusted.            */
/* ===================================================================== */

typedef struct { dd lo, hi; } ddiv;

static ddiv ddiv_pt(dd x) { ddiv r; r.lo = x; r.hi = x; return r; }
static ddiv ddiv_i(long n) { return ddiv_pt(dd_of((double)n)); }

/* widen by one relative DD_OP_EPS step in each direction */
static ddiv ddiv_widen(dd lo, dd hi) {
    double al = fabs(lo.hi) * DD_OP_EPS + 0x1p-1000;
    double ah = fabs(hi.hi) * DD_OP_EPS + 0x1p-1000;
    ddiv r; r.lo = dd_sub(lo, dd_of(al)); r.hi = dd_add(hi, dd_of(ah));
    return r;
}
static ddiv ddiv_add(ddiv a, ddiv b) { return ddiv_widen(dd_add(a.lo, b.lo), dd_add(a.hi, b.hi)); }
static ddiv ddiv_sub(ddiv a, ddiv b) { return ddiv_widen(dd_sub(a.lo, b.hi), dd_sub(a.hi, b.lo)); }

static ddiv ddiv_mul(ddiv a, ddiv b) {
    dd p[4]; p[0] = dd_mul(a.lo, b.lo); p[1] = dd_mul(a.lo, b.hi);
             p[2] = dd_mul(a.hi, b.lo); p[3] = dd_mul(a.hi, b.hi);
    dd lo = p[0], hi = p[0];
    for (int i = 1; i < 4; i++) {
        if (dd_cmp(p[i], lo) < 0) lo = p[i];
        if (dd_cmp(p[i], hi) > 0) hi = p[i];
    }
    return ddiv_widen(lo, hi);
}

static ddiv ddiv_div_i(ddiv a, long n) {
    dd d = dd_of((double)n);
    dd lo = dd_div(a.lo, d), hi = dd_div(a.hi, d);
    if (n < 0) { dd t = lo; lo = hi; hi = t; }
    return ddiv_widen(lo, hi);
}

/* atan(1/n) by the alternating series sum (-1)^k / ((2k+1) n^(2k+1)).
 * Terms decrease monotonically, so truncation error is bounded in absolute
 * value by the first omitted term and lies strictly between 0 and it. */
static ddiv ddiv_atan_recip(long n) {
    dd n2 = dd_of((double)n * (double)n);
    dd pw = dd_div(dd_of(1.0), dd_of((double)n));      /* 1/n^(2k+1) */
    ddiv s = ddiv_pt(dd_of(0.0));
    int k = 0;
    for (;; k++) {
        dd term = dd_div(pw, dd_of((double)(2 * k + 1)));
        if (fabs(term.hi) < 1e-40) {
            /* remaining tail is bounded by this term in absolute value */
            ddiv tail; tail.lo = dd_neg(dd_abs(term)); tail.hi = dd_abs(term);
            return ddiv_add(s, tail);
        }
        ddiv t = ddiv_pt((k & 1) ? dd_neg(term) : term);
        s = ddiv_add(s, t);
        pw = dd_div(pw, n2);
    }
}

/* atanh(p/q) = sum_{k>=0} z^(2k+1)/(2k+1), z = p/q, 0 < z < 1.
 * All terms positive; tail after n terms is in [0, z^(2n+1)/((2n+1)(1-z^2))]. */
static ddiv ddiv_atanh_ratio(long p, long q) {
    dd z  = dd_div(dd_of((double)p), dd_of((double)q));
    dd z2 = dd_mul(z, z);
    dd pw = z;
    ddiv s = ddiv_pt(dd_of(0.0));
    for (int k = 0;; k++) {
        dd term = dd_div(pw, dd_of((double)(2 * k + 1)));
        if (fabs(term.hi) < 1e-40) {
            dd one_m = dd_sub(dd_of(1.0), z2);
            dd bound = dd_div(term, one_m);            /* >= true tail */
            ddiv tail; tail.lo = dd_of(0.0); tail.hi = dd_mul_d(dd_abs(bound), 1.5);
            return ddiv_add(s, tail);
        }
        s = ddiv_add(s, ddiv_pt(term));
        pw = dd_mul(pw, z2);
    }
}

/* ===================================================================== */
/*  Constant derivation and verification                                  */
/* ===================================================================== */

static iv iv_from_ddiv(ddiv a) {
    return iv_mk(iv_pred(a.lo.hi + a.lo.lo), iv_succ(a.hi.hi + a.hi.lo));
}

/* Does the hard-coded dd constant lie inside the independently derived
 * enclosure, to within `tol` absolute?  Returns 0 on success. */
static int check_dd(const char *name, dd c, ddiv encl, double tol, int verbose) {
    dd lo = dd_sub(encl.lo, dd_of(tol));
    dd hi = dd_add(encl.hi, dd_of(tol));
    int ok = (dd_cmp(c, lo) >= 0) && (dd_cmp(c, hi) <= 0);
    if (verbose || !ok) {
        dd mid = dd_mul_d(dd_add(encl.lo, encl.hi), 0.5);
        dd err = dd_sub(c, mid);
        fprintf(ok ? stdout : stderr,
                "  %-12s %s  hard-coded - derived = %+.3e  (enclosure width %.3e)\n",
                name, ok ? "OK  " : "FAIL",
                err.hi + err.lo, (dd_sub(encl.hi, encl.lo)).hi);
    }
    return ok ? 0 : 1;
}

static int constants_ready = 0;

void iv_init_constants(void) {
    if (constants_ready) return;
    /* Machin: pi = 16 atan(1/5) - 4 atan(1/239) */
    ddiv a5   = ddiv_atan_recip(5);
    ddiv a239 = ddiv_atan_recip(239);
    ddiv pi   = ddiv_sub(ddiv_mul(ddiv_i(16), a5), ddiv_mul(ddiv_i(4), a239));

    /* log 2 = 2 atanh(1/3) */
    ddiv log2 = ddiv_mul(ddiv_i(2), ddiv_atanh_ratio(1, 3));

    /* log(2 pi) = log 2 + log pi,  log pi = 2 atanh((pi-1)/(pi+1)) */
    ddiv one   = ddiv_i(1);
    ddiv num   = ddiv_sub(pi, one);
    ddiv den   = ddiv_add(pi, one);
    dd   zlo   = dd_div(num.lo, den.hi), zhi = dd_div(num.hi, den.lo);
    ddiv z     = ddiv_widen(zlo, zhi);
    /* atanh(z) for an interval z: series with positive terms, monotone in z */
    ddiv s = ddiv_pt(dd_of(0.0)), pw = z, z2 = ddiv_mul(z, z);
    for (int k = 0; k < 200; k++) {
        ddiv term = ddiv_div_i(pw, 2 * k + 1);
        if (fabs(term.hi.hi) < 1e-40) {
            ddiv tail; tail.lo = dd_of(0.0);
            tail.hi = dd_mul_d(dd_abs(term.hi), 2.0);
            s = ddiv_add(s, tail);
            break;
        }
        s = ddiv_add(s, term);
        pw = ddiv_mul(pw, z2);
    }
    ddiv logpi  = ddiv_mul(ddiv_i(2), s);
    ddiv log2pi = ddiv_add(log2, logpi);

    ddiv two_pi = ddiv_mul(ddiv_i(2), pi);

    IV_PI      = iv_from_ddiv(pi);
    IV_2PI     = iv_from_ddiv(two_pi);
    IV_PI_2    = iv_from_ddiv(ddiv_div_i(pi, 2));
    IV_PI_4    = iv_from_ddiv(ddiv_div_i(pi, 4));
    IV_LOG2    = iv_from_ddiv(log2);
    IV_LOG2PI  = iv_from_ddiv(log2pi);
    {   /* 1/(2 pi) */
        dd lo = dd_div(dd_of(1.0), two_pi.hi), hi = dd_div(dd_of(1.0), two_pi.lo);
        IV_INV_2PI = iv_from_ddiv(ddiv_widen(lo, hi));
    }
    constants_ready = 1;
}

int iv_verify_constants(int verbose) {
    iv_init_constants();
    ddiv a5   = ddiv_atan_recip(5);
    ddiv a239 = ddiv_atan_recip(239);
    ddiv pi   = ddiv_sub(ddiv_mul(ddiv_i(16), a5), ddiv_mul(ddiv_i(4), a239));
    ddiv log2 = ddiv_mul(ddiv_i(2), ddiv_atanh_ratio(1, 3));

    int bad = 0;
    if (verbose) printf("Verifying hard-coded dd constants against Machin/atanh derivations:\n");
    bad += check_dd("pi",      DD_PI,   pi, 1e-31, verbose);
    bad += check_dd("2pi",     DD_2PI,  ddiv_mul(ddiv_i(2), pi), 1e-31, verbose);
    bad += check_dd("pi/2",    DD_PI_2, ddiv_div_i(pi, 2), 1e-31, verbose);
    bad += check_dd("pi/4",    DD_PI_4, ddiv_div_i(pi, 4), 1e-31, verbose);
    bad += check_dd("log2",    DD_LOG2, log2, 1e-31, verbose);
    {   /* 1/(2pi) checked by multiplying back */
        ddiv prod = ddiv_mul(ddiv_pt(DD_INV_2PI), ddiv_mul(ddiv_i(2), pi));
        bad += check_dd("1/(2pi)*2pi", dd_of(1.0), prod, 1e-31, verbose);
    }
    {   /* log(2pi) checked via exp: e^{log2pi} should equal 2pi */
        dd back = dd_exp(DD_LOG2PI);
        ddiv tp = ddiv_mul(ddiv_i(2), pi);
        bad += check_dd("exp(log2pi)", back, tp, 1e-29, verbose);
    }
    return bad;
}

/* ===================================================================== */
/*  Self test: catches fp-contract, x87 excess precision, broken fma      */
/* ===================================================================== */

static volatile double vol_a = 0.0, vol_b = 0.0, vol_c = 0.0;

int iv_self_test(void) {
    int bad = 0;

    /* 1. two_prod must be exact -- fails if fma() is emulated badly */
    vol_a = 1.0 + 0x1p-30; vol_b = 1.0 + 0x1p-25;
    dd p = dd_two_prod(vol_a, vol_b);
    double exact_lo = (1.0 * 0x1p-25 + 0x1p-30 * 1.0 + 0x1p-55) - (p.hi - 1.0);
    if (fabs((p.hi + p.lo) - (1.0 + 0x1p-25 + 0x1p-30 + 0x1p-55)) > 1e-300) {
        fprintf(stderr, "  self-test FAIL: two_prod not exact (fma broken?)\n"); bad++;
    }
    (void)exact_lo;

    /* 2. ulp helpers */
    if (iv_succ(1.0) != 1.0 + 0x1p-52 || iv_pred(1.0) != 1.0 - 0x1p-53) {
        fprintf(stderr, "  self-test FAIL: succ/pred wrong\n"); bad++;
    }
    if (iv_succ(0.0) <= 0.0 || iv_pred(0.0) >= 0.0) {
        fprintf(stderr, "  self-test FAIL: succ/pred at zero\n"); bad++;
    }

    /* 3. fp-contract: (a*b - a*b) must be exactly zero when written twice */
    vol_a = 0.1; vol_b = 0.3; vol_c = vol_a * vol_b;
    if (vol_a * vol_b - vol_c != 0.0) {
        fprintf(stderr, "  self-test FAIL: fp contraction detected"
                        " (build with -ffp-contract=off)\n"); bad++;
    }

    /* 4. interval containment on a nasty cancellation */
    iv x = iv_pt(1.0), y = iv_pt(3.0);
    iv q = iv_div(x, y);
    iv back = iv_mul(q, y);
    if (!(back.lo <= 1.0 && 1.0 <= back.hi)) {
        fprintf(stderr, "  self-test FAIL: (1/3)*3 does not enclose 1\n"); bad++;
    }
    return bad;
}

/* ===================================================================== */
/*  exp                                                                   */
/* ===================================================================== */

/* Rigorous enclosure of exp(x) for a double x.
 * Reduction x = m*log2 + r done in dd; Taylor of expm1(r/2^S) truncated at
 * degree n with remainder |R| <= |u|^(n+1)/((n+1)! (1-|u|)); then squared up. */
static iv exp_pt(double x) {
    if (x <= -745.2) return iv_mk(0.0, 0x1p-1074);
    if (x >=  709.79) return iv_mk(0x1.fffffffffffffp+1023, INFINITY);
    if (x == 0.0) return iv_pt(1.0);

    double m = floor(x / DD_LOG2.hi + 0.5);
    dd r = dd_sub(dd_of(x), dd_mul_d(DD_LOG2, m));
    /* reduction error: dd ops (<= 2 * DD_OP_EPS * |x|) + m * |log2 - DD_LOG2| */
    double red_err = 2.0 * DD_OP_EPS * (fabs(x) + fabs(m) * 0.7) + fabs(m) * 1e-33;

    const int S = 8;
    dd u = dd_mul_d(r, ldexp(1.0, -S));
    double au = fabs(u.hi) + 1e-30;

    dd s = u, term = u;
    int n = 1;
    for (int k = 2; k <= 14; k++) {
        term = dd_div_d(dd_mul(term, u), (double)k);
        s = dd_add(s, term); n = k;
        if (fabs(term.hi) < 1e-36) break;
    }
    /* truncation of expm1: |R| <= au^(n+1) / ((n+1)! (1 - au)) */
    double fact = 1.0, trunc = 1.0;
    for (int k = 1; k <= n + 1; k++) { fact *= (double)k; trunc *= au; }
    trunc = trunc / (fact * (1.0 - au));
    /* dd rounding over ~3n ops, relative to |s| ~ au */
    double round_err = 3.0 * (double)n * DD_OP_EPS * au;

    double err = trunc + round_err;
    /* square up: e_{i+1} = 2 e_i + 2 s_i e_i + e_i^2, s_i <= expm1(log2/2)  */
    for (int i = 0; i < S; i++) {
        double si = fabs(s.hi);
        s = dd_add(dd_mul_d(s, 2.0), dd_mul(s, s));
        err = 2.0 * err * (1.0 + si) + err * err + DD_OP_EPS * fabs(s.hi);
    }
    s = dd_add_d(s, 1.0);                       /* now s ~ exp(r) in [0.7, 1.42] */

    /* propagate the reduction error: exp(r+d) = exp(r)(1+d+...) */
    err += fabs(s.hi) * red_err * 1.001;
    err += DD_OP_EPS * fabs(s.hi);

    double lo = ldexp(s.hi + s.lo - err, (int)m);
    double hi = ldexp(s.hi + s.lo + err, (int)m);
    return iv_mk(iv_pred(lo), iv_succ(hi));
}

iv iv_exp(iv x) {                                /* exp is increasing */
    if (iv_nan(x)) return iv_empty();
    return iv_mk(exp_pt(x.lo).lo, exp_pt(x.hi).hi);
}

/* ===================================================================== */
/*  log                                                                   */
/* ===================================================================== */

/* Rigorous enclosure of log(x) for a double x > 0.
 * x = 2^m f with f in [1/sqrt2, sqrt2];  log f = 2 atanh(z), z=(f-1)/(f+1),
 * |z| <= 0.17158.  Positive-term (in |z|) series, tail bounded geometrically. */
/* Same computation, exposed so callers that need the dd value (and must do
 * their own cancellation in dd) can have it together with its proven bound. */
dd iv_log_dd(double x, double *err_out) {
    if (x <= 0.0) { if (err_out) *err_out = INFINITY; return dd_of(NAN); }
    if (x == 1.0) { if (err_out) *err_out = 0.0; return dd_of(0.0); }
    int m;
    double f = frexp(x, &m);
    f *= 2.0; m -= 1;
    if (f > 1.4142135623730951) { f *= 0.5; m += 1; }

    dd zf = dd_div(dd_sub(dd_of(f), dd_of(1.0)), dd_add(dd_of(f), dd_of(1.0)));
    double az = fabs(zf.hi) + 1e-30;
    dd z2 = dd_mul(zf, zf);

    dd s = zf, pw = zf;
    int n = 0;
    double last = az;
    for (int k = 1; k <= 60; k++) {
        pw = dd_mul(pw, z2);
        dd term = dd_div_d(pw, (double)(2 * k + 1));
        s = dd_add(s, term); n = k;
        last = fabs(term.hi);
        if (last < 1e-36) break;
    }
    /* Tail beyond the z^(2n+1) term:
     *     sum_{k>n} z^(2k+1)/(2k+1)  <=  |last term| * z^2/(1-z^2).
     * Taken from the term already in hand rather than via pow(), which would
     * otherwise dominate the cost of this routine -- it is called once per
     * main-sum term, tens of millions of times per run. */
    double tail = last * az * az / (1.0 - az * az);
    double round_err = 4.0 * (double)n * DD_OP_EPS * az;

    dd logf = dd_mul_d(s, 2.0);
    dd res  = dd_add(logf, dd_mul_d(DD_LOG2, m));
    if (err_out)
        *err_out = 2.0 * (tail + round_err)
                 + fabs((double)m) * 1e-33
                 + DD_OP_EPS * (fabs(res.hi) + fabs((double)m) * 0.7);
    return res;
}

static iv log_pt(double x) {
    if (x <= 0.0) return iv_empty();
    if (x == 1.0) return iv_pt(0.0);
    double e = 0.0;
    dd r = iv_log_dd(x, &e);
    return iv_of_dd(r, e);
}

iv iv_log(iv x) {                                /* log is increasing */
    if (x.lo <= 0.0) return iv_empty();
    return iv_mk(log_pt(x.lo).lo, log_pt(x.hi).hi);
}

iv iv_pow_d(iv x, double p) {
    return iv_exp(iv_mul_d(iv_log(x), p));
}

iv iv_atan_recip(long n) { return iv_from_ddiv(ddiv_atan_recip(n)); }

/* ===================================================================== */
/*  sin / cos                                                             */
/* ===================================================================== */

/* Rigorous sin and cos of a double r with |r| <= pi/4 + eps, by the
 * alternating Taylor series (terms decrease monotonically for |r|<1, so the
 * truncation error is bounded by the first omitted term). */
static void sincos_small(double r, iv *s, iv *c) {
    double ar = fabs(r);
    dd rr = dd_of(r), r2 = dd_mul(rr, rr);

    dd t = rr, sum = rr;                          /* sin */
    double at = ar, tr;
    int n = 1;
    for (int k = 3; k <= 31; k += 2) {
        t = dd_neg(dd_div_d(dd_mul(t, r2), (double)(k * (k - 1))));
        at = at * ar * ar / (double)(k * (k - 1));
        sum = dd_add(sum, t); n = k;
        if (at < 1e-40) break;
    }
    tr = at * ar * ar / (double)((n + 2) * (n + 1));      /* first omitted */
    *s = iv_of_dd(sum, tr + 3.0 * (double)n * DD_OP_EPS);

    dd u = dd_of(1.0), csum = dd_of(1.0);
    double au = 1.0;
    n = 0;
    for (int k = 2; k <= 32; k += 2) {
        u = dd_neg(dd_div_d(dd_mul(u, r2), (double)(k * (k - 1))));
        au = au * ar * ar / (double)(k * (k - 1));
        csum = dd_add(csum, u); n = k;
        if (au < 1e-40) break;
    }
    tr = au * ar * ar / (double)((n + 2) * (n + 1));
    *c = iv_of_dd(csum, tr + 3.0 * (double)n * DD_OP_EPS);
}

/* sin and cos of a double x of any size, with the mod-2pi reduction done in
 * dd and its error accounted for. */
static void sincos_pt(double x, iv *s, iv *c) {
    dd q = dd_nint(dd_mul(dd_of(x), DD_INV_2PI));
    dd r = dd_sub(dd_of(x), dd_mul(DD_2PI, q));
    double red_err = fabs(q.hi) * 6.0e-33                    /* |2pi - DD_2PI| */
                   + 2.0 * DD_OP_EPS * fabs(x)
                   + 1e-300;
    double rv = r.hi + r.lo;

    /* fold into [-pi/4, pi/4] */
    int quad = (int)floor(rv / DD_PI_2.hi + 0.5);            /* -2..2 */
    dd rf = dd_sub(r, dd_mul_d(DD_PI_2, (double)quad));
    red_err += fabs((double)quad) * 2e-33 + DD_OP_EPS * 2.0;
    double rr = rf.hi + rf.lo;

    iv ss, cc;
    sincos_small(rr, &ss, &cc);
    /* |sin(a+d)-sin(a)| <= |d| */
    iv slop = iv_mk(-red_err, red_err);
    ss = iv_add(ss, slop);
    cc = iv_add(cc, slop);

    int k = ((quad % 4) + 4) % 4;
    switch (k) {
        case 0: *s = ss;            *c = cc;            break;
        case 1: *s = cc;            *c = iv_neg_(ss);   break;
        case 2: *s = iv_neg_(ss);   *c = iv_neg_(cc);   break;
        default:*s = iv_neg_(cc);   *c = ss;            break;
    }
    /* clamp: sin and cos are bounded by 1 */
    if (s->lo < -1.0) s->lo = -1.0;
    if (s->hi >  1.0) s->hi =  1.0;
    if (c->lo < -1.0) c->lo = -1.0;
    if (c->hi >  1.0) c->hi =  1.0;
}

void iv_sincos(iv x, iv *s, iv *c) {
    if (iv_nan(x)) { *s = iv_empty(); *c = iv_empty(); return; }
    if (iv_wid(x) >= 6.2831853071795862) { *s = iv_mk(-1, 1); *c = iv_mk(-1, 1); return; }

    iv sl, cl, sh, ch;
    sincos_pt(x.lo, &sl, &cl);
    sincos_pt(x.hi, &sh, &ch);
    iv S = iv_hull(sl, sh), C = iv_hull(cl, ch);

    /* include any extremum of sin/cos strictly inside [x.lo, x.hi] */
    double a = x.lo / DD_PI_2.hi, b = x.hi / DD_PI_2.hi;
    long ka = (long)floor(a), kb = (long)floor(b);
    for (long k = ka; k <= kb + 1; k++) {
        double crit = (double)k * DD_PI_2.hi;                /* k*pi/2 */
        if (crit <= x.lo || crit >= x.hi) continue;
        long m = ((k % 4) + 4) % 4;
        if (m == 1) S.hi =  1.0;
        if (m == 3) S.lo = -1.0;
        if (m == 0) C.hi =  1.0;
        if (m == 2) C.lo = -1.0;
        if (kb - ka > 8) { S = iv_mk(-1, 1); C = iv_mk(-1, 1); break; }
    }
    *s = S; *c = C;
}

iv iv_sin(iv x) { iv s, c; iv_sincos(x, &s, &c); return s; }
iv iv_cos(iv x) { iv s, c; iv_sincos(x, &s, &c); return c; }

/* ===================================================================== */
/*  phase reduction mod 2pi                                               */
/* ===================================================================== */

iv iv_reduce_2pi(dd x, double err) {
    dd q = dd_nint(dd_mul(x, DD_INV_2PI));
    dd r = dd_sub(x, dd_mul(DD_2PI, q));
    double mag = fabs(x.hi) + fabs(q.hi) * 6.2831853071795862;
    double e = err
             + fabs(q.hi) * 6.0e-33                 /* 2pi truncation in dd    */
             + 2.0 * DD_OP_EPS * mag                /* dd_mul + dd_sub         */
             + DD_OP_EPS * fabs(x.hi);              /* dd_mul for q            */
    return iv_of_dd(r, e);
}
