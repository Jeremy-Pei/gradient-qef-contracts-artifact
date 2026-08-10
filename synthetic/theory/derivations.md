# Gradient–Hermite–QEF contracts: definitions and derivations

## Status and scope

This document is an agent-drafted mathematical derivation for human review.
The finite experiments in `results/topic4_results.json` check implementations
of the inequalities but are not proofs.  Claims below marked **closed chain**
have a complete elementary argument written here; they should still be checked
line by line by the author before submission.

We use the signed-distance convention "positive outside".  Consequently, a
hard union is represented by a pointwise minimum.  All norms are Euclidean or
their induced matrix 2-norms unless stated otherwise.

---

## 1. Local gradient contract

Let (C\subset\mathbb R^d) be a cell or certified query neighborhood.  A local
field contract stores

\[
\mathcal C_C(\widehat\phi)
= (V_C,G_C,D_V,D_G,S_C),
\]

where (V_C) bounds the true value or the value error,
(G_C\subset\mathbb R^d) encloses the true gradient wherever it exists,
(D_V,D_G) are the respective validity domains, and (S_C) stores certified
branch information.  A common representation is

\[
\|\widehat\phi-\phi\|_{L^\infty(C)}\le\varepsilon,
\qquad
\|\nabla\widehat\phi-\nabla\phi\|\le g.
\]

The gradient object is a set.  A scalar (g) is only the radius of a ball
around an approximate gradient; it is not an adequate representation at every
Boolean switch.

---

## 2. Hard Boolean operations

### Theorem 1: no branch-independent single-normal continuity

**Statement.** Fix any angle (\theta\in(0,\pi]).  In every neighborhood of
the origin there are exact half-space SDFs (\phi_A,\phi_B), approximate SDFs
(\widehat\phi_A,\widehat\phi_B), and differentiability points (x_\varepsilon)
of both the exact and approximate hard minima such that

\[
\|\widehat\phi_i-\phi_i\|_\infty=\varepsilon,
\qquad
\nabla\widehat\phi_i=\nabla\phi_i,
\]

but

\[
\|\nabla\min(\widehat\phi_A,\widehat\phi_B)(x_\varepsilon)
-\nabla\min(\phi_A,\phi_B)(x_\varepsilon)\|
=2\sin(\theta/2).
\]

Thus no uniform single-normal error bound (F(\varepsilon,g)) with
(F(\varepsilon,g)\to0) as ((\varepsilon,g)\to(0,0)) can hold without a
positive branch margin or a set-valued conclusion.

**Proof (closed chain).** Choose unit vectors (n_A,n_B) with included angle
(\theta), let (d=n_B-n_A), and define exact half-space SDFs

\[
\phi_A(x)=n_A^\top x,
\qquad
\phi_B(x)=n_B^\top x.
\]

For every (\varepsilon>0), set

\[
x_\varepsilon=\frac{\varepsilon}{\|d\|^2}d,
\qquad
\widehat\phi_A=\phi_A+\varepsilon,
\qquad
\widehat\phi_B=\phi_B-\varepsilon.
\]

Because

\[
\phi_B(x_\varepsilon)-\phi_A(x_\varepsilon)
=d^\top x_\varepsilon=\varepsilon>0,
\]

the true minimum uniquely selects branch (A).  The approximate branch gap is

\[
\widehat\phi_B(x_\varepsilon)-\widehat\phi_A(x_\varepsilon)
=\varepsilon-2\varepsilon=-\varepsilon<0,
\]

so the approximate minimum uniquely selects branch (B).  Both minima are
therefore differentiable at (x_\varepsilon), and their gradients are (n_A)
and (n_B), respectively.  Finally,

\[
\|n_B-n_A\|^2=2-2\cos\theta=4\sin^2(\theta/2).
\]

Moreover (\|x_\varepsilon\|\to0), so the construction occurs arbitrarily
close to the switch while never evaluating the classical gradient at the
non-differentiable tie itself.  ∎

### Theorem 2: branch-separated inheritance

**Statement.** Suppose for all (x\in C),

\[
|\widehat\phi_i(x)-\phi_i(x)|\le\varepsilon_i,
\quad i\in\{A,B\},
\]

and

\[
\sup_C\widehat\phi_A+\varepsilon_A
<\inf_C\widehat\phi_B-\varepsilon_B. \tag{1}
\]

Then (\phi_A(x)<\phi_B(x)) throughout (C).  Hence for the hard union
(\psi=\min(\phi_A,\phi_B)), (\psi=\phi_A) on (C), and every valid value or
gradient contract of branch (A) transfers unchanged to (\psi) on (C).

**Proof (closed chain).** For every (x\in C),

