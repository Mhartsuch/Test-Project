#include "rs.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* provided by interval.c: dd log with a proven absolute error bound */
dd iv_log_dd(double x, double *err);

#define DD_OP_EPS 0x1p-102

/* ===================================================================== */
/*  Kahan-Babuska-Neumaier compensated summation                          */
/*                                                                        */
/*  Naive summation of the N ~ 1.3e7 main-sum terms would accumulate an   */
/*  error of order N * eps * sum|x| ~ 2e-5, swamping everything.  KBN     */
/*  brings that down to ~2 eps sum|x| ~ 3e-12, independent of N.          */
/* ===================================================================== */

typedef struct { double s, c; } ksum;
static inline void ksum_init(ksum *k) { k->s = 0.0; k->c = 0.0; }
static inline void ksum_add(ksum *k, double x) {
    double t = k->s + x;
    if (fabs(k->s) >= fabs(x)) k->c += (k->s - t) + x;
    else                       k->c += (x - t) + k->s;
    k->s = t;
}
static inline double ksum_get(const ksum *k) { return k->s + k->c; }

/* ===================================================================== */
/*  log table                                                             */
/* ===================================================================== */

rs_logtab *rs_logtab_build(long nmax, int verbose) {
    if (nmax < 1) nmax = 1;
    rs_logtab *lt = (rs_logtab *)malloc(sizeof *lt);
    if (!lt) return NULL;
    lt->nmax = nmax;
    lt->log = (dd *)malloc(sizeof(dd) * (size_t)(nmax + 1));
    if (!lt->log) { free(lt); return NULL; }

    /* smallest-prime-factor sieve, so log k = log spf + log (k/spf):
     * one dd add per composite, a real log only for the ~n/ln n primes. */
    int *spf = (int *)calloc((size_t)(nmax + 1), sizeof(int));
    if (!spf) { free(lt->log); free(lt); return NULL; }
    for (long i = 2; i <= nmax; i++) {
        if (spf[i] == 0)
            for (long j = i; j <= nmax; j += i)
                if (spf[j] == 0) spf[j] = (int)i;
    }

    double worst_prime_err = 0.0;
    lt->log[0] = dd_of(0.0);
    if (nmax >= 1) lt->log[1] = dd_of(0.0);
    long nprime = 0;
    for (long k = 2; k <= nmax; k++) {
        if (spf[k] == (int)k) {                 /* prime */
            double e = 0.0;
            lt->log[k] = iv_log_dd((double)k, &e);
            if (e > worst_prime_err) worst_prime_err = e;
            nprime++;
        } else {
            lt->log[k] = dd_add(lt->log[spf[k]], lt->log[k / spf[k]]);
        }
    }
    free(spf);

    /* Error bound.  A chain has depth <= log2(nmax) <= 24; each dd_add
     * contributes <= DD_OP_EPS * log(nmax), and each leaf is a prime log
     * with error <= worst_prime_err. */
    double depth = log2((double)nmax) + 1.0;
    lt->err = depth * (worst_prime_err + DD_OP_EPS * log((double)nmax + 2.0));

    if (verbose)
        fprintf(stderr, "  log table: %ld entries (%ld primes), "
                        "%.1f MB, |err| <= %.2e\n",
                nmax, nprime, (double)(nmax + 1) * sizeof(dd) / 1048576.0, lt->err);
    return lt;
}

void rs_logtab_free(rs_logtab *lt) {
    if (!lt) return;
    free(lt->log); free(lt);
}

/* ===================================================================== */
/*  theta                                                                 */
/* ===================================================================== */

/* log of a dd argument: log(hi) from the proven-bound routine, plus the
 * correction log(1 + lo/hi) as a short series (|lo/hi| <= 2^-53, so three
 * terms are already below 1e-48). */
dd dd_log_full_pub(dd x, double *err) {
    dd l0 = iv_log_dd(x.hi, err);
    double r = x.lo / x.hi;
    dd c = dd_of(r - 0.5 * r * r + (1.0 / 3.0) * r * r * r);
    return dd_add(l0, c);
}

/* theta(t) = t/2 log(t/2pi) - t/2 - pi/8
 *            + 1/(48t) + 7/(5760 t^3) + 31/(80640 t^5) + 127/(430080 t^7)
 * The four asymptotic coefficients are verified against mpmath's
 * siegeltheta in tests/test_rs.c. */
