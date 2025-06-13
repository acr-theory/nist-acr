#!/usr/bin/env python3
"""
cumulative_ch_plot.py
---------------------
Compute the cumulative CH-norm (and its 1-sigma error) after k, 2k, 3k, ...
events for a single *mini.hdf5* file (as produced by build_clicks_hdf5.py)
and draw a stability plot.

Usage
-----
python cumulative_ch_plot.py run02_54_scan_0.050_mini.hdf5 \
        --step 100 --outdir ./diagnostics
"""

from __future__ import annotations
import argparse
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def load_clicks_settings(path: Path):
    """Return (a_clicks, a_set, b_clicks, b_set) - numpy arrays."""
    with h5py.File(path, "r") as f:
        a_clicks = f["alice/clicks"][:]
        a_set    = f["alice/settings"][:]
        b_clicks = f["bob/clicks"][:]
        b_set    = f["bob/settings"][:]
    return a_clicks, a_set, b_clicks, b_set


def cumulative_ch(a_clicks, a_set, b_clicks, b_set, step: int):
    """
    Return DataFrame with columns:
        n_trials, CH_norm, sigma
    evaluated every <step> trials.
    """
    # "has click" indicators are more convenient as bool masks
    a_hit = a_clicks != 0
    b_hit = b_clicks != 0

    # coincidences by basis
    coinc00 = (a_set == 1) & (b_set == 1) & a_hit & b_hit
    coinc01 = (a_set == 1) & (b_set == 2) & a_hit & b_hit
    coinc10 = (a_set == 2) & (b_set == 1) & a_hit & b_hit
    coinc11 = (a_set == 2) & (b_set == 2) & a_hit & b_hit

    # singles
    S_A0 = (a_set == 1) & a_hit
    S_A1 = (a_set == 2) & a_hit
    S_B0 = (b_set == 1) & b_hit
    S_B1 = (b_set == 2) & b_hit

    # cumulative sums
    c00 = np.cumsum(coinc00)
    c01 = np.cumsum(coinc01)
    c10 = np.cumsum(coinc10)
    c11 = np.cumsum(coinc11)

    sA0 = np.cumsum(S_A0)
    sA1 = np.cumsum(S_A1)
    sB0 = np.cumsum(S_B0)
    sB1 = np.cumsum(S_B1)

    n_total = a_clicks.size
    idx = np.arange(step, n_total + 1, step)

    CH  = []
    SIG = []
    for i in idx - 1:                               # i is last index included
        num = (c00[i] + c01[i] + c10[i] - c11[i])
        denom = 0.5 * (sA0[i] + sA1[i] + sB0[i] + sB1[i])
        sch = num / denom if denom else 0.0
        CH.append(sch)

        # Poissonian 1-sigma (as in acr_ch_test.py)
        var = (c00[i] + c01[i] + c10[i] + c11[i] +
               0.25 * (sA0[i] + sA1[i] + sB0[i] + sB1[i])) / (denom**2)
        SIG.append(np.sqrt(var))

    return pd.DataFrame({
        "n_trials": idx,
        "CH_norm": CH,
        "sigma":   SIG,
    })


def main():
    ap = argparse.ArgumentParser(description="Cumulative CH stability plot")
    ap.add_argument("hdf5", help="mini.hdf5 file (from build_clicks_hdf5.py)")
    ap.add_argument("--step", type=int, default=100,
                    help="trial step for cumulative evaluation (default 100)")
    ap.add_argument("--outdir", default="./diagnostics",
                    help="where to save CSV and PNG")
    args = ap.parse_args()

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    a_clicks, a_set, b_clicks, b_set = load_clicks_settings(Path(args.hdf5))
    df = cumulative_ch(a_clicks, a_set, b_clicks, b_set, args.step)

    csv_path = outdir / (Path(args.hdf5).stem + "_cumulative.csv")
    df.to_csv(csv_path, index=False)
    print(f"[saved] {csv_path}")

    # --- plot ---
    plt.figure(figsize=(5.2, 3.6))
    plt.errorbar(df["n_trials"], df["CH_norm"],
                 yerr=df["sigma"], fmt="o-", capsize=3, linewidth=1)
    plt.axhline(0, color="grey", linestyle="--", linewidth=0.8)
    plt.xlabel("Cumulative # trials")
    plt.ylabel("CH-norm")
    plt.title(Path(args.hdf5).stem)
    plt.tight_layout()
    plt.fill_between(df['n_trials'],
                 -df['sigma'],
                  df['sigma'],
                 color='green', alpha=0.15, label=r'$\pm1\sigma$')
    plt.legend()

    png_path = outdir / (Path(args.hdf5).stem + "_cumulative.png")
    plt.savefig(png_path, dpi=300)
    plt.close()
    print(f"[saved] {png_path}")


if __name__ == "__main__":
    main()
