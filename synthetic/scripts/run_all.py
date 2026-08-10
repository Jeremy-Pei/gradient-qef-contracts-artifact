#!/usr/bin/env python3
"""Run generation, regression checks, and plotting in separate processes."""

from __future__ import annotations

import subprocess
import sys
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCAL_PYTHON = ROOT / ".venv" / "bin" / "python"
PYTHON = str(LOCAL_PYTHON) if LOCAL_PYTHON.exists() else sys.executable


def run(*args: str) -> None:
    env = os.environ.copy()
    mpl = ROOT / "tmp" / "mpl"
    cache = ROOT / "tmp" / "cache"
    mpl.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    env.setdefault("MPLBACKEND", "Agg")
    env["MPLCONFIGDIR"] = str(mpl)
    env["XDG_CACHE_HOME"] = str(cache)
    subprocess.run([PYTHON, *args], cwd=ROOT, check=True, env=env)


def main() -> None:
    run("scripts/generate_results.py", "--out", "results/topic4_results.json")
    run("tests/test_contracts.py")
    run("scripts/plot_results.py", "results/topic4_results.json",
        "figures/fig_topic4_contract_audit.png")
    latexmk = shutil.which("latexmk")
    if latexmk:
        subprocess.run(
            [latexmk, "-pdf", "-interaction=nonstopmode", "-halt-on-error",
             "gradient_qef_contracts_v5.tex"],
            cwd=ROOT / "paper", check=True,
        )
    else:
        print("latexmk not found; skipped PDF compilation")


if __name__ == "__main__":
    main()