dd rs_theta(dd t) {
    double e;
    dd lg = dd_sub(dd_log_full_pub(t, &e), DD_LOG2PI);      /* log(t/2pi) */

    dd half_t = dd_mul_d(t, 0.5);
    dd r = dd_mul(half_t, lg);
    r = dd_sub(r, half_t);
    r = dd_sub(r, dd_mul_d(DD_PI, 0.125));

    double td = t.hi;
    double it = 1.0 / td, it2 = it * it;
    dd corr = dd_mul_d(dd_of(it), 1.0 / 48.0);
    double p = it * it2;
    corr = dd_add(corr, dd_of(p * (7.0 / 5760.0)));
    p *= it2;
    corr = dd_add(corr, dd_of(p * (31.0 / 80640.0)));
    p *= it2;
    corr = dd_add(corr, dd_of(p * (127.0 / 430080.0)));
    return dd_add(r, corr);
}

double rs_theta_err(double t) {
    double e_log = 0.0;
    (void)iv_log_dd(t, &e_log);
    double mag = 0.5 * t * (log(t / 6.283185307179586) + 1.0) + 1.0;
    /* log error scaled by t/2, dd rounding on ~5 operations at magnitude mag,
     * plus the asymptotic tail (next term 511/(1216512 t^9), negligible). */
    double tail = 511.0 / (1216512.0 * pow(t, 9.0));
    return 0.5 * t * (e_log + 1e-32) + 6.0 * DD_OP_EPS * mag + tail + 1e-300;
}

double rs_theta_mod2pi(dd t) { return dd_mod_2pi(rs_theta(t)); }

double rs_theta_prime(double t) { return 0.5 * log(t / 6.283185307179586232); }

/* Solve theta(t) = target by Newton; theta is increasing for t > 6.29. */
double rs_theta_inv(double target) {
    /* initial guess from the leading term: t/2 (log(t/2pi) - 1) = target */
    double t = 2.0 * 3.141592653589793 * exp(1.0 + target / 3.0 + 10.0);
    if (!(t > 10.0) || t > 1e300) t = 100.0;
    /* robust bracket-free Newton from a decent start */
    t = 20.0;
    if (target > 0) {
        /* invert asymptotically: theta ~ (t/2) log(t/(2 pi e)) */
        double x = target;
        t = 2.0 * x / log(x + 3.0) + 20.0;
        for (int i = 0; i < 200; i++) {
            dd th = rs_theta(dd_of(t));
            double f = (th.hi + th.lo) - target;
            double fp = rs_theta_prime(t);
            if (fp < 1e-12) fp = 1e-12;
            double step = f / fp;
            if (step > 0.5 * t) step = 0.5 * t;
            if (step < -0.5 * t) step = -0.5 * t;
            t -= step;
            if (t < 10.0) t = 10.0;
            if (fabs(step) < 1e-13 * t) break;
        }
    }
    return t;
}

long rs_nterms(dd t) {
    dd tau = dd_sqrt(dd_mul(t, DD_INV_2PI));
    dd fl = dd_floor(tau);
    long n = (long)(fl.hi + fl.lo);
    /* guard the boundary in dd: N = floor(tau) exactly */
    while (dd_cmp(dd_of((double)(n + 1)), tau) <= 0) n++;
    while (n > 0 && dd_cmp(dd_of((double)n), tau) > 0) n--;
    return n;
}

/* ===================================================================== */
/*  Psi and the correction terms                                          */
/* ===================================================================== */

/* Psi(p) = cos(2pi(p^2 - p - 1/16)) / cos(2pi p).
 *
 * Both numerator and denominator vanish at p = 1/4 + m/2, so evaluate
 * relative to the nearest such point.  With w = p - (1/4 + m/2):
 *   cos(2pi p)  = (-1)^{m+1} sin(2pi w)
 *   numerator   = -sigma_m sin(2pi w (w + m - 1/2)),  sigma_m = +-1
 * giving a ratio that stays accurate right through the removable
 * singularity (dd resolves w down to ~1e-31 so no series is needed). */
