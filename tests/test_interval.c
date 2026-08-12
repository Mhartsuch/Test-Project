/* test_interval.c -- containment and tightness of the rigorous interval layer. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include "interval.h"

int iv_verify_constants(int verbose);

static int fails = 0;
static void ok(const char *what, int cond, const char *extra) {
    if (!cond) fails++;
    printf("  %-34s %s %s\n", what, cond ? "ok  " : "FAIL", extra ? extra : "");
}

/* deterministic PRNG so failures reproduce */
static unsigned long long rs = 88172645463325252ULL;
static double urand(void) {
    rs ^= rs << 13; rs ^= rs >> 7; rs ^= rs << 17;
    return (double)(rs >> 11) / 9007199254740992.0;
}

int main(void) {
    printf("test_interval\n");
    iv_init_constants();

    ok("self test (fma, contract, ulp)", iv_self_test() == 0, NULL);
    ok("constants match derivations",    iv_verify_constants(1) == 0, NULL);

    /* pi must be enclosed and tight */
    {
        double pi = 3.141592653589793116e+00;
        ok("IV_PI encloses pi", IV_PI.lo <= pi && pi <= IV_PI.hi, NULL);
        char b[64]; snprintf(b, sizeof b, "width %.2e", iv_wid(IV_PI));
        ok("IV_PI tight (< 1e-15)", iv_wid(IV_PI) < 1e-15, b);
    }

    /* exp / log containment vs libm, and tightness */
    {
        double worst_w = 0; int contained = 1;
        for (int i = 0; i < 20000; i++) {
            double x = (urand() - 0.5) * 1000.0;
            iv e = iv_exp(iv_pt(x));
            double r = exp(x);
            /* libm exp is within a few ulp; require our interval to contain
             * it up to that slack, and to be narrow in relative terms */
            if (!(e.lo <= r * (1 + 1e-14) && r * (1 - 1e-14) <= e.hi)) contained = 0;
            double rel = iv_wid(e) / (fabs(r) + 1e-300);
            if (r > 1e-290 && r < 1e290 && rel > worst_w) worst_w = rel;
        }
        char b[64]; snprintf(b, sizeof b, "worst rel width %.2e", worst_w);
        ok("iv_exp contains libm exp", contained, NULL);
        /* A double-endpoint interval cannot be narrower than 1 ulp
         * (2.2e-16 relative); 2 ulps is essentially optimal. */
        ok("iv_exp tight (rel < 1e-15)", worst_w < 1e-15, b);
    }
    {
        double worst_w = 0; int contained = 1;
        for (int i = 0; i < 20000; i++) {
            double x = exp((urand() - 0.5) * 60.0);
            iv l = iv_log(iv_pt(x));
            double r = log(x);
            if (!(l.lo <= r + 1e-13 && r - 1e-13 <= l.hi)) contained = 0;
            double w = iv_wid(l);
            if (w > worst_w) worst_w = w;
        }
        char b[64]; snprintf(b, sizeof b, "worst abs width %.2e", worst_w);
        ok("iv_log contains libm log", contained, NULL);
        /* |log x| <= 30 here, so 1 ulp is 3.6e-15; 4 ulps is near optimal. */
        ok("iv_log tight (abs < 2e-14)", worst_w < 2e-14, b);
    }

    /* exp/log inverse consistency in interval terms */
    {
        int good = 1;
        for (int i = 0; i < 5000; i++) {
            double x = exp((urand() - 0.5) * 40.0);
            iv back = iv_exp(iv_log(iv_pt(x)));
            if (!(back.lo <= x && x <= back.hi)) good = 0;
        }
        ok("exp(log(x)) encloses x", good, NULL);
    }

    /* sin/cos: containment vs libm and the Pythagorean identity */
    {
        double worst_w = 0; int contained = 1, pyth = 1;
        for (int i = 0; i < 20000; i++) {
            double x = (urand() - 0.5) * 2e15;
            iv s, c;
            iv_sincos(iv_pt(x), &s, &c);
            double rs_ = sin(x), rc = cos(x);
            /* libm loses accuracy in its own argument reduction near 1e15,
             * so allow generous slack here; tightness is checked separately */
            if (!(s.lo <= rs_ + 1e-8 && rs_ - 1e-8 <= s.hi)) contained = 0;
            if (!(c.lo <= rc  + 1e-8 && rc  - 1e-8 <= c.hi)) contained = 0;
            iv one = iv_add(iv_sqr(s), iv_sqr(c));
            if (!(one.lo <= 1.0 && 1.0 <= one.hi)) pyth = 0;
            double w = iv_wid(s) > iv_wid(c) ? iv_wid(s) : iv_wid(c);
            if (w > worst_w) worst_w = w;
        }
        char b[64]; snprintf(b, sizeof b, "worst width %.2e", worst_w);
        ok("iv_sincos contains libm", contained, NULL);
        ok("sin^2+cos^2 encloses 1", pyth, NULL);
        ok("iv_sincos tight (< 1e-14)", worst_w < 1e-14, b);
    }

    /* sin/cos over wide intervals must still enclose (extrema handling) */
    {
        int good = 1;
        for (int i = 0; i < 4000; i++) {
            double a = (urand() - 0.5) * 100.0;
            double w = urand() * 8.0;
            iv S = iv_sin(iv_mk(a, a + w));
            for (int j = 0; j <= 200; j++) {
                double t = a + w * (double)j / 200.0;
                double v = sin(t);
                if (!(S.lo - 1e-12 <= v && v <= S.hi + 1e-12)) { good = 0; break; }
            }
        }
        ok("iv_sin on wide intervals encloses", good, NULL);
    }

    /* mod-2pi reduction of a huge dd phase */
    {
        int good = 1; double worst = 0;
        for (int i = 0; i < 20000; i++) {
            double a = (urand() - 0.5) * 6.0;
            long k = (long)(urand() * 2.0e14);
            dd x = dd_add_d(dd_mul_d(DD_2PI, (double)k), a);
            iv r = iv_reduce_2pi(x, 0.0);
            if (!(r.lo <= a + 1e-12 && a - 1e-12 <= r.hi)) good = 0;
            if (iv_wid(r) > worst) worst = iv_wid(r);
        }
        char b[64]; snprintf(b, sizeof b, "worst width %.2e", worst);
        ok("iv_reduce_2pi correct at 1e15", good, NULL);
        ok("iv_reduce_2pi tight (< 1e-13)", worst < 1e-13, b);
    }

    printf("test_interval: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