\[
\phi_A(x)\le\widehat\phi_A(x)+\varepsilon_A
\le\sup_C\widehat\phi_A+\varepsilon_A,
\]

while

\[
\phi_B(x)\ge\widehat\phi_B(x)-\varepsilon_B
\ge\inf_C\widehat\phi_B-\varepsilon_B.
\]

Equation (1) therefore gives (\phi_A(x)<\phi_B(x)).  The minimum equals
(\phi_A) pointwise, so the inheritance claim is immediate. ∎

The symmetric condition selects (B).  Hard intersection follows by replacing
minimum with maximum and reversing the separation inequalities.

### Proposition 3: safe set-valued switch contract

Let (\phi_A,\phi_B) be continuously differentiable in a neighborhood of
(x), and let (\psi=\min(\phi_A,\phi_B)).  At a tie, every gradient limit of
(\psi) from differentiability points is a limiting gradient of an active
branch.  Consequently the Clarke generalized gradient satisfies the safe
enclosure

\[
\partial_C\psi(x)
\subseteq
\operatorname{conv}\{\nabla\phi_A(x),\nabla\phi_B(x)\}. \tag{2}
\]

If the operand gradients are themselves enclosed by sets (G_A,G_B) over a
cell, a safe cell-level enclosure is

\[
G_\psi\supseteq\operatorname{conv}(G_A\cup G_B). \tag{3}
\]

Equation (3) is not a single surface normal.  A downstream algorithm must keep
the active constraints separately, consume the set-valued normal, subdivide,
or return `Unknown`.

**Proof dependency.** Equation (2) uses the standard definition/calculus of
the Clarke generalized gradient.  The specialization to a finite minimum is
short, but the paper should cite a standard nonsmooth-analysis reference.

---

## 3. Smooth Boolean propagation

Let

\[
\psi_k(a,b)=-k\log(e^{-a/k}+e^{-b/k}),
\qquad k>0,
\]

and define

\[
w_A(a,b)=\frac{e^{-a/k}}{e^{-a/k}+e^{-b/k}},
\qquad w_B=1-w_A.
\]

Then

\[
\nabla\psi_k=w_A\nabla\phi_A+w_B\nabla\phi_B.
\]

### Theorem 4: executable binary smooth-min gradient bound

Assume at (x)

\[
|\widehat\phi_i-\phi_i|\le\varepsilon_i,
\qquad
\|\nabla\widehat\phi_i-\nabla\phi_i\|\le g_i,
\]

and let (\widehat w_i) be computed from the approximate field values.  If an
upstream gradient enclosure supplies

\[
M_{AB}\ge\|\nabla\phi_A-\nabla\phi_B\|,
\]

then

\[
\boxed{
\|\nabla\widehat\psi_k-\nabla\psi_k\|
\le
\widehat w_Ag_A+\widehat w_Bg_B
+\frac{\varepsilon_A+\varepsilon_B}{4k}M_{AB}.}
\tag{4}
\]

One executable choice is

\[
M_{AB}=\|\nabla\widehat\phi_A-\nabla\widehat\phi_B\|+g_A+g_B. \tag{5}
\]

**Proof (closed chain).** Add and subtract the true gradients under the
approximate weights:

\[
\begin{aligned}
\nabla\widehat\psi_k-\nabla\psi_k
={}&\widehat w_A(\nabla\widehat\phi_A-\nabla\phi_A)
+\widehat w_B(\nabla\widehat\phi_B-\nabla\phi_B)\\
&+(\widehat w_A-w_A)(\nabla\phi_A-\nabla\phi_B).
\end{aligned}
\]

