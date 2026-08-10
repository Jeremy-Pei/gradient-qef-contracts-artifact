#!/usr/bin/env python3
"""Plot the frozen topic-4 JSON record without recomputing experiments."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


COLORS = {
    "blue": "#2A6FBB",
    "red": "#C43C2C",
    "green": "#4C8F3A",
    "gold": "#D99A2B",
    "gray": "#777777",
}


def _identity(ax, values):
    values = np.asarray(values)
    lo = max(float(np.min(values[values > 0])), 1e-16)
    hi = float(np.max(values))
    ax.plot([lo, hi], [lo, hi], "--", color="black", lw=1.1, label="identity")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    ex = data["experiments"]

    plt.rcParams.update({
        "font.size": 9.5,
        "axes.titlesize": 11,
        "axes.labelsize": 9.5,
        "legend.fontsize": 8,
        "figure.dpi": 150,
        "savefig.dpi": 220,
    })
    fig, axes = plt.subplots(2, 3, figsize=(13.4, 7.4), constrained_layout=True)

    # (a) Hard switch counterexample.
    ax = axes[0, 0]
    rows = ex["hard_switch"]["rows"]
    for angle, color in zip((30.0, 90.0, 150.0),
                            (COLORS["blue"], COLORS["green"], COLORS["red"])):
        group = [r for r in rows if r["angle_deg"] == angle]
        ax.plot([r["epsilon"] for r in group],
                [r["gradient_error"] for r in group], "o-", ms=3.5,
                color=color, label=fr"$\theta={angle:.0f}^\circ$")
    ax.set_xscale("log")
    ax.set_xlabel(r"value-error budget $\varepsilon$")
    ax.set_ylabel("output normal jump")
    ax.set_title("(a) Hard switch: error does not vanish", loc="left")
    ax.grid(True, which="both", alpha=0.22)
    ax.legend(frameon=False)

    # (b) Smooth-min certificate.
    ax = axes[0, 1]
    samples = ex["smooth_min"]["plot_samples"]
    actual = np.array([s["actual"] for s in samples])
    bound = np.array([s["bound"] for s in samples])
    ax.scatter(actual, bound, s=8, alpha=0.34, color=COLORS["blue"], edgecolors="none")
    _identity(ax, np.concatenate([actual, bound]))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("measured gradient error")
    ax.set_ylabel("complete upper bound")
    nv = ex["smooth_min"]["naive_without_coupling_violations"]
    n = ex["smooth_min"]["sample_count"]
    ax.text(0.03, 0.96, f"complete: 0/{n:,} violations\n"
            f"without coupling: {nv:,}/{n:,}", transform=ax.transAxes,
            va="top", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="#BBBBBB"))
    ax.set_title("(b) Smooth-min coupled bound", loc="left")
    ax.grid(True, which="both", alpha=0.18)
    ax.legend(frameon=False, loc="lower right")

    # (c) Hermite edge-root certificate.
    ax = axes[0, 2]
    samples = ex["hermite_root"]["plot_samples"]
    actual = np.array([s["actual"] for s in samples])
    bound = np.array([s["bound"] for s in samples])
    ax.scatter(actual, bound, s=8, alpha=0.34, color=COLORS["green"], edgecolors="none")
    _identity(ax, np.concatenate([actual, bound]))
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("measured root displacement")
    ax.set_ylabel("root-displacement bound")
    ax.set_title("(c) Hermite root transfer", loc="left")
    ax.grid(True, which="both", alpha=0.18)
    ax.legend(frameon=False, loc="lower right")

    # (d) Per-configuration useful coverage at tau=0.10.
    ax = axes[1, 0]
    order = ["orthogonal", "random", "edge20", "near_planar"]
    labels_config = ["orthogonal", "random", "20° edge", "near-planar"]
    x = np.arange(len(order))
    width = 0.25
    per_config = [ex["qef"]["by_configuration"][k]["tolerance_coverage"]["0.10"]
                  for k in order]
    declared = [100.0 * v["declared_contract"] for v in per_config]
    realized = [100.0 * v["realized_budget_diagnostic"] for v in per_config]
    matrix = [100.0 * v["matrix_oracle_diagnostic"] for v in per_config]
    ax.bar(x - width, declared, width, color=COLORS["blue"], label="declared")
    ax.bar(x, realized, width, color=COLORS["gold"], label="realized-budget diag.")
    ax.bar(x + width, matrix, width, color=COLORS["green"], label="matrix oracle diag.")
    ax.set_xticks(x, labels_config,
                  rotation=15, ha="right")
    ax.set_ylim(0, 108)
    ax.set_ylabel(r"coverage at $\tau=0.10$ (%)")
    ax.set_title("(d) Configuration-dependent usefulness", loc="left")
    ax.grid(True, axis="y", alpha=0.2)
    ax.legend(frameon=False, fontsize=7.2, loc="upper right")

    # (e) Aggregate useful coverage for the deployable and diagnostic arms.
    ax = axes[1, 1]
    tol = ex["qef"]["tolerance_coverage"]
    labels = list(tol.keys())
    x = np.arange(len(labels))
    declared = [100.0 * tol[t]["coverage_of_all_queries"] for t in labels]
    realized = [100.0 * tol[t]["realized_budget_diagnostic_coverage"]
                for t in labels]
    matrix = [100.0 * tol[t]["matrix_oracle_diagnostic_coverage"]
              for t in labels]
    ax.bar(x - width, declared, width, color=COLORS["blue"], label="declared")
    ax.bar(x, realized, width, color=COLORS["gold"], label="realized-budget diag.")
    ax.bar(x + width, matrix, width, color=COLORS["green"], label="matrix oracle diag.")
    ax.set_xticks(x, labels)
    ax.set_xlabel("absolute vertex-error tolerance (cell side = 1)")
    ax.set_ylabel("coverage (%)")
    ax.set_ylim(0, 100)
    ax.set_title("(e) Source of certificate slack", loc="left")
    ax.grid(True, axis="y", alpha=0.2)
    ax.legend(frameon=False, fontsize=7.2, loc="upper left")

    # (f) Complete chain versus two tempting ablations.
    ax = axes[1, 2]
    counts = [
        ex["smooth_min"]["complete_violations"],
        ex["smooth_min"]["naive_without_coupling_violations"],
        ex["qef"]["complete_violations"],
        ex["qef"]["incomplete_bridge_violations"],
    ]
    labels = ["smooth\ncomplete", "smooth\nno coupling",
              "QEF\ncomplete", "QEF\nno point budget"]
    colors = [COLORS["green"], COLORS["red"], COLORS["green"], COLORS["red"]]
    bars = ax.bar(range(4), counts, color=colors)
    ax.set_xticks(range(4), labels)
    ax.set_yscale("symlog", linthresh=1)
    ax.set_ylim(0, max(counts) * 2.2)
    ax.set_ylabel("observed violations (symlog)")
    ax.set_title("(f) Proof-chain ablations", loc="left")
    for bar, value in zip(bars, counts):
        ax.text(bar.get_x() + bar.get_width() / 2, max(value, 0.6) * 1.12,
                f"{value:,}", ha="center", va="bottom", fontsize=8.5)
    ax.grid(True, axis="y", alpha=0.2)

    fig.suptitle("Executable audit of gradient–Hermite–QEF contracts",
                 fontsize=14, fontweight="semibold")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, bbox_inches="tight")
    fig.savefig(args.output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig)

    # Separate M5 audit: figures read only frozen JSON values.
    stress = ex["qef_residual_stress"]
    groups = [
        ("compatible\ncommon point", ex["qef"]),
        ("inconsistent\nplanes", stress["by_kind"]["inconsistent_planes"]),
        ("curved\npatches", stress["by_kind"]["curved_patch"]),
    ]
    fig2, axes2 = plt.subplots(1, 3, figsize=(11.8, 3.35),
                               constrained_layout=True)
    x = np.arange(len(groups))

    ax = axes2[0]
    residual = [g[1]["unregularized_data_residual"]["q50"] for g in groups]
    ax.bar(x, residual, color=[COLORS["gray"], COLORS["gold"], COLORS["green"]])
    ax.set_yscale("log")
    ax.set_xticks(x, [g[0] for g in groups])
    ax.set_ylabel("median minimum data residual")
    ax.set_title("(a) Compatibility of true planes", loc="left")
    ax.grid(True, axis="y", alpha=0.2)

    ax = axes2[1]
    compatible_tol = ex["qef"]["tolerance_coverage"]["0.10"]
    declared = [
        100.0 * compatible_tol["coverage_of_all_queries"],
        100.0 * stress["by_kind"]["inconsistent_planes"]
        ["tolerance_coverage"]["0.10"]["declared_contract"],
        100.0 * stress["by_kind"]["curved_patch"]
        ["tolerance_coverage"]["0.10"]["declared_contract"],
    ]
    measured = [
        100.0 * compatible_tol["measured_actual_coverage"],
        100.0 * stress["by_kind"]["inconsistent_planes"]
        ["tolerance_coverage"]["0.10"]["measured_actual"],
        100.0 * stress["by_kind"]["curved_patch"]
        ["tolerance_coverage"]["0.10"]["measured_actual"],
    ]
    width2 = 0.34
    ax.bar(x - width2 / 2, declared, width2, color=COLORS["blue"],
           label="declared certificate")
    ax.bar(x + width2 / 2, measured, width2, color=COLORS["green"],
           label="measured displacement")
    ax.set_xticks(x, [g[0] for g in groups])
    ax.set_ylim(0, 108)
    ax.set_ylabel(r"coverage at $\tau=0.10$ (%)")
    ax.set_title("(b) Soundness versus usefulness", loc="left")
    ax.grid(True, axis="y", alpha=0.2)
    ax.legend(frameon=False, fontsize=7.2, loc="upper center",
              bbox_to_anchor=(0.5, -0.20), ncol=2)

    ax = axes2[2]
    actual = [g[1]["absolute_actual_error"]["q50"] for g in groups]
    bound = [g[1]["absolute_bound"]["q50"] for g in groups]
    ax.bar(x - width2 / 2, actual, width2, color=COLORS["green"],
           label="measured")
    ax.bar(x + width2 / 2, bound, width2, color=COLORS["blue"],
           label="declared bound")
    ax.set_yscale("log")
    ax.set_xticks(x, [g[0] for g in groups])
    ax.set_ylabel("median QEF displacement")
    ax.set_title("(c) Bound conservatism", loc="left")
    ax.grid(True, axis="y", alpha=0.2)
    ax.legend(frameon=False, fontsize=7.2, loc="upper left")

    residual_output = args.output.with_name("fig_topic4_residual_stress.png")
    fig2.savefig(residual_output, bbox_inches="tight")
    fig2.savefig(residual_output.with_suffix(".pdf"), bbox_inches="tight")
    plt.close(fig2)
    print(f"Wrote {args.output} and {args.output.with_suffix('.pdf')}")
    print(f"Wrote {residual_output} and {residual_output.with_suffix('.pdf')}")


if __name__ == "__main__":
    main()
