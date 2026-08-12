#define _POSIX_C_SOURCE 200809L
#include "os.h"
#include "fft.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <complex.h>
#include <time.h>

#define DD_OP_EPS 0x1p-102
#define TWO_PI_OVER_LOG2 9.06472028365468601e+00   /* 2*pi / log 2 */

/* k below the cutoff are summed directly at every grid point.  Keeping the
 * small dyadic blocks out of the transform machinery saves ~8 blocks worth of
 * FFTs and costs only k_small*m phase reductions.  The cutoff adapts so the
 * routine still works at modest heights where N itself is small. */
#define K_SMALL_MAX 256

static double now_s(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return (double)ts.tv_sec + 1e-9 * (double)ts.tv_nsec;
}

int os_points_for(double t0, double t1, double delta) {
    if (delta <= 0.0 || t1 <= t0) return 0;
    double n = (t1 - t0) / delta;
    if (n > 2.0e9) return 0;
    return (int)n + 2;
}

static int next_pow2(int n) {
    int q = 1;
    while (q < n) q <<= 1;
    return q;
}

void os_window_free(os_window *w) {
    if (!w) return;
    free(w->Z);
    free(w);
}

os_window *os_eval(double t0, double delta_target, int m, int oversample,
                   const rs_logtab *lt, int J, int verbose)
{
    if (m < 2 || delta_target <= 0.0) return NULL;
    if (oversample < 2) oversample = 8;

    double T_start = now_s();

    dd t0d = dd_of(t0);
    long N = rs_nterms(t0d);
    if (N > lt->nmax || N < 64) return NULL;

    long k_small = 4;
    while (k_small * 2 <= K_SMALL_MAX && k_small * 16 <= N) k_small *= 2;

    /* ---- grid geometry -------------------------------------------------- */
    int Q = next_pow2(oversample * m);
    long P = lrint(delta_target * (double)Q / TWO_PI_OVER_LOG2);
    if (P < 1) P = 1;
    double delta = TWO_PI_OVER_LOG2 * (double)P / (double)Q;
    double h = 0.69314718055994530942 / (double)P;      /* bin width, log2/P */
    double rho = 3.14159265358979323846 * (double)(m - 1) / (double)Q;

    /* N must not change across the window, or the block structure and the
     * correction term's index parity would both shift underneath us. */
    dd deltad = dd_of(delta);
    if (rs_nterms(dd_add(t0d, dd_mul_d(deltad, (double)(m - 1)))) != N) return NULL;

    /* Taylor depth: truncation is bounded by rho^D / D! (times sum|a_k|). */
    int D = 1;
    {
        double term = 1.0;
        for (D = 1; D < 64; D++) {
            term *= rho / (double)D;
            if (term < 1e-18) break;
        }
        D += 1;
        if (D < 4) D = 4;
    }

    /* ---- block layout --------------------------------------------------- */
    int nblocks = 0;
    for (long K = k_small; K <= N; K <<= 1) nblocks++;
    if (nblocks < 1) return NULL;

    fft_plan *plan = fft_plan_new(Q);
    if (!plan) return NULL;

    size_t nmom = (size_t)nblocks * (size_t)D * (size_t)P;
    double complex *S   = (double complex *)calloc(nmom, sizeof(double complex));
    double complex *out = (double complex *)malloc(sizeof(double complex) *
                                                   (size_t)nblocks * (size_t)D * (size_t)m);
    double complex *buf = (double complex *)malloc(sizeof(double complex) * (size_t)Q);
    os_window *w = (os_window *)calloc(1, sizeof *w);
    double *Z = (double *)malloc(sizeof(double) * (size_t)m);
    if (!S || !out || !buf || !w || !Z) {
        free(S); free(out); free(buf); free(w); free(Z);
        fft_plan_free(plan); return NULL;
    }

    if (verbose)
        fprintf(stderr,
            "  O-S window: t0=%.6f  N=%ld  m=%d  delta=%.6g\n"
            "              Q=%d  P=%ld  blocks=%d  rho=%.4f  Taylor D=%d\n",
            t0, N, m, delta, Q, P, nblocks, rho, D);

    /* ---- pass 1: the only O(N) loop ------------------------------------- */
    double t_coef0 = now_s();
    double sumabs = 0.0;
    {
        int b = 0;
        for (long K = k_small; K <= N; K <<= 1, b++) {
            long Kend = K << 1;
            if (Kend > N + 1) Kend = N + 1;
            dd Lb = lt->log[K];
            double complex *Sb = S + (size_t)b * (size_t)D * (size_t)P;

            for (long k = K; k < Kend; k++) {
                dd ud = dd_sub(lt->log[k], Lb);          /* u_k in [0, log2) */
                double u = ud.hi + ud.lo;
                double phi = dd_mod_2pi(dd_mul(ud, t0d));
                double amp = 1.0 / sqrt((double)k);
                double complex a = amp * (cos(phi) - I * sin(phi));
                sumabs += amp;

                long mm = (long)(u / h);
                if (mm < 0) mm = 0;
                if (mm >= P) mm = P - 1;
                double wk = u - ((double)mm + 0.5) * h;
                double what = 2.0 * wk / h;              /* in [-1, 1] */

                double complex pw = 1.0;
                for (int d = 0; d < D; d++) {
                    Sb[(size_t)d * (size_t)P + mm] += a * pw;
                    pw *= what;
                }
            }
        }
    }
    double t_coef1 = now_s();

    /* ---- pass 2: one FFT per (block, Taylor order) ---------------------- */
    for (int b = 0; b < nblocks; b++) {
        for (int d = 0; d < D; d++) {
            const double complex *Sbd = S + ((size_t)b * D + d) * (size_t)P;
            memcpy(buf, Sbd, sizeof(double complex) * (size_t)P);
            memset(buf + P, 0, sizeof(double complex) * (size_t)(Q - P));
            fft_forward(plan, buf);
            memcpy(out + ((size_t)b * D + d) * (size_t)m, buf,
                   sizeof(double complex) * (size_t)m);
        }
    }
    double t_fft1 = now_s();

    /* ---- pass 3: assemble Z on the grid --------------------------------- */
    for (int j = 0; j < m; j++) {
        /* The grid point must be formed in dd.  At t = 1e15 one ulp of a
         * double is 0.125 while delta is ~0.02, so `t0 + j*delta' evaluated
         * in double would quantise the grid to a coarser lattice than the
         * spacing itself -- and the block phases below, which are multiplied
         * by log K ~ 16, would then disagree with the Taylor/FFT machinery
         * (which works off the exact t0 + j*delta) by ~1e-7. */
        dd tj = dd_add(t0d, dd_mul_d(deltad, (double)j));
        double beta = 3.14159265358979323846 * (double)j / (double)Q;
        double complex pref = cos(beta) - I * sin(beta);          /* e^{-i beta} */

        double complex G = 0.0;

        /* blocks */
        int b = 0;
        for (long K = k_small; K <= N; K <<= 1, b++) {
            double complex acc = 0.0;
            double complex cd = 1.0;                              /* (-i beta)^d/d! */
            const double complex *ob = out + (size_t)b * D * (size_t)m;
            for (int d = 0; d < D; d++) {
                acc += cd * ob[(size_t)d * (size_t)m + j];
                cd *= (-I * beta) / (double)(d + 1);
            }
            acc *= pref;
            double psi = dd_mod_2pi(dd_mul(lt->log[K], tj));      /* t_j * L_b */
            G += acc * (cos(psi) - I * sin(psi));
        }

        /* small k, summed directly */
        for (long k = 1; k < k_small; k++) {
            double ph = dd_mod_2pi(dd_mul(lt->log[k], tj));
            double amp = 1.0 / sqrt((double)k);
            G += amp * (cos(ph) - I * sin(ph));
        }

        double Th = rs_theta_mod2pi(tj);
        double complex eth = cos(Th) + I * sin(Th);
        Z[j] = 2.0 * creal(eth * G) + rs_correction(tj, J);
    }
    double T_end = now_s();

    /* ---- rigorous error budget ------------------------------------------ */
    double eps = 0x1p-53;
    double sa = 2.0 * sqrt((double)N) + 1.0;      /* >= sum_{k<=N} k^{-1/2} */
    (void)sumabs;

    /* (a) coefficient phase error: log-table error scaled by t0, dd rounding
     *     on the u_k subtraction and the t0*u_k product, and libm sin/cos. */
    double e_a = t0 * (2.0 * lt->err)
               + 4.0 * DD_OP_EPS * (t0 * 0.7 + 20.0)
               + 2.0 * eps;
    /* (b) Taylor truncation, bounded by rho^D/D! */
    double taylor = 1.0;
    for (int d = 1; d <= D; d++) taylor *= rho / (double)d;
    /* (c) FFT round-off, weighted by sum_d rho^d/d! = e^rho */
    double e_fft = FFT_ERR_C * log2((double)Q) * eps * exp(rho);
    /* (d) block assembly and the final combination */
    double e_asm = (double)(nblocks + 8) * eps;
    /* (e) theta, coherent across all terms */
    double e_th = rs_theta_err(t0 + (double)m * delta);
    /* grid-point representation is exact in dd, so nothing to add here */

    w->err = 2.0 * sa * (e_a + taylor + e_fft + e_asm + e_th)
           + rs_trunc_bound(t0, J) + 1e-14;

    w->t0 = t0; w->delta = delta; w->m = m; w->N = N; w->Z = Z;
    w->fft_len = Q; w->nbins = (int)P; w->taylor_d = D; w->nblocks = nblocks;
    w->rho = rho;
    w->secs_coef = t_coef1 - t_coef0;
    w->secs_fft  = t_fft1 - t_coef1;
    w->secs_total = T_end - T_start;

    if (verbose)
        fprintf(stderr,
            "              coef %.2fs  fft %.2fs  assemble %.2fs  total %.2fs\n"
            "              error bound %.3e  (taylor %.1e, fft %.1e, coef %.1e)\n",
            w->secs_coef, w->secs_fft, T_end - t_fft1, w->secs_total,
            w->err, 2 * sa * taylor, 2 * sa * e_fft, 2 * sa * e_a);

    free(S); free(out); free(buf);
    fft_plan_free(plan);
    return w;
}
