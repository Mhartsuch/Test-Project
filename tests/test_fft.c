/* test_fft.c -- the FFT is exercised in detail inside test_os; this binary
 * exists so the transform can be checked on its own. */
#include <stdio.h>
#include <stdlib.h>
#include <math.h>
#include <complex.h>
#include "fft.h"

static int fails = 0;
static void ok(const char *what, int cond, const char *extra) {
    if (!cond) fails++;
    printf("  %-40s %s %s\n", what, cond ? "ok  " : "FAIL", extra ? extra : "");
}

int main(void) {
    printf("test_fft\n");
    unsigned long long s = 99;
    for (int n = 2; n <= 65536; n <<= 1) {
        fft_plan *p = fft_plan_new(n);
        if (!p) { ok("plan", 0, NULL); continue; }
        double complex *a = malloc(sizeof(double complex) * n);
        double complex *b = malloc(sizeof(double complex) * n);
        double sumabs = 0;
        for (int i = 0; i < n; i++) {
            s ^= s << 13; s ^= s >> 7; s ^= s << 17;
            double re = (double)(s >> 11) / 9007199254740992.0 - 0.5;
            s ^= s << 13; s ^= s >> 7; s ^= s << 17;
            double im = (double)(s >> 11) / 9007199254740992.0 - 0.5;
            a[i] = re + im * I; b[i] = a[i];
            sumabs += cabs(a[i]);
        }
        fft_forward(p, b);
        fft_inverse(p, b);
        double worst = 0;
        for (int i = 0; i < n; i++) {
            double d = cabs(a[i] - b[i]);
            if (d > worst) worst = d;
        }
        char msg[100];
        double bound = fft_error_bound(n, sumabs);
        snprintf(msg, sizeof msg, "n=%5d err %.2e (bound %.2e)", n, worst, bound);
        ok("round trip within the stated bound", worst <= bound + 1e-15, msg);
        free(a); free(b); fft_plan_free(p);
    }
    /* a known transform: delta -> all ones */
    {
        int n = 64;
        fft_plan *p = fft_plan_new(n);
        double complex *a = calloc(n, sizeof(double complex));
        a[0] = 1.0;
        fft_forward(p, a);
        int good = 1;
        for (int i = 0; i < n; i++) if (cabs(a[i] - 1.0) > 1e-15) good = 0;
        ok("FFT(delta) = all ones", good, NULL);
        free(a); fft_plan_free(p);
    }
    printf("test_fft: %s (%d failures)\n", fails ? "FAILED" : "PASSED", fails);
    return fails ? 1 : 0;
}