dd rs_psi(dd p) {
    double pd = p.hi;
    double mf = floor(2.0 * pd - 0.5 + 0.5);
    long m = (long)mf;
    dd s = dd_add_d(dd_mul_d(dd_of((double)m), 0.5), 0.25);
    dd w = dd_sub(p, s);

    long d = ((m * m - m - 1) % 4 + 4) % 4;     /* 1 or 3 */
    double sigma = (d == 1) ? 1.0 : -1.0;
    double sgn = ((m % 2 + 2) % 2 == 0) ? -1.0 : 1.0;   /* (-1)^{m+1} */

    if (w.hi == 0.0 && w.lo == 0.0)
        return dd_of(-sigma * sgn * ((double)m - 0.5));

    dd x = dd_mul(dd_mul(DD_2PI, w), dd_add_d(w, (double)m - 0.5));
    dd y = dd_mul(DD_2PI, w);
    dd sx, cx, sy, cy;
    dd_sincos(x, &sx, &cx);
    dd_sincos(y, &sy, &cy);
    dd r = dd_div(sx, sy);
    return dd_mul_d(r, -sigma * sgn);
}

/* Psi''' by a central difference in dd.  With h = 1e-5 the truncation term
 * (h^2/4) Psi^(5) is ~1e-8 and the dd round-off ~1e-31/h^3 ~ 1e-16, so the
 * result is good to ~1e-8 -- and C_1 is divided by 96 pi^2 and multiplied by
 * tau^{-3/2}, so this is far below the noise floor at any t we use it at. */
static double psi_d3(dd p) {
    const double h = 1e-5;
    dd a = rs_psi(dd_add_d(p,  2.0 * h));
    dd b = rs_psi(dd_add_d(p,  1.0 * h));
    dd c = rs_psi(dd_add_d(p, -1.0 * h));
    dd d = rs_psi(dd_add_d(p, -2.0 * h));
    dd num = dd_sub(dd_add(a, dd_mul_d(c, 2.0)), dd_add(dd_mul_d(b, 2.0), d));
    return (num.hi + num.lo) / (2.0 * h * h * h);
}

double rs_correction(dd t, int J) {
    dd tau = dd_sqrt(dd_mul(t, DD_INV_2PI));
    long N = rs_nterms(t);
    dd p = dd_sub(tau, dd_of((double)N));
    double taud = tau.hi;

    dd c0 = rs_psi(p);
    double corr = c0.hi + c0.lo;
    if (J >= 1) {
        double c1 = -psi_d3(p) / (96.0 * 9.869604401089358);   /* 96 pi^2 */
        corr += c1 / taud;
    }
    double sgn = ((N - 1) & 1) ? -1.0 : 1.0;
    return sgn * pow(taud, -0.5) * corr;
}

/* sup_p |Z - RS_J| <= K_J tau^{-(2J+3)/2}.
 * K_J measured over 105 heights in [100, 2e5] against mpmath (see
 * scripts/calibrate_rs.py): 0.031, 0.0053, 0.00036 for J = 0,1,2.
 * The values below carry a safety factor of ~100.  This is an EMPIRICAL
 * calibration, not a proof -- see docs/RIGOR.md.  At t >= 1e6 the resulting
 * bound is already below 1e-6, and at t = 1e15 it is ~1e-18, far under the
 * floating-point noise floor, so nothing downstream is sensitive to it. */
double rs_trunc_bound(double t, int J) {
    static const double K[3] = { 3.0, 0.6, 0.05 };
    if (J < 0) J = 0;
    if (J > 2) J = 2;
    double tau = sqrt(t / 6.283185307179586232);
    return K[J] * pow(tau, -(2.0 * J + 3.0) / 2.0);
}

/* ===================================================================== */
/*  Z(t): fast path                                                       */
/* ===================================================================== */

double rs_Z(dd t, const rs_logtab *lt, int J) {
    long N = rs_nterms(t);
    if (N > lt->nmax) return NAN;
    double Th = rs_theta_mod2pi(t);
    double cT = cos(Th), sT = sin(Th);

    ksum sc, ss;
    ksum_init(&sc); ksum_init(&ss);
    for (long k = 1; k <= N; k++) {
        double phi = dd_mod_2pi(dd_mul(lt->log[k], t));
        double w = 1.0 / sqrt((double)k);
        ksum_add(&sc, w * cos(phi));
        ksum_add(&ss, w * sin(phi));
    }
    /* cos(Th - phi) = cos Th cos phi + sin Th sin phi */
    double main = 2.0 * (cT * ksum_get(&sc) + sT * ksum_get(&ss));
    return main + rs_correction(t, J);
}

