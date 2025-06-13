#!/usr/bin/env python3
"""
gps_jitter_check.py
===================

Diagnostics for the GPS-sync selection produced by *build_sync_table.py*.

The script performs two checks:

1) running-median drift of consecutive GPS periods Δ;
2) histogram of phase residuals for Alice / Bob with the +/-5-tick gate.

If the JSON contains the new keys "alice_sync_tag" and "bob_sync_tag"
(real FPGA-tick timestamps), they are used; otherwise the script falls back
to the legacy "alice_sync_idx" / "bob_sync_idx" (indices in the raw file).

Outputs
-------
* <stem>_delta_med.png  - running-median plot
* <stem>_delta_med.csv  - table idx, period_ticks, running_med
* <stem>_phase_hist.png - phase-residual histogram
* <stem>_phase_hist.csv - two-column CSV  phase_ticks, side   (0 = Alice, 1 = Bob)
"""

from pathlib import Path
import argparse, json
import numpy as np, matplotlib.pyplot as plt, pandas as pd
from scipy.ndimage import median_filter

# --------------------------------------------------------------------------- #
def load_sync(js: Path):
    """Return (tag_A, tag_B, delta_ticks).  Prefer *sync_tag*, fallback to *sync_idx*."""
    d = json.loads(js.read_text())

    # new format ------------------------------------------------------------
    if "alice_sync_tag" in d and "bob_sync_tag" in d:
        A = np.array(d["alice_sync_tag"], dtype=np.int64)
        B = np.array(d["bob_sync_tag"],   dtype=np.int64)
    else:                                  # legacy fallback
        print("[warn] *_sync_tag not in JSON - falling back to *_sync_idx")
        A = np.array(d["alice_sync_idx"], dtype=np.int64)
        B = np.array(d["bob_sync_idx"],   dtype=np.int64)

    delta = int(d["delta_ticks"])
    return A, B, delta
# --------------------------------------------------------------------------- #

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sync_json")
    ap.add_argument("--outdir", default="./diagnostics",
                    help="directory for PNG/CSV output")
    ap.add_argument("--window", type=int, default=201,
                    help="odd window size of the running-median filter (default 201)")
    args = ap.parse_args()

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)

    A, B, delta = load_sync(Path(args.sync_json))

    if args.window < 3 or args.window >= A.size:
        raise ValueError("--window must be >=3 and < number of pulses")

    # ---------- 1. running median of the inter-pulse period delta -------------
    period = np.diff(A)                            # delta_i in ticks
    med    = median_filter(period, size=args.window, mode="nearest")

    plt.figure(figsize=(5.5, 3))
    plt.plot(med, label="running median delta")
    plt.axhline(delta, ls="--", c="k", lw=0.8, label="overall delta median")
    plt.xlabel("index"); plt.ylabel("ticks")
    plt.title("Running median of delta  (Alice)")
    plt.legend(); plt.tight_layout()
    p1 = out / (Path(args.sync_json).stem + "_delta_med.png")
    plt.savefig(p1, dpi=300); plt.close()
    print("[saved]", p1)

    # save CSV -------------------------------------------------------------
    df_delta = pd.DataFrame({
        "idx"          : np.arange(period.size),
        "period_ticks" : period,
        "running_med"  : med
    })
    csv1 = p1.with_suffix(".csv")
    df_delta.to_csv(csv1, index=False)
    print("[saved]", csv1)

    # ---------- 2. phase-residual histogram -------------------------------
    plt.figure(figsize=(5.5, 3))
    for arr, label, color in [(A, "Alice", "tab:blue"),
                              (B, "Bob",   "tab:orange")]:
        phase = (arr - arr[0]) % delta
        phase[phase > delta / 2] -= delta          # center on 0 for plotting
        plt.hist(phase, bins=41, alpha=0.5, label=label, color=color)

    plt.axvline(+5, ls="--", c="k", lw=0.8)
    plt.axvline(-5, ls="--", c="k", lw=0.8)
    plt.xlabel("phase residual [ticks]")
    plt.title("GPS phase-residual histogram")
    plt.legend(); plt.tight_layout()
    p2 = out / (Path(args.sync_json).stem + "_phase_hist.png")
    plt.savefig(p2, dpi=300); plt.close()
    print("[saved]", p2)

    # save raw residuals to CSV -------------------------------------------
    phase_A = (A - A[0]) % delta
    phase_A[phase_A > delta/2] -= delta
    phase_B = (B - B[0]) % delta
    phase_B[phase_B > delta/2] -= delta

    phase_all = np.concatenate([
        np.column_stack([phase_A, np.zeros_like(phase_A)]),
        np.column_stack([phase_B, np.ones_like(phase_B)])
    ])
    csv2 = p2.with_suffix(".csv")
    np.savetxt(csv2, phase_all, fmt=["%d","%d"],
               header="phase_ticks,side", delimiter=",", comments='')
    print("[saved]", csv2)

if __name__ == "__main__":
    main()
