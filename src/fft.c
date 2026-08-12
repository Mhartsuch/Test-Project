#include "fft.h"
#include "dd.h"
#include <stdlib.h>
#include <math.h>

fft_plan *fft_plan_new(int n) {
    if (n < 2 || (n & (n - 1))) return NULL;
    fft_plan *p = (fft_plan *)malloc(sizeof *p);
    if (!p) return NULL;
    p->n = n;
    p->log2n = 0;
    while ((1 << p->log2n) < n) p->log2n++;
    p->w   = (double complex *)malloc(sizeof(double complex) * (size_t)(n / 2));
    p->rev = (int *)malloc(sizeof(int) * (size_t)n);
    if (!p->w || !p->rev) { fft_plan_free(p); return NULL; }

    /* twiddles from dd so the table is correctly rounded */
    for (int j = 0; j < n / 2; j++) {
        dd ang = dd_div_d(dd_mul_d(DD_2PI, (double)j), (double)n);
        dd s, c;
        dd_sincos(ang, &s, &c);
        p->w[j] = (c.hi + c.lo) - I * (s.hi + s.lo);
    }
    for (int j = 0; j < n; j++) {
        int r = 0;
        for (int b = 0; b < p->log2n; b++) if (j & (1 << b)) r |= 1 << (p->log2n - 1 - b);
        p->rev[j] = r;
    }
    return p;
}

void fft_plan_free(fft_plan *p) {
    if (!p) return;
    free(p->w); free(p->rev); free(p);
}

void fft_forward(const fft_plan *p, double complex *a) {
    const int n = p->n;
    for (int j = 0; j < n; j++) {
        int r = p->rev[j];
        if (j < r) { double complex t = a[j]; a[j] = a[r]; a[r] = t; }
    }
    for (int len = 2; len <= n; len <<= 1) {
        int half = len >> 1, step = n / len;
        for (int i = 0; i < n; i += len) {
            for (int j = 0; j < half; j++) {
                double complex u = a[i + j];
                double complex v = a[i + j + half] * p->w[j * step];
                a[i + j]        = u + v;
                a[i + j + half] = u - v;
            }
        }
    }
}

void fft_inverse(const fft_plan *p, double complex *a) {
    const int n = p->n;
    for (int j = 0; j < n; j++) a[j] = conj(a[j]);
    fft_forward(p, a);
    double inv = 1.0 / (double)n;
    for (int j = 0; j < n; j++) a[j] = conj(a[j]) * inv;
}

double fft_error_bound(int n, double sum_abs_input) {
    double l = log2((double)n);
    return FFT_ERR_C * l * 0x1p-53 * sum_abs_input;
}