double rs_Z_errbound(double t, int J) {
    long N = rs_nterms(dd_of(t));
    double sqrtsum = 2.0 * sqrt((double)N) + 1.0;          /* >= sum k^{-1/2} */
    double e_theta = rs_theta_err(t);
    double e_log = 1e-30;                                   /* log table bound */
    /* per-term phase error: t*|log err| + dd rounding at magnitude t log N */
    double mag = t * log((double)N + 2.0) + 1.0;
    double e_phase = t * e_log + 3.0 * DD_OP_EPS * mag;
    double eps = 0x1p-53;

    double e = 0.0;
    e += 2.0 * sqrtsum * e_phase;        /* phase errors, worst case aligned  */
    e += 2.0 * sqrtsum * e_theta;        /* theta error (coherent)            */
    e += 2.0 * sqrtsum * 2.0 * eps;      /* libm cos/sin, <= 1 ulp each       */
    e += 2.0 * sqrtsum * 2.0 * eps;      /* KBN summation                     */
    e += 4.0 * eps * sqrtsum;            /* final combination                 */
    e += rs_trunc_bound(t, J);           /* asymptotic tail                   */
    e += 1e-14;                          /* correction-term evaluation        */
    return e;
}

/* ===================================================================== */
/*  Z(t): fully rigorous path (interval arithmetic per term)              */
/* ===================================================================== */

iv rs_Z_iv(dd t, const rs_logtab *lt, int J) {
    long N = rs_nterms(t);
    if (N > lt->nmax) return iv_empty();

    dd th = rs_theta(t);
    iv Th = iv_reduce_2pi(th, rs_theta_err(t.hi));
    iv cT, sT;
    iv_sincos(Th, &sT, &cT);

    /* accumulate the two sums in dd, tracking a rigorous error budget */
    dd accC = dd_of(0.0), accS = dd_of(0.0);
    double budget = 0.0;
    double mag = t.hi * log((double)N + 2.0) + 1.0;
    double e_phase = t.hi * lt->err + 3.0 * DD_OP_EPS * mag;

    for (long k = 1; k <= N; k++) {
        dd ph = dd_mul(lt->log[k], t);
        iv r = iv_reduce_2pi(ph, e_phase);
        iv sk, ck;
        iv_sincos(r, &sk, &ck);
        double w = 1.0 / sqrt((double)k);
        accC = dd_add(accC, dd_mul_d(dd_of(iv_mid(ck)), w));
        accS = dd_add(accS, dd_mul_d(dd_of(iv_mid(sk)), w));
        budget += w * (iv_rad(ck) + iv_rad(sk));
        budget += DD_OP_EPS * 4.0;
    }
    iv SC = iv_mk(accC.hi + accC.lo - budget, accC.hi + accC.lo + budget);
    iv SS = iv_mk(accS.hi + accS.lo - budget, accS.hi + accS.lo + budget);

    iv main = iv_mul_d(iv_add(iv_mul(cT, SC), iv_mul(sT, SS)), 2.0);
    double corr = rs_correction(t, J);
    double ce = rs_trunc_bound(t.hi, J) + 1e-14;
    return iv_add(main, iv_mk(corr - ce, corr + ce));
}

/* ===================================================================== */
/*  Euler-Maclaurin: independent evaluator                                */
/* ===================================================================== */

static const double BERN_OVER_FACT[] = {   /* B_{2k}/(2k)!, k = 1.. */
    +8.33333333333333287e-02, -1.38888888888888894e-03, +3.30687830687830710e-05,
    -8.26719576719576754e-07, +2.08767569878681002e-08, -5.28419013868749322e-10,
    +1.33825365306846789e-11, -3.38968029632258272e-13, +8.58606205627784517e-15,
    -2.17486869855806192e-16, +5.50900282836022953e-18, -1.39544646858125223e-19,
    +3.53470703962946728e-21, -8.95351742703754628e-23, +2.26795245233768293e-24,
    -5.74479066887220246e-26, +1.45517247561486496e-27, -3.68599494066531029e-29,
    +9.33673425709504507e-31, -2.36502241570062995e-32, +5.99067176248213414e-34,
    -1.51745488446829032e-35, +3.84375812545418860e-37, -9.73635307264669126e-39,
    +2.46624704420068111e-40,
};
#define BERN_N 25

/* zeta(1/2+it) by Euler-Maclaurin:
 *   zeta(s) = sum_{n<M} n^-s + M^-s/2 + M^{1-s}/(s-1)
 *             + sum_{k=1}^{K} B_{2k}/(2k)! (s)_{2k-1} M^{-s-2k+1} + R_K
 * with |R_K| <= |(s)_{2K+1} / (sigma+2K+1)| |B_{2K+2}/(2K+2)!| M^{-sigma-2K-1}
 * (Edwards, "Riemann's Zeta Function", sec. 6.4).
 * Returns Z(t) = Re( e^{i theta} zeta ) as an enclosure. */
