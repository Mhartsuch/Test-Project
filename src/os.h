/* os.h -- Odlyzko-Schoenhage multi-evaluation of the Riemann-Siegel main sum.
 *
 * The problem.  Evaluating Z(t) once costs O(sqrt(t)) = O(N) with
 * N = floor(sqrt(t/2pi)); at t = 1e15 that is 1.26e7 terms.  Locating the
 * zeros in a window needs thousands of evaluations, so the naive cost is
 * O(M N) for M sample points.
 *
 * The method.  Odlyzko and Schoenhage (1988) observed that the main sum,
 * restricted to a window in t, is a band-limited object that can be
 * evaluated at many equally spaced points at once.  This file implements the
 * practical form of that idea:
 *
 *   1. Split k in [1,N] into dyadic blocks [K, 2K).  Inside a block write
 *      log k = log K + u_k with u_k in [0, log 2), so
 *        F(t) = sum_b e^{-i t log K_b} sum_{k in b} a_k e^{-i t u_k}.
 *   2. Write t = t0 + j*delta and absorb the t0 part into the coefficients:
 *        a_k = k^{-1/2} e^{-i t0 u_k}.
 *      This is the only O(N) pass, done once per window.
 *   3. Bin the u_k into P equal bins and Taylor-expand e^{-i j delta w} about
 *      each bin centre (|w| <= h/2).  The k-dependence collapses into
 *      moments  S[b][d][m] = sum_{k in bin m} a_k (2 w_k / h)^d.
 *   4. The bin centres are equally spaced, so summing over m at all j at once
 *      is a DFT -- one FFT per (block, Taylor order).
 *
 * Choosing the grid.  With delta = 2 pi P / (Q log 2) and FFT length Q, the
 * Taylor argument satisfies |j delta w_k| <= rho = pi (M-1) / Q, independent
 * of P.  So Q/M alone controls the expansion depth D, and the truncation
 * error is bounded rigorously by rho^D / D! times sum |a_k|.
 *
 * Cost.  One O(N) pass plus O(B D Q log Q) for the transforms, versus O(M N)
 * for repeated direct evaluation.  At t = 1e15 with M ~ 8000 that is a
 * speed-up of three orders of magnitude, and it is exact up to a bound this
 * module computes and returns.
 */
#ifndef ZETA_OS_H
#define ZETA_OS_H

#include "rs.h"

typedef struct {
    double  t0;         /* first grid point                               */
    double  delta;      /* grid spacing                                   */
    int     m;          /* number of grid points                          */
    long    N;          /* main-sum length (constant across the window)   */
    double *Z;          /* Z(t0 + j*delta), j = 0..m-1                    */
    double  err;        /* rigorous bound on |Z[j] - Z_exact(t_j)|        */
    /* diagnostics */
    int     fft_len, nbins, taylor_d, nblocks;
    double  rho;
    double  secs_coef, secs_fft, secs_total;
} os_window;

/* Evaluate Z on the grid t0 + j*delta, j < m.
 *
 * delta_target is the spacing you would like; the actual spacing is snapped
 * to the nearest value expressible as 2 pi P / (Q log 2) and reported in
 * w->delta.  oversample is Q/M (8 or 16 are good choices; larger means
 * shorter Taylor expansions but bigger transforms).
 * Returns NULL on allocation failure or if N is not constant on the window. */
os_window *os_eval(double t0, double delta_target, int m, int oversample,
                   const rs_logtab *lt, int J, int verbose);

void os_window_free(os_window *w);

/* Number of grid points needed to cover [t0, t1] at the given spacing. */
int os_points_for(double t0, double t1, double delta);

#endif /* ZETA_OS_H */
