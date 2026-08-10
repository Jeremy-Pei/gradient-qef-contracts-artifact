#!/usr/bin/env python3
"""Generate frozen evidence for the topic-4 gradient/Hermite/QEF contracts.

The script uses only NumPy and the Python standard library.  It records finite
tests of analytic inequalities; it does not treat zero observed violations as
a proof.  The proofs are stated separately in theory/derivations.md.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np


SEED = 20260808


def _unit_rows(x: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(x, axis=1, keepdims=True)
    return x / np.maximum(norms, np.finfo(float).tiny)


def _stable_weight_a(a: np.ndarray, b: np.ndarray, k: np.ndarray) -> np.ndarray:
    # w_A = exp(-a/k) / (exp(-a/k) + exp(-b/k))
    z = np.clip((a - b) / k, -700.0, 700.0)
    return 1.0 / (1.0 + np.exp(z))


def _quantiles(x: np.ndarray) -> dict[str, float]:
    if x.size == 0:
        return {"q05": None, "q50": None, "q95": None, "max": None}
    q = np.quantile(x, [0.05, 0.5, 0.95, 1.0])
    return {"q05": float(q[0]), "q50": float(q[1]),
            "q95": float(q[2]), "max": float(q[3])}


def _cp_lower_all_successes(n: int, alpha: float = 0.05) -> float | None:
    # Exact one-sided Clopper-Pearson lower bound when all n trials succeed.
    return float(alpha ** (1.0 / n)) if n > 0 else None


def experiment_hard_switch() -> dict:
    epsilons = np.logspace(-1, -10, 10)
    rows = []
    for angle_deg in (30.0, 90.0, 150.0):
        theta = math.radians(angle_deg)
        n_a = np.array([1.0, 0.0])
        n_b = np.array([math.cos(theta), math.sin(theta)])
        d = n_b - n_a
        jump = float(np.linalg.norm(d))
        for eps in epsilons:
            # The true branch gap is eps>0, so the exact hard minimum is smooth
            # at x. Opposite constant offsets, each of magnitude eps, reverse
            # the active branch without changing either input gradient.
            x = (eps / float(np.dot(d, d))) * d
            a = float(np.dot(n_a, x))
            b = float(np.dot(n_b, x))
            ah = a + eps
            bh = b - eps
            if not (a < b and bh < ah):
                raise AssertionError("hard-switch construction did not flip")
            rows.append({
                "angle_deg": angle_deg,
                "epsilon": float(eps),
                "true_gap": float(b - a),
                "query_norm": float(np.linalg.norm(x)),
                "gradient_error": jump,
                "theoretical_jump": float(2.0 * math.sin(theta / 2.0)),
            })
    return {
        "description": "Differentiable points approaching a hard-min switch",
        "sample_count": len(rows),
        "rows": rows,
        "violations": int(sum(abs(r["gradient_error"] - r["theoretical_jump"]) > 1e-12
                              for r in rows)),
    }


def experiment_smooth_min(rng: np.random.Generator, n: int = 250_000) -> dict:
    a = rng.uniform(-2.0, 2.0, n)
    b = rng.uniform(-2.0, 2.0, n)
    k = np.exp(rng.uniform(math.log(0.01), math.log(0.5), n))
    eps_a = np.exp(rng.uniform(math.log(1e-6), math.log(2e-2), n))
    eps_b = np.exp(rng.uniform(math.log(1e-6), math.log(2e-2), n))
    da = rng.uniform(-1.0, 1.0, n) * eps_a
    db = rng.uniform(-1.0, 1.0, n) * eps_b

    grad_a = _unit_rows(rng.normal(size=(n, 3))) * rng.uniform(0.5, 1.5, (n, 1))
    grad_b = _unit_rows(rng.normal(size=(n, 3))) * rng.uniform(0.5, 1.5, (n, 1))
    g_a = np.exp(rng.uniform(math.log(1e-6), math.log(5e-2), n))
    g_b = np.exp(rng.uniform(math.log(1e-6), math.log(5e-2), n))
    dir_a = _unit_rows(rng.normal(size=(n, 3)))
    dir_b = _unit_rows(rng.normal(size=(n, 3)))
    mag_a = rng.uniform(0.0, 1.0, n) * g_a
    mag_b = rng.uniform(0.0, 1.0, n) * g_b
    grad_ah = grad_a + dir_a * mag_a[:, None]
    grad_bh = grad_b + dir_b * mag_b[:, None]

    w_a = _stable_weight_a(a, b, k)
    wh_a = _stable_weight_a(a + da, b + db, k)
    w_b = 1.0 - w_a
    wh_b = 1.0 - wh_a
    true_grad = w_a[:, None] * grad_a + w_b[:, None] * grad_b
    approx_grad = wh_a[:, None] * grad_ah + wh_b[:, None] * grad_bh
    actual = np.linalg.norm(approx_grad - true_grad, axis=1)

    # Executable upper bound on the unknown true gradient difference.
    m_ab = np.linalg.norm(grad_ah - grad_bh, axis=1) + g_a + g_b
    input_term = wh_a * g_a + wh_b * g_b
    coupling = (eps_a + eps_b) * m_ab / (4.0 * k)
    bound = input_term + coupling
    naive_bound = input_term  # Ablation: omit value-to-gradient coupling.
    tol = 2e-12 * np.maximum(1.0, bound)
    complete_violations = actual > bound + tol
    naive_violations = actual > naive_bound + tol
    ratio = bound / np.maximum(actual, 1e-15)

    take = np.linspace(0, n - 1, 800, dtype=int)
    return {
        "description": "Binary log-sum-exp gradient propagation",
        "sample_count": n,
        "k_range": [float(k.min()), float(k.max())],
        "complete_violations": int(np.count_nonzero(complete_violations)),
        "naive_without_coupling_violations": int(np.count_nonzero(naive_violations)),
        "naive_without_coupling_violation_rate": float(np.mean(naive_violations)),
        "all_successes_cp95_lower": _cp_lower_all_successes(
            n - int(np.count_nonzero(complete_violations))),
        "bound_to_actual": _quantiles(ratio[np.isfinite(ratio)]),
        "plot_samples": [
            {"actual": float(actual[i]), "bound": float(bound[i]),
             "naive_bound": float(naive_bound[i]), "k": float(k[i])}
            for i in take
        ],
    }


def _bisect_root(func, lo: float = 0.0, hi: float = 1.0,
                 iterations: int = 64) -> tuple[float, float]:
    flo = func(lo)
    fhi = func(hi)
    if flo == 0.0:
        return lo, 0.0
    if fhi == 0.0:
        return hi, 0.0
    if flo * fhi > 0.0:
        raise ValueError("root is not bracketed")
    for _ in range(iterations):
        mid = 0.5 * (lo + hi)
        fm = func(mid)
        if flo * fm <= 0.0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    root = 0.5 * (lo + hi)
    return root, abs(func(root))


def experiment_hermite_root(rng: np.random.Generator, n: int = 30_000) -> dict:
    actuals = np.empty(n)
    bounds = np.empty(n)
    residuals = np.empty(n)
    violations = 0
    for i in range(n):
        root_true = rng.uniform(0.2, 0.8)
        slope = rng.uniform(0.5, 2.0)
        cubic = rng.uniform(0.0, 2.0)
        eps = math.exp(rng.uniform(math.log(1e-6), math.log(1e-2)))
        omega = rng.uniform(1.0, 30.0)
        phase = rng.uniform(-math.pi, math.pi)

        def f(t: float) -> float:
            z = t - root_true
            return slope * z + cubic * z * z * z

        def fh(t: float) -> float:
            return f(t) + eps * math.sin(omega * t + phase)

        root_hat, residual = _bisect_root(fh)
        actual = abs(root_hat - root_true)
        bound = (eps + residual) / slope
        if actual > bound + 5e-13:
            violations += 1
        actuals[i] = actual
        bounds[i] = bound
        residuals[i] = residual
    ratio = bounds / np.maximum(actuals, 1e-15)
    take = np.linspace(0, n - 1, 600, dtype=int)
    return {
        "description": "Monotone edge root under bounded value error",
        "sample_count": n,
        "complete_violations": violations,
        "all_successes_cp95_lower": _cp_lower_all_successes(n - violations),
        "bound_to_actual": _quantiles(ratio[np.isfinite(ratio)]),
        "max_solver_residual": float(residuals.max()),
        "plot_samples": [
            {"actual": float(actuals[i]), "bound": float(bounds[i])}
            for i in take
        ],
    }


def _orthogonal_tangent(n: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    v = rng.normal(size=3)
    v = v - np.dot(v, n) * n
    norm = np.linalg.norm(v)
    if norm < 1e-12:
        axis = np.array([1.0, 0.0, 0.0]) if abs(n[0]) < 0.8 else np.array([0.0, 1.0, 0.0])
        v = axis - np.dot(axis, n) * n
        norm = np.linalg.norm(v)
    return v / norm


def _normal_configuration(name: str, m: int, rng: np.random.Generator) -> np.ndarray:
    if name == "orthogonal":
        base = np.eye(3)
        return np.vstack([base[i % 3] for i in range(m)])
    if name == "edge20":
        theta = math.radians(20.0)
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([math.cos(theta), math.sin(theta), 0.0])
        return np.vstack([a if i % 2 == 0 else b for i in range(m)])
    if name == "near_planar":
        rows = np.array([[rng.normal(0.0, 0.025), rng.normal(0.0, 0.025), 1.0]
                         for _ in range(m)])
        return _unit_rows(rows)
    if name == "random":
        return _unit_rows(rng.normal(size=(m, 3)))
    raise ValueError(name)


def _perturb_normal(n: np.ndarray, budget: float,
                    rng: np.random.Generator) -> tuple[np.ndarray, float]:
    distance = rng.uniform(0.0, budget)
    angle = 2.0 * math.asin(min(1.0, 0.5 * distance))
    tangent = _orthogonal_tangent(n, rng)
    nh = math.cos(angle) * n + math.sin(angle) * tangent
    return nh / np.linalg.norm(nh), distance


def _unregularized_qef_residual(nmat: np.ndarray, h: np.ndarray) -> float:
    """Return the minimum data-term residual, without regularization."""
    y_ls, *_ = np.linalg.lstsq(nmat, h, rcond=None)
    return float(np.linalg.norm(nmat @ y_ls - h))


def _evaluate_qef_contract(nmat: np.ndarray, p: np.ndarray,
                           budget_n: float, budget_p: float, lam: float,
                           rng: np.random.Generator, rc: float) -> dict:
    """Evaluate the complete theorem and point-budget ablation for one QEF."""
    m = nmat.shape[0]
    nhat = np.empty_like(nmat)
    phat = np.empty_like(p)
    for i in range(m):
        nhat[i], _ = _perturb_normal(nmat[i], budget_n, rng)
        direction = rng.normal(size=3)
        direction /= np.linalg.norm(direction)
        phat[i] = p[i] + direction * rng.uniform(0.0, budget_p)

    h = np.einsum("ij,ij->i", nmat, p)
    hhat = np.einsum("ij,ij->i", nhat, phat)
    hess = nmat.T @ nmat + lam * np.eye(3)
    hess_hat = nhat.T @ nhat + lam * np.eye(3)
    q = nmat.T @ h
    qhat = nhat.T @ hhat
    y = np.linalg.solve(hess, q)
    yhat = np.linalg.solve(hess_hat, qhat)
    actual = float(np.linalg.norm(yhat - y))

    eta_n = math.sqrt(m) * budget_n
    eta_h = math.sqrt(m) * (budget_p + rc * budget_n)
    norm_nhat = float(np.linalg.norm(nhat, 2))
    eta_hess = 2.0 * norm_nhat * eta_n + eta_n * eta_n
    eta_q = (norm_nhat * eta_h + eta_n * float(np.linalg.norm(hhat))
             + eta_n * eta_h)
    lmin_hat = float(np.linalg.eigvalsh(hess_hat)[0])
    denominator = max(lam, lmin_hat - eta_hess)
    bound = ((eta_hess * float(np.linalg.norm(yhat)) + eta_q)
             / denominator)

    eta_h_incomplete = math.sqrt(m) * (rc * budget_n)
    eta_q_incomplete = (
        norm_nhat * eta_h_incomplete
        + eta_n * float(np.linalg.norm(hhat))
        + eta_n * eta_h_incomplete
    )
    incomplete_bound = (
        eta_hess * float(np.linalg.norm(yhat)) + eta_q_incomplete
    ) / denominator
    residual = _unregularized_qef_residual(nmat, h)
    scale = 2e-11 * max(1.0, bound)
    return {
        "actual": actual,
        "bound": float(bound),
        "bound_to_actual": float(bound / max(actual, 1e-15)),
        "complete_violation": bool(actual > bound + scale),
        "incomplete_bound": float(incomplete_bound),
        "incomplete_violation": bool(
            actual > incomplete_bound + 2e-11 * max(1.0, incomplete_bound)),
        "unregularized_data_residual": residual,
    }


def experiment_qef(rng: np.random.Generator, per_config: int = 10_000) -> dict:
    configs = ("orthogonal", "random", "edge20", "near_planar")
    tolerances = (0.01, 0.05, 0.10, 0.25)
    rc = math.sqrt(3.0) / 2.0  # half diagonal of a unit cube
    by_config = {}
    total = 0
    finite_bounds = 0
    data_identifiable = 0
    complete_violations = 0
    realized_budget_violations = 0
    matrix_oracle_violations = 0
    incomplete_violations = 0
    incomplete_certified = 0
    complete_ratios = []
    complete_bounds = []
    complete_actuals = []
    realized_budget_bounds = []
    matrix_oracle_bounds = []
    data_residuals = []
    plot_samples = []

    for name in configs:
        c_total = c_finite = c_data = c_viol = c_incomplete_viol = 0
        c_realized_viol = c_matrix_viol = 0
        c_ratios = []
        c_bounds = []
        c_actuals = []
        c_realized_bounds = []
        c_matrix_bounds = []
        c_data_residuals = []
        for j in range(per_config):
            m = 6
            nmat = _normal_configuration(name, m, rng)
            y_target = rng.uniform(-0.28, 0.28, 3)
            p = np.tile(y_target, (m, 1))
            budget_n = math.exp(rng.uniform(math.log(1e-4), math.log(3e-2)))
            budget_p = math.exp(rng.uniform(math.log(1e-5), math.log(3e-2)))
            lam = math.exp(rng.uniform(math.log(2e-3), math.log(2e-1)))

            nhat = np.empty_like(nmat)
            phat = np.empty_like(p)
            realized_n = np.empty(m)
            realized_p = np.empty(m)
            for i in range(m):
                nhat[i], realized_n[i] = _perturb_normal(
                    nmat[i], budget_n, rng)
                direction = rng.normal(size=3)
                direction /= np.linalg.norm(direction)
                realized_p[i] = rng.uniform(0.0, budget_p)
                phat[i] = p[i] + direction * realized_p[i]

            h = np.einsum("ij,ij->i", nmat, p)
            hhat = np.einsum("ij,ij->i", nhat, phat)
            hess = nmat.T @ nmat + lam * np.eye(3)
            hess_hat = nhat.T @ nhat + lam * np.eye(3)
            q = nmat.T @ h
            qhat = nhat.T @ hhat
            y = np.linalg.solve(hess, q)
            yhat = np.linalg.solve(hess_hat, qhat)
            actual = float(np.linalg.norm(yhat - y))
            data_residual = _unregularized_qef_residual(nmat, h)

            eta_n = math.sqrt(m) * budget_n
            eta_h = math.sqrt(m) * (budget_p + rc * budget_n)
            norm_nhat = float(np.linalg.norm(nhat, 2))
            eta_hess = 2.0 * norm_nhat * eta_n + eta_n * eta_n
            eta_q = (norm_nhat * eta_h + eta_n * float(np.linalg.norm(hhat))
                     + eta_n * eta_h)
            lmin_hat = float(np.linalg.eigvalsh(hess_hat)[0])
            # H=N^T N+lambda I always has lambda as a certified lower
            # eigenvalue.  The observed data can improve that lower bound.
            data_gap = (lmin_hat - lam) - eta_hess
            denominator = lam + max(0.0, data_gap)
            if data_gap > 0.0:
                c_data += 1
                data_identifiable += 1

            bound = ((eta_hess * float(np.linalg.norm(yhat)) + eta_q)
                     / denominator)
            c_finite += 1
            finite_bounds += 1
            ratio = bound / max(actual, 1e-15)
            c_ratios.append(ratio)
            c_bounds.append(bound)
            c_actuals.append(actual)
            complete_ratios.append(ratio)
            complete_bounds.append(bound)
            complete_actuals.append(actual)
            c_data_residuals.append(data_residual)
            data_residuals.append(data_residual)
            if actual > bound + 2e-11 * max(1.0, bound):
                c_viol += 1
                complete_violations += 1

            # Diagnostic arm 1: replace declared row budgets by the errors that
            # actually occurred in this synthetic trial.  This still uses the
            # same proof formulas and is not deployable because it sees truth.
            eta_n_realized = float(np.linalg.norm(realized_n))
            e_h_realized = float(np.linalg.norm(realized_p + rc * realized_n))
            eta_hess_realized = (
                2.0 * norm_nhat * eta_n_realized
                + eta_n_realized * eta_n_realized
            )
            eta_q_realized = (
                norm_nhat * e_h_realized
                + eta_n_realized * float(np.linalg.norm(hhat))
                + eta_n_realized * e_h_realized
            )
            realized_denominator = max(
                lam, lmin_hat - eta_hess_realized)
            realized_bound = (
                eta_hess_realized * float(np.linalg.norm(yhat))
                + eta_q_realized
            ) / realized_denominator
            c_realized_bounds.append(realized_bound)
            realized_budget_bounds.append(realized_bound)
            if actual > realized_bound + 2e-11 * max(1.0, realized_bound):
                c_realized_viol += 1
                realized_budget_violations += 1

            # Diagnostic arm 2: use the exact matrix/right-hand-side
            # perturbations and the true smallest eigenvalue.  It isolates
            # slack introduced by row aggregation, triangle inequalities, and
            # the observed-side spectral lower bound.  It is an oracle, not a
            # runtime certificate.
            exact_hess_delta = float(np.linalg.norm(hess - hess_hat, 2))
            exact_q_delta = float(np.linalg.norm(q - qhat))
            exact_gamma = float(np.linalg.eigvalsh(hess)[0])
            matrix_bound = (
                exact_hess_delta * float(np.linalg.norm(yhat))
                + exact_q_delta
            ) / exact_gamma
            c_matrix_bounds.append(matrix_bound)
            matrix_oracle_bounds.append(matrix_bound)
            if actual > matrix_bound + 2e-11 * max(1.0, matrix_bound):
                c_matrix_viol += 1
                matrix_oracle_violations += 1

            # Ablation: omit the certified Hermite-point error budget.
            eta_h_incomplete = math.sqrt(m) * (rc * budget_n)
            eta_q_incomplete = (
                norm_nhat * eta_h_incomplete
                + eta_n * float(np.linalg.norm(hhat))
                + eta_n * eta_h_incomplete
            )
            incomplete_bound = (
                eta_hess * float(np.linalg.norm(yhat)) + eta_q_incomplete
            ) / denominator
            incomplete_certified += 1
            if actual > incomplete_bound + 2e-11 * max(1.0, incomplete_bound):
                incomplete_violations += 1
                c_incomplete_viol += 1

            if len(plot_samples) < 1200 and j % 17 == 0:
                plot_samples.append({
                    "config": name,
                    "actual": actual,
                    "bound": float(bound),
                    "realized_budget_bound": float(realized_bound),
                    "matrix_oracle_bound": float(matrix_bound),
                    "incomplete_bound": float(incomplete_bound),
                    "data_spectral_gap": float(data_gap),
                    "denominator": float(denominator),
                })
            c_total += 1
            total += 1

        c_bounds_array = np.asarray(c_bounds)
        c_actuals_array = np.asarray(c_actuals)
        c_realized_array = np.asarray(c_realized_bounds)
        c_matrix_array = np.asarray(c_matrix_bounds)
        c_tolerance = {}
        for tolerance in tolerances:
            key = f"{tolerance:.2f}"
            c_tolerance[key] = {
                "measured_actual": float(np.mean(c_actuals_array <= tolerance)),
                "declared_contract": float(np.mean(c_bounds_array <= tolerance)),
                "realized_budget_diagnostic": float(
                    np.mean(c_realized_array <= tolerance)),
                "matrix_oracle_diagnostic": float(
                    np.mean(c_matrix_array <= tolerance)),
            }

        by_config[name] = {
            "total": c_total,
            "finite_bounds": c_finite,
            "finite_bound_coverage": c_finite / c_total,
            "data_identifiable": c_data,
            "data_identifiability_coverage": c_data / c_total,
            "complete_violations": c_viol,
            "realized_budget_diagnostic_violations": c_realized_viol,
            "matrix_oracle_diagnostic_violations": c_matrix_viol,
            "incomplete_bridge_violations": c_incomplete_viol,
            "bound_to_actual": _quantiles(np.asarray(c_ratios)),
            "absolute_bound": _quantiles(c_bounds_array),
            "absolute_actual_error": _quantiles(c_actuals_array),
            "unregularized_data_residual": _quantiles(
                np.asarray(c_data_residuals)),
            "realized_budget_diagnostic_bound": _quantiles(c_realized_array),
            "matrix_oracle_diagnostic_bound": _quantiles(c_matrix_array),
            "tolerance_coverage": c_tolerance,
        }

    bounds_array = np.asarray(complete_bounds)
    actuals_array = np.asarray(complete_actuals)
    tolerance_coverage = {}
    realized_array = np.asarray(realized_budget_bounds)
    matrix_array = np.asarray(matrix_oracle_bounds)
    for tolerance in tolerances:
        useful = int(np.count_nonzero(bounds_array <= tolerance))
        useful_violations = int(np.count_nonzero(
            (bounds_array <= tolerance) & (actuals_array > bounds_array + 2e-11)
        ))
        tolerance_coverage[f"{tolerance:.2f}"] = {
            "measured_actual_coverage": float(
                np.mean(actuals_array <= tolerance)),
            "certified_within_tolerance": useful,
            "coverage_of_all_queries": useful / total,
            "realized_budget_diagnostic_coverage": float(
                np.mean(realized_array <= tolerance)),
            "matrix_oracle_diagnostic_coverage": float(
                np.mean(matrix_array <= tolerance)),
            "violations": useful_violations,
        }

    return {
        "description": "Observed-side regularized QEF certificate",
        "sample_count": total,
        "finite_bounds": finite_bounds,
        "finite_bound_coverage": finite_bounds / total,
        "data_identifiable": data_identifiable,
        "data_identifiability_coverage": data_identifiable / total,
        "complete_violations": complete_violations,
        "realized_budget_diagnostic_violations": realized_budget_violations,
        "matrix_oracle_diagnostic_violations": matrix_oracle_violations,
        "certified_all_successes_cp95_lower": _cp_lower_all_successes(
            finite_bounds - complete_violations),
        "bound_to_actual": _quantiles(np.asarray(complete_ratios)),
        "absolute_bound": _quantiles(bounds_array),
        "absolute_actual_error": _quantiles(actuals_array),
        "unregularized_data_residual": _quantiles(
            np.asarray(data_residuals)),
        "realized_budget_diagnostic_bound": _quantiles(realized_array),
        "matrix_oracle_diagnostic_bound": _quantiles(matrix_array),
        "tolerance_coverage": tolerance_coverage,
        "incomplete_bridge_certified": incomplete_certified,
        "incomplete_bridge_violations": incomplete_violations,
        "incomplete_bridge_violation_rate": (
            incomplete_violations / incomplete_certified
            if incomplete_certified else None
        ),
        "by_configuration": by_config,
        "plot_samples": plot_samples,
    }


def _inconsistent_plane_system(rng: np.random.Generator, m: int,
                               config: str) -> tuple[np.ndarray, np.ndarray]:
    """Construct planes with a controlled component outside range(N)."""
    nmat = _normal_configuration(config, m, rng)
    anchor = rng.uniform(-0.20, 0.20, 3)
    trial = rng.normal(size=m)
    projected = nmat @ np.linalg.lstsq(nmat, trial, rcond=None)[0]
    residual = trial - projected
    residual_norm = float(np.linalg.norm(residual))
    if residual_norm < 1e-10:
        raise AssertionError("failed to construct an inconsistent plane system")
    target_residual = math.exp(
        rng.uniform(math.log(1e-4), math.log(8e-2)))
    residual *= target_residual / residual_norm
    # Since each row normal is unit, n_i^T(anchor+r_i n_i)
    # equals n_i^T anchor+r_i and realizes the prescribed inconsistent offset.
    p = anchor[None, :] + residual[:, None] * nmat
    return nmat, p


def _sphere_patch(rng: np.random.Generator, m: int) -> tuple[np.ndarray, np.ndarray]:
    center = rng.uniform(-0.08, 0.08, 3)
    radius = rng.uniform(0.25, 0.42)
    base = rng.normal(size=3)
    base /= np.linalg.norm(base)
    normals = []
    for _ in range(m):
        tangent = _orthogonal_tangent(base, rng)
        angle = rng.uniform(-0.55, 0.55)
        direction = math.cos(angle) * base + math.sin(angle) * tangent
        normals.append(direction / np.linalg.norm(direction))
    nmat = np.asarray(normals)
    p = center[None, :] + radius * nmat
    return nmat, p


def _paraboloid_patch(rng: np.random.Generator,
                      m: int) -> tuple[np.ndarray, np.ndarray]:
    cx, cy, z0 = rng.uniform(-0.10, 0.10, 3)
    curvature_x = rng.uniform(0.35, 1.15)
    curvature_y = rng.uniform(0.35, 1.15)
    uv = rng.uniform(-0.26, 0.26, (m, 2))
    u = uv[:, 0]
    v = uv[:, 1]
    p = np.column_stack([
        cx + u,
        cy + v,
        z0 + curvature_x * u * u + curvature_y * v * v,
    ])
    nmat = _unit_rows(np.column_stack([
        -2.0 * curvature_x * u,
        -2.0 * curvature_y * v,
        np.ones(m),
    ]))
    return nmat, p


def experiment_qef_residual_stress(
        rng: np.random.Generator, per_kind: int = 10_000) -> dict:
    """Audit Theorem 7 beyond compatible, common-point Hermite planes."""
    kinds = ("inconsistent_planes", "curved_patch")
    tolerances = (0.01, 0.05, 0.10, 0.25)
    rc = math.sqrt(3.0) / 2.0
    configurations = ("orthogonal", "random", "edge20", "near_planar")
    by_kind = {}
    all_actuals = []
    all_bounds = []
    all_ratios = []
    all_residuals = []
    complete_violations = 0
    incomplete_violations = 0
    surface_subtypes = {"sphere": 0, "paraboloid": 0}

    for kind in kinds:
        actuals = []
        bounds = []
        ratios = []
        residuals = []
        kind_violations = 0
        kind_incomplete_violations = 0
        for j in range(per_kind):
            m = 6
            if kind == "inconsistent_planes":
                nmat, p = _inconsistent_plane_system(
                    rng, m, configurations[j % len(configurations)])
            elif j % 2 == 0:
                nmat, p = _sphere_patch(rng, m)
                surface_subtypes["sphere"] += 1
            else:
                nmat, p = _paraboloid_patch(rng, m)
                surface_subtypes["paraboloid"] += 1

            if float(np.max(np.linalg.norm(p, axis=1))) > rc:
                raise AssertionError("true Hermite point left the unit-cell ball")
            budget_n = math.exp(
                rng.uniform(math.log(1e-4), math.log(3e-2)))
            budget_p = math.exp(
                rng.uniform(math.log(1e-5), math.log(3e-2)))
            lam = math.exp(rng.uniform(math.log(2e-3), math.log(2e-1)))
            row = _evaluate_qef_contract(
                nmat, p, budget_n, budget_p, lam, rng, rc)
            actuals.append(row["actual"])
            bounds.append(row["bound"])
            ratios.append(row["bound_to_actual"])
            residuals.append(row["unregularized_data_residual"])
            kind_violations += int(row["complete_violation"])
            kind_incomplete_violations += int(row["incomplete_violation"])

        actual_array = np.asarray(actuals)
        bound_array = np.asarray(bounds)
        ratio_array = np.asarray(ratios)
        residual_array = np.asarray(residuals)
        by_kind[kind] = {
            "sample_count": per_kind,
            "complete_violations": kind_violations,
            "incomplete_bridge_violations": kind_incomplete_violations,
            "absolute_actual_error": _quantiles(actual_array),
            "absolute_bound": _quantiles(bound_array),
            "bound_to_actual": _quantiles(ratio_array),
            "unregularized_data_residual": _quantiles(residual_array),
            "tolerance_coverage": {
                f"{tolerance:.2f}": {
                    "measured_actual": float(
                        np.mean(actual_array <= tolerance)),
                    "declared_contract": float(
                        np.mean(bound_array <= tolerance)),
                }
                for tolerance in tolerances
            },
        }
        all_actuals.extend(actuals)
        all_bounds.extend(bounds)
        all_ratios.extend(ratios)
        all_residuals.extend(residuals)
        complete_violations += kind_violations
        incomplete_violations += kind_incomplete_violations

    actual_array = np.asarray(all_actuals)
    bound_array = np.asarray(all_bounds)
    return {
        "description": (
            "Non-concurrent analytic planes and sphere/paraboloid Hermite "
            "patches for the regularized QEF theorem"),
        "sample_count": len(all_actuals),
        "complete_violations": complete_violations,
        "incomplete_bridge_violations": incomplete_violations,
        "all_successes_cp95_lower": _cp_lower_all_successes(
            len(all_actuals) - complete_violations),
        "surface_subtypes": surface_subtypes,
        "absolute_actual_error": _quantiles(actual_array),
        "absolute_bound": _quantiles(bound_array),
        "bound_to_actual": _quantiles(np.asarray(all_ratios)),
        "unregularized_data_residual": _quantiles(
            np.asarray(all_residuals)),
        "tolerance_coverage": {
            f"{tolerance:.2f}": {
                "measured_actual": float(np.mean(actual_array <= tolerance)),
                "declared_contract": float(np.mean(bound_array <= tolerance)),
            }
            for tolerance in tolerances
        },
        "by_kind": by_kind,
    }


def generate() -> dict:
    rng = np.random.default_rng(SEED)
    hard = experiment_hard_switch()
    smooth = experiment_smooth_min(rng)
    hermite = experiment_hermite_root(rng)
    qef = experiment_qef(rng)
    qef_residual_stress = experiment_qef_residual_stress(rng)
    return {
        "schema": "hybridcad.topic4.gradient-hermite-qef.v3",
        "seed": SEED,
        "claim_scope": (
            "Analytic finite-dimensional stress tests. Zero observed violations "
            "are implementation evidence, not mathematical proof."
        ),
        "experiments": {
            "hard_switch": hard,
            "smooth_min": smooth,
            "hermite_root": hermite,
            "qef": qef,
            "qef_residual_stress": qef_residual_stress,
        },
        "all_required_checks_pass": bool(
            hard["violations"] == 0
            and smooth["complete_violations"] == 0
            and smooth["naive_without_coupling_violations"] > 0
            and hermite["complete_violations"] == 0
            and qef["complete_violations"] == 0
            and qef["realized_budget_diagnostic_violations"] == 0
            and qef["matrix_oracle_diagnostic_violations"] == 0
            and qef["incomplete_bridge_violations"] > 0
            and qef_residual_stress["complete_violations"] == 0
            and qef_residual_stress["incomplete_bridge_violations"] > 0
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    record = generate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n",
                        encoding="utf-8")
    if not record["all_required_checks_pass"]:
        raise SystemExit("Topic-4 audit failed; inspect the JSON record")
    print(f"Wrote {args.out}")
    print("All executable checks passed. Finite sampling is not a proof.")


if __name__ == "__main__":
    main()