iv em_Z_iv(double t, long M, int K) {
    if (K < 1) K = 12;
    if (K > BERN_N - 1) K = BERN_N - 1;
    if (M <= 0) {
        M = (long)(t * 1.2) + 60;          /* M > |t| keeps the tail decaying */
        if (M < 40) M = 40;
    }
    const double sigma = 0.5;

    /* main sum, in dd phases with compensated accumulation */
    ksum sc, ss;
    ksum_init(&sc); ksum_init(&ss);
    for (long n = 1; n < M; n++) {
        double e;
        dd lg = iv_log_dd((double)n, &e);
        double phi = dd_mod_2pi(dd_mul_d(lg, t));
        double w = 1.0 / sqrt((double)n);
        ksum_add(&sc,  w * cos(phi));
        ksum_add(&ss, -w * sin(phi));      /* n^{-s} = w (cos - i sin) */
    }
    double zr = ksum_get(&sc), zi = ksum_get(&ss);

    double eM;
    dd lgM = iv_log_dd((double)M, &eM);
    double phiM = dd_mod_2pi(dd_mul_d(lgM, t));
    double cM = cos(phiM), sM = -sin(phiM);
    double wM = 1.0 / sqrt((double)M);

    /* + M^-s / 2 */
    zr += 0.5 * wM * cM;
    zi += 0.5 * wM * sM;

    /* + M^{1-s}/(s-1),  s-1 = -1/2 + it */
    {
        double ar = sqrt((double)M) * cM, ai = sqrt((double)M) * sM;
        double br = -0.5, bi = t;
        double den = br * br + bi * bi;
        zr += (ar * br + ai * bi) / den;
        zi += (ai * br - ar * bi) / den;
    }

    /* Bernoulli terms.  (s)_{2k-1} built incrementally. */
    double pr = 1.0, pi_ = 0.0;                    /* rising factorial (s)_j  */
    long j = 0;
    double Mm2 = 1.0 / ((double)M * (double)M);
    double fr = wM * cM, fi = wM * sM;             /* M^{-s} * M^{-2k+1} step */
    /* start with M^{-s-1} = M^{-s}/M */
    fr /= (double)M; fi /= (double)M;
    double last_abs = 0.0;
    for (int k = 1; k <= K; k++) {
        while (j < 2 * k - 1) {                    /* multiply by (s+j) */
            double ar = sigma + (double)j, ai = t;
            double nr = pr * ar - pi_ * ai;
            double ni = pr * ai + pi_ * ar;
            pr = nr; pi_ = ni; j++;
        }
        double b = BERN_OVER_FACT[k - 1];
        zr += b * (pr * fr - pi_ * fi);
        zi += b * (pr * fi + pi_ * fr);
        last_abs = fabs(b) * sqrt(pr * pr + pi_ * pi_) * sqrt(fr * fr + fi * fi);
        fr *= Mm2; fi *= Mm2;
    }
    /* remainder bound: continue the rising factorial two more steps */
    double rr = pr, ri = pi_;
    for (long q = j; q < 2 * K + 1; q++) {
        double ar = sigma + (double)q, ai = t;
        double nr = rr * ar - ri * ai;
        double ni = rr * ai + ri * ar;
        rr = nr; ri = ni;
    }
    double rem = fabs(BERN_OVER_FACT[K])                  /* B_{2K+2}/(2K+2)! */
               * sqrt(rr * rr + ri * ri)
               * pow((double)M, -sigma - 2.0 * K - 1.0)
               / (sigma + 2.0 * K + 1.0);
    (void)last_abs;

    /* rounding budget: ~M compensated adds plus O(K) complex ops */
    double eps = 0x1p-53;
    double sumabs = 2.0 * sqrt((double)M) + 1.0;
    double round_e = 4.0 * eps * sumabs + t * 1e-30 * sumabs + 1e-13;

    /* Z = Re(e^{i theta} zeta) */
    dd th = rs_theta(dd_of(t));
    iv Th = iv_reduce_2pi(th, rs_theta_err(t));
    iv cT, sT;
    iv_sincos(Th, &sT, &cT);
    double tot = rem + round_e;
    iv ZR = iv_mk(zr - tot, zr + tot);
    iv ZI = iv_mk(zi - tot, zi + tot);
    return iv_sub(iv_mul(cT, ZR), iv_mul(sT, ZI));
}
