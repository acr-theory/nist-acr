#!/usr/bin/env python3
"""
phase_peak_scan.py
==================
Track the drift of the phase-histogram peak throughout a run.

Algorithm
---------
1) Read mini-HDF5 produced by *build_clicks_hdf5.py* (datasets
   'phase_ticks' and 'period_ticks' already stored there).
2) Split data into non-overlapping blocks of `--block` trials
   (default 1000).
3) For each block build a histogram of phase residuals (mod period)
   and record the bin with the global maximum.
4) Save the drift curve to CSV and render a PNG plot.

Outputs
-------
* <stem>_peak_drift.csv : columns  trial_idx, peak_phase_ticks
* <stem>_peak_drift.png : drift plot

Example
-------
python phase_peak_scan.py run02_54_mini.hdf5 --block 1000 --outdir diagnostics
"""

from pathlib import Path
import argparse, h5py, numpy as np, pandas as pd
import matplotlib.pyplot as plt

def load_phases(h5: Path):
    with h5py.File(h5, "r") as f:
        phase  = f["phase_ticks"][:]          # int64
        period = int(f["period_ticks"][()])   # scalar
    return phase, period

def peak_drift(phase: np.ndarray, period: int, block: int):
    n_blocks = phase.size // block
    peaks, idx = [], []
    for k in range(n_blocks):
        p = phase[k*block : (k+1)*block]
        hist, edges = np.histogram(p % period, bins=256)
        peak_bin = edges[np.argmax(hist)]
        peaks.append(int(peak_bin))
        idx.append((k+1)*block)
    return pd.DataFrame({"trial_idx": idx, "peak_phase_ticks": peaks})

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hdf5")
    ap.add_argument("--block", type=int, default=1000,
                    help="trials per block (default 1000)")
    ap.add_argument("--outdir", default="./diagnostics")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    phase, period = load_phases(Path(args.hdf5))
    df = peak_drift(phase, period, args.block)

    csv = outdir / (Path(args.hdf5).stem + "_peak_drift.csv")
    df.to_csv(csv, index=False);  print("[saved]", csv)

    # plot
    plt.figure(figsize=(5.2,3.5))
    plt.plot(df["trial_idx"], df["peak_phase_ticks"], "o-")
    plt.axhline(0, ls="--", c="grey", lw=0.8)
    plt.xlabel("trial index"), plt.ylabel("peak phase [ticks]")
    plt.title("Drift of peak phase")
    plt.tight_layout()
    png = csv.with_suffix(".png")
    plt.savefig(png, dpi=300); plt.close();  print("[saved]", png)

if __name__ == "__main__":
    main()
