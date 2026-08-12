/* fft.h -- self-contained radix-2 complex FFT (no external dependency).
 *
 * Sizes must be powers of two; the Odlyzko-Schoenhage driver chooses them.
 * Twiddle factors are built once per size in double-double and rounded, so
 * the table itself is accurate to <1 ulp -- this matters because the FFT
 * length reaches 2^15..2^20 and a naive recurrence for the twiddles would
 * drift by orders of magnitude more than the transform's own error.
 */
#ifndef ZETA_FFT_H
#define ZETA_FFT_H

#include <complex.h>

typedef struct {
    int n;                    /* transform length, a power of two */
    int log2n;
    double complex *w;        /* w[j] = exp(-2*pi*i*j/n), j < n/2 */
    int *rev;                 /* bit-reversal permutation */
} fft_plan;

fft_plan *fft_plan_new(int n);
void      fft_plan_free(fft_plan *p);

/* In-place forward transform: X[k] = sum_j x[j] exp(-2*pi*i*j*k/n). */
void fft_forward(const fft_plan *p, double complex *a);
/* In-place inverse (with the 1/n scaling). */
void fft_inverse(const fft_plan *p, double complex *a);

/* Rigorous-ish componentwise error bound for fft_forward.
 *
 *   |X_k^computed - X_k^exact| <= FFT_ERR_C * log2(n) * eps * sum_j |x_j|
 *
 * with eps = 2^-53.  This is the standard worst-case bound for radix-2
 * Cooley-Tukey with a correctly-rounded twiddle table (Higham, "Accuracy and
 * Stability of Numerical Algorithms", 2nd ed., ch. 24); FFT_ERR_C = 12 leaves
 * a comfortable margin over the constant proved there.  This is a LITERATURE
 * bound, not one proved in this repository -- see docs/RIGOR.md.
 */
#define FFT_ERR_C 12.0
double fft_error_bound(int n, double sum_abs_input);

#endif /* ZETA_FFT_H */