The first line has norm at most
(\widehat w_Ag_A+\widehat w_Bg_B).  Write
(w_A=\sigma((b-a)/k)), where (\sigma'(z)=\sigma(z)(1-\sigma(z))\le1/4).
The mean-value theorem gives

\[
|\widehat w_A-w_A|
\le\frac{|(\widehat b-b)-(\widehat a-a)|}{4k}
\le\frac{\varepsilon_A+\varepsilon_B}{4k}.
\]

Multiplication by (M_{AB}) proves (4).  Equation (5) follows from the triangle
inequality. ∎

The factor (1/k) correctly records loss of conditioning as the smooth
operator approaches a hard minimum.  Omitting this coupling is unsound; the
frozen experiment contains explicit finite counterexamples.

No unit-gradient or eikonal assumption is used.  The proof needs only the
stated value and gradient budgets, and the executable (M_{AB}) follows from
the triangle inequality for arbitrary operand-gradient norms.

---

## 4. From a field contract to a Hermite-plane contract

### Theorem 5: edge-root displacement

Parameterize a grid edge by arc length (s\in[0,L]).  Suppose (f) is
continuously differentiable, has a root (s_\star), and

\[
|f'(s)|\ge m_e>0 \quad\text{for all }s\in[0,L]. \tag{6}
\]

Let (\widehat f) obey
(\|\widehat f-f\|_\infty\le\varepsilon_\phi), and let a numerical root
(\widehat s\in[0,L]) satisfy

\[
|\widehat f(\widehat s)|\le\eta_{\rm solve}.
\]

Then (f) is strictly monotone, its root is unique, and

\[
|\widehat s-s_\star|
\le\eta_p:=\frac{\varepsilon_\phi+\eta_{\rm solve}}{m_e}. \tag{7}
\]

**Proof (closed chain).** Continuity of (f') and (6) prevent its sign from
changing, so (f) is strictly monotone.  Further,

\[
|f(\widehat s)|
\le|f(\widehat s)-\widehat f(\widehat s)|
+|\widehat f(\widehat s)|
\le\varepsilon_\phi+\eta_{\rm solve}.
\]

The mean-value theorem and (6) give

\[
|f(\widehat s)-f(s_\star)|\ge m_e|\widehat s-s_\star|.
\]

Since (f(s_\star)=0), equation (7) follows. ∎

### Lemma 6: normalization transfer

If (u\ne0), (\|u-v\|\le g<\|u\|), and
(\|u\|\ge\mu>0), then (v\ne0) and

\[
\left\|\frac{u}{\|u\|}-\frac{v}{\|v\|}\right\|
\le\frac{2g}{\mu}=: \eta_n. \tag{8}
\]

**Proof (closed chain).** The reverse triangle inequality gives
(\|v\|\ge\|u\|-g>0).  Add and subtract (v/\|u\|):

\[
\left\|\frac{u-v}{\|u\|}
+v\left(\frac1{\|u\|}-\frac1{\|v\|}\right)\right\|
\le\frac{\|u-v\|}{\|u\|}
+\frac{|\|v\|-\|u\||}{\|u\|}
\le\frac{2g}{\mu}.
\]

### Lemma 7: local Hermite-plane offset

Let (c) be the cell center, (p,\widehat p) true and approximate edge roots,
and (n,\widehat n) their unit normals.  Define local plane offsets

\[
h=n^\top(p-c),
\qquad
\widehat h=\widehat n^\top(\widehat p-c).
\]

If

\[
\|p-c\|\le R_c,
\quad\|\widehat p-p\|\le\eta_p,
\quad\|\widehat n-n\|\le\eta_n,
\]

then

\[
|\widehat h-h|\le\eta_p+R_c\eta_n=: \eta_h^{\rm loc}. \tag{9}
\]

**Proof (closed chain).** Use

\[
\widehat h-h
=(\widehat n-n)^\top(p-c)
+\widehat n^\top(\widehat p-p)
\]

and apply Cauchy–Schwarz with (\|\widehat n\|=1). ∎

The use of (p-c), rather than a global coordinate (p), makes (9) invariant
under global translation and keeps the budget on the cell scale.

---

## 5. From Hermite planes to a QEF vertex

Stack unit normals as rows of (N\in\mathbb R^{m\times d}) and local plane
offsets into (h\in\mathbb R^m).  Use the regularized QEF

\[
\min_y\|Ny-h\|_2^2+\lambda\|y\|_2^2,
\quad
H=N^\top N+\lambda I,
\quad
q=N^\top h. \tag{10}
\]

The approximate quantities carry hats.  Assume row-wise contracts

\[
\|n_i-\widehat n_i\|\le\eta_{n,i},
\qquad
|h_i-\widehat h_i|\le\eta_{h,i}.
\]

Set

\[
\eta_N=\left(\sum_i\eta_{n,i}^2\right)^{1/2},
\qquad
E_h=\left(\sum_i\eta_{h,i}^2\right)^{1/2}. \tag{11}
\]

Then (\|N-\widehat N\|_2\le\eta_N) and
(\|h-\widehat h\|_2\le E_h).

### Lemma 8: observed-side matrix and right-hand-side budgets

Define

\[
\eta_H=2\|\widehat N\|_2\eta_N+\eta_N^2, \tag{12}
\]

\[
\eta_q=\|\widehat N\|_2E_h
+\eta_N\|\widehat h\|_2
+\eta_NE_h. \tag{13}
\]

Then

\[
\|H-\widehat H\|_2\le\eta_H,
\qquad
\|q-\widehat q\|_2\le\eta_q.
\]

**Proof (closed chain).** Let (E=N-\widehat N) and
(e=h-\widehat h).  From (11), (\|E\|_2\le\|E\|_F\le\eta_N) and
(\|e\|_2\le E_h).  Expanding gives

\[
H-\widehat H
=\widehat N^\top E+E^\top\widehat N+E^\top E,
\]

which yields (12).  Likewise,

\[
q-\widehat q
=\widehat N^\top e+E^\top\widehat h+E^\top e,
\]

which yields (13). ∎

The Frobenius aggregation in (11) is intentionally worst case. If an upstream
producer can certify an operator-norm budget
(`eta_N_op >= ||N-Nhat||_2`), then every step above remains valid with
`eta_N_op` in place of `eta_N`. A smaller realized operator norm computed from
the unknown true matrix is only an oracle diagnostic, not a deployable input.

### Theorem 9: observed-side certified regularized QEF displacement

Let (\lambda\ge0), and let (\widehat y) solve
(\widehat H\widehat y=\widehat q), and define the computable lower bound

\[
\underline\gamma
:=\max\{\lambda,\lambda_{\min}(\widehat H)-\eta_H\}. \tag{14}
\]

If (\underline\gamma>0), then the true (H) is positive definite and its
solution (y) obeys

\[
\boxed{
\|\widehat y-y\|_2
\le
\frac{\eta_H\|\widehat y\|_2+\eta_q}{\underline\gamma}.}
\tag{15}
\]

**Proof (closed chain).** Because (H=N^\top N+\lambda I),
(\lambda_{\min}(H)\ge\lambda).  Weyl's eigenvalue perturbation inequality and
(12) also give

\[
\lambda_{\min}(H)
\ge\lambda_{\min}(\widehat H)-\|H-\widehat H\|_2
\ge\lambda_{\min}(\widehat H)-\eta_H.
\]

Taking the larger lower bound gives
(\lambda_{\min}(H)\ge\underline\gamma>0).  Thus (H) is invertible and
(\|H^{-1}\|_2\le1/\underline\gamma).  Since
(H y=q) and (\widehat H\widehat y=\widehat q),

\[
H(\widehat y-y)
=(H-\widehat H)\widehat y+(\widehat q-q).
\]

Taking norms and applying (12)–(14) proves (15). ∎

Equation (15) is an absolute, cell-local displacement bound.  For
(\lambda>0), it is always finite once the upstream Hermite budgets are finite;
when the data term is nearly singular, the lower bound falls back to
(\lambda) and may be too loose to be useful.  For (\lambda=0), a positive
observed-side spectral gap is required.  A consumer may
declare a vertex useful at tolerance (\tau) only if the right-hand side is at
most (\tau).  A finite sound bound does not imply that the bound is tight or
useful.

For (\lambda>0), the QEF well-posedness test alone never returns Unknown
because (\underline\gamma\ge\lambda>0).  The full consumer remains
fail-closed: all upstream validity, branch, root, and normal obligations must
pass, and a finite bound larger than (\tau) yields Unknown.  Any heuristic
fallback is explicitly uncertified.

If (\widehat H) is positive definite and
(\|\widehat H^{-1}\|_2\eta_H<1), the direct Neumann estimate is

\[
\|H^{-1}\|_2
\le
\frac{\|\widehat H^{-1}\|_2}
{1-\|\widehat H^{-1}\|_2\eta_H}
=\frac{1}{\lambda_{\min}(\widehat H)-\eta_H}.
\]

This reproduces the observed spectral term in (14). Since (\underline\gamma)
is the maximum of that term and (\lambda), substituting this Neumann estimate
cannot tighten (15) when the numerator and perturbation budgets are unchanged.

---

## 6. Composition statement and open obligations

The closed chain for one regularized QEF cell is:

1. a field value contract and derivative lower bound certify an edge root via
   Theorem 5;
2. a gradient contract and gradient-norm lower bound certify a unit normal via
   Lemma 6;
3. these budgets certify a local Hermite plane via Lemma 7;
4. the collection of Hermite planes gives (\eta_N,E_h) via (11);
5. the observed QEF gives a spectral guard and vertex bound via Theorem 9.

For hard Boolean cells, this chain additionally requires either certified
branch separation (Theorem 2) or a downstream treatment that preserves the
set-valued/multiple constraints of Proposition 3.

The following are **not closed by this document**:

- a producer for certified value/gradient intervals for arbitrary neural or
  sampled fields;
- an adaptive-octree crack-freedom or topology theorem;
- a complete mixed-operator deep-CSG composition theorem;
- a certificate for heuristic SVD rank truncation when a singular-value
  interval straddles the chosen threshold;
- a large-corpus engineering evaluation.
