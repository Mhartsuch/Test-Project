import mpmath as mp
mp.mp.dps = 80

TWO_PI = 2*mp.pi
def psi(z): return mp.cos(TWO_PI*(z*z - z - mp.mpf(1)/16))/mp.cos(TWO_PI*z)

def dpsi(p, k, r=mp.mpf('0.5'), M=400):
    tot = mp.mpc(0)
    for j in range(M):
        phi = TWO_PI*(j+mp.mpf('0.5'))/M
        tot += psi(p + r*mp.exp(1j*phi))*mp.exp(-1j*k*phi)
    return mp.re(mp.factorial(k)*(tot/M)/r**k)

def main_sum(t, N):
    th = mp.siegeltheta(t)
    return 2*mp.fsum(mp.cos(th - t*mp.log(n))/mp.sqrt(n) for n in range(1, N+1))

def fit_Ck(p, Ns, nterms=7):
    rows, rhs = [], []
    for N in Ns:
        tau = N + mp.mpf(p); t = 2*mp.pi*tau**2
        r = (mp.siegelz(t) - main_sum(t, N))*(-1)**(N-1)*mp.sqrt(tau)
        rows.append([tau**(-k) for k in range(nterms)]); rhs.append(r)
    A = mp.matrix(rows); b = mp.matrix(rhs)
    return mp.lu_solve(A.T*A, A.T*b)

Ns = [18,22,26,30,36,42,50,60,72,86,100,120]
ps = ['0.05','0.13','0.21','0.29','0.37','0.44','0.58','0.66','0.71','0.83','0.91','0.97']

rows, rhs = [], []
print('fitted C_3(p) and the three basis derivatives:')
for ps_ in ps:
    p = mp.mpf(ps_)
    c3 = fit_Ck(p, Ns)[3]
    basis = [dpsi(p,1), dpsi(p,5), dpsi(p,9)]
    rows.append(basis); rhs.append(c3)
    print(f'  p={ps_}: C_3={mp.nstr(c3,10):>16}  psi1={mp.nstr(basis[0],8):>14} psi5={mp.nstr(basis[1],8):>14} psi9={mp.nstr(basis[2],8):>14}')

A = mp.matrix(rows); b = mp.matrix(rhs)
sol = mp.lu_solve(A.T*A, A.T*b)
print()
names = ['Psi^(1)','Psi^(5)','Psi^(9)']
pows  = [mp.pi**2, mp.pi**4, mp.pi**6]
pnames= ['pi^2','pi^4','pi^6']
for i in range(3):
    coef = sol[i]
    denom = 1/(coef*pows[i])          # coef = 1/(D * pi^{2i+2})  => D = 1/(coef pi^..)
    print(f'{names[i]}: coefficient {mp.nstr(coef,12):>18}   =  1 / ({mp.nstr(denom,14)} * {pnames[i]})')
