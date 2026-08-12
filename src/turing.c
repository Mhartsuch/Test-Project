#include "turing.h"
#include <stdio.h>
#include <stdlib.h>
#include <math.h>

/* exact dd from a 64-bit integer (n can exceed 2^53) */
static dd dd_of_ll_t(long long n) {
    double hi = (double)n;
    double lo = (double)(n - (long long)hi);
    return dd_quick_two_sum(hi, lo);
}

double turing_S_bound(double t2) {
    if (t2 < 6.283185307179586) t2 = 6.283185307179586;
    return 2.30 + 0.128 * log(t2 / 6.283185307179586232);
}

/* Int theta dt = (t^2/4) log(t/2pi) - 3t^2/8 - pi t/8 + (log t)/48
 *                - 7/(11520 t^2) - 31/(322560 t^4) - ...
 * (term-by-term antiderivative of the asymptotic series in rs_theta).
 *
 * The leading term is ~1e30 at t = 1e15 while the differences we take are
 * ~1e18, so ~12 digits cancel; dd's 32 leave ~19, i.e. an absolute error
 * around 0.1 in the integral.  Divided by a Turing zone of length ~50 that
 * is ~0.002 of an integer -- far below the ~0.13 slack the S-bound leaves. */
dd turing_theta_integral(dd t) {
    double e;
    dd lg = dd_sub(dd_log_full_pub(t, &e), DD_LOG2PI);     /* log(t/2pi) */
    dd t2 = dd_mul(t, t);

    dd r = dd_mul(dd_mul_d(t2, 0.25), lg);
    r = dd_sub(r, dd_mul_d(t2, 0.375));
    r = dd_sub(r, dd_mul_d(dd_mul(DD_PI, t), 0.125));

    double td = t.hi;
    r = dd_add(r, dd_of(log(td) / 48.0));
    double it2 = 1.0 / (td * td);
    r = dd_sub(r, dd_of(7.0 * it2 / 11520.0));
    r = dd_sub(r, dd_of(31.0 * it2 * it2 / 322560.0));
    return r;
}

/* sum over certified zeros in (lo, hi] of (hi - gamma), and the count.
 * A bracket contributes its midpoint; because we only ever use the sum in a
 * one-sided inequality, we take the conservative end of each bracket. */
static void zone_sums(const zlist *zl, dd lo, dd hi, int toward_hi,
                      double *sum, long *count) {
    double s = 0.0; long c = 0;
    for (long i = 0; i < zl->n; i++) {
        /* the zero lies in (b.lo, b.hi); require the whole bracket inside */
        if (dd_cmp(zl->b[i].lo, lo) < 0) continue;
        if (dd_cmp(zl->b[i].hi, hi) > 0) continue;
        c++;
        if (toward_hi) {
            /* need a lower bound on (hi - gamma): use gamma <= b.hi */
            dd d = dd_sub(hi, zl->b[i].hi);
            s += d.hi + d.lo;
        } else {
            /* need a lower bound on (gamma - lo): use gamma >= b.lo */
            dd d = dd_sub(zl->b[i].lo, lo);
            s += d.hi + d.lo;
        }
    }
    *sum = s; *count = c;
}

/* (1/pi) * Int_lo^hi theta dt, minus n0*(hi-lo), as a double.
 *
 * WHY THE OFFSET.  At t = 1e15 we have N(t) ~ 5.1e15, which is past 2^52, so
 * one ulp of a double up there is 1.0 -- the whole integer window Turing's
 * method is supposed to resolve fits inside a single rounding step.  The
 * bounds must therefore be formed as offsets from a reference integer n0
 * (the Gram index), with the large cancelling parts done in dd. */
static double theta_int_minus(dd lo, dd hi, long n0) {
    dd d = dd_sub(turing_theta_integral(hi), turing_theta_integral(lo));
    dd q = dd_div(d, DD_PI);
    dd L = dd_sub(hi, lo);
    dd off = dd_mul(dd_of_ll_t(n0), L);
    dd r = dd_sub(q, off);
    return r.hi + r.lo;
}

/* Upper bound on N(a) - n0, using the zone [a, b]. */
static double N_upper(dd a, dd b, const zlist *zl, long n0) {
    dd wd = dd_sub(b, a);
    double L = wd.hi + wd.lo;
    double sum; long cnt;
    zone_sums(zl, a, b, 1, &sum, &cnt);
    double B = turing_S_bound(b.hi);
    return 1.0 + (theta_int_minus(a, b, n0) + B - sum) / L;
}

/* Lower bound on N(a) - n0, using the zone [c, a]. */
static double N_lower(dd c, dd a, const zlist *zl, long n0) {
    dd wd = dd_sub(a, c);
    double L = wd.hi + wd.lo;
    double sum; long cnt;
    zone_sums(zl, c, a, 0, &sum, &cnt);
    double B = turing_S_bound(a.hi);
    return 1.0 + (theta_int_minus(c, a, n0) + sum - B) / L;
}

/* Pin N at a point given zones on both sides.  Returns 1 on success.
 * N is returned as an absolute count; all the arithmetic happens on the
 * offset from n0 so that it stays in a range a double can resolve. */
static int pin_N(dd x, dd below, dd above, const zlist *zl,
                 long *N, double *slack) {
    long n0 = gram_index(x);
    double up = N_upper(x, above, zl, n0);
    double lo = N_lower(below, x, zl, n0);
    *slack = up - lo;
    if (!(up >= lo)) return 0;
    double fl = floor(up);
    if (fl < lo - 1e-9) return 0;          /* no integer in [lo, up] */
    if (fl - 1.0 >= lo - 1e-9) return 0;   /* more than one integer  */
    *N = n0 + (long)fl;
    return 1;
}

int turing_verify(dd a, dd b, dd c, dd e, const zlist *zl, turing_report *rep) {
    rep->verified = 0; rep->why = "";
    rep->Na = rep->Nb = 0;
    rep->slack_a = rep->slack_b = 0.0;
    dd z1 = dd_sub(a, c), z2 = dd_sub(e, b);
    rep->zone = fmin(z1.hi, z2.hi);

    if (!(dd_cmp(c, a) < 0 && dd_cmp(a, b) < 0 && dd_cmp(b, e) < 0)) {
        rep->why = "zones are not ordered c < a < b < e";
        return 0;
    }

    long Na, Nb;
    double sa, sb;
    int oka = pin_N(a, c, b, zl, &Na, &sa);
    int okb = pin_N(b, a, e, zl, &Nb, &sb);
    rep->slack_a = sa; rep->slack_b = sb;

    if (!oka || !okb) {
        rep->why = (sa >= 1.0 || sb >= 1.0)
                 ? "Turing zone too short: the bound leaves more than one integer"
                 : "no integer consistent with the Turing bounds "
                   "(zeros are missing from the certified list)";
        return 0;
    }
    rep->Na = Na; rep->Nb = Nb;
    rep->expected = Nb - Na;

    long found = 0;
    for (long i = 0; i < zl->n; i++)
        if (dd_cmp(zl->b[i].lo, a) >= 0 && dd_cmp(zl->b[i].hi, b) <= 0) found++;
    rep->found = found;

    if (found != rep->expected) {
        rep->why = "certified sign changes do not match the Turing count";
        return 0;
    }
    rep->verified = 1;
    rep->why = "all zeros in the range are simple and on the critical line";
    return 1;
}
