#!/usr/bin/env python3
"""
pk_overlap_mc.py
================
Monte-Carlo estimate of the probability that at least two of the four
measurement windows (A0,A1,B0,B1) overlap, given:

    * pk      - number of phase-slots per GPS period (affects only the
                *discrete* mode, see below);
    * radius  - half-width of the phase window in *fraction of period*
                (e.g. radius = 0.05  =>  full width = 10 % of the period).

Two simulation modes are available:

  --mode continuous   (default)  - centres are sampled uniform in [0,1).
                                   Conservative: ignores the fact that real
                                   centres sit near the middle of pk-slots.

  --mode discrete                - first choose an integer slot j in {0..pk-1},
                                   then add a uniform intra-slot offset.
                                   Reproduces the pk-quantisation more
                                   faithfully, but requires pk >= 4.

Outputs
-------
* <stem>_pk_overlap_mc.csv   - columns  pk, overlap
* <stem>_pk_overlap_mc.png   - the plot

Example
-------
python pk_overlap_mc.py --sync run02_54_sync.json \
                        --range 60 120 5 \
                        --radius 0.05 \
                        --mode discrete \
                        --shots 200000 \
                        --outdir ./diagnostics
"""

from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ------------------------------------------------------------------------- #
def load_pk(sync_json: Path) -> int:
    """Read 'pk' from a sync_table.json produced by build_sync_table.py."""
    try:
        return int(json.loads(sync_json.read_text())["pk"])
    except (KeyError, ValueError):
        print(f"[error] 'pk' key not found in {sync_json}", file=sys.stderr)
        sys.exit(1)
# ------------------------------------------------------------------------- #
def any_overlap(centres: np.ndarray, r: float) -> bool:
    """Return True if *any* pair of 4 centres (0-1) is closer than 2r modulo 1."""
    # sort for faster pair-wise check
    c = np.sort(centres)
    # distance to next neighbour (cyclic)
    d = np.minimum(np.diff(c, append=c[0]+1), 1.0)
    return np.any(d < 2.0*r)

# ------------------------------------------------------------------------- #
def mc_overlap(pk: int, r: float, shots: int, mode: str) -> float:
    """
    Vectorised Monte-Carlo estimate P(overlap).

    Parameters
    ----------
    pk     : int   - number of phase slots
    r      : float - radius (fraction of period)
    shots  : int   - number of random 4-tuples
    mode   : "continuous" | "discrete"
    """
    rng = np.random.default_rng()

    if mode == "continuous":
        # (shots,4) uniform points in [0,1)
        centres = rng.random(size=(shots, 4))
    else:
        # discrete slot 0..pk-1  +  intra-slot offset
        slots   = rng.integers(0, pk, size=(shots, 4))
        centres = (slots + rng.random(size=(shots, 4))) / pk

    # sort each row once, then compute cyclic nearest-neighbour gaps
    centres.sort(axis=1)
    gaps      = np.diff(centres, axis=1)                       # 3 gaps
    last_gap  = 1.0 - centres[:, -1] + centres[:, 0]           # cyclic gap
    gaps_all  = np.hstack([gaps, last_gap[:, None]])           # shape (shots,4)

    # overlap if ANY gap < 2r
    hits = (gaps_all < 2.0 * r).any(axis=1).mean()
    return float(hits)

# ------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync", required=True,
                    help="sync_table.json (to obtain default pk)")
    ap.add_argument("--range", nargs=3, type=int, metavar=("MIN","MAX","STEP"),
                    default=[60,120,5],
                    help="pk range: min max step  (inclusive)")
    ap.add_argument("--radius", type=float, default=0.05,
                    help="phase-window radius  (fraction of period, default 0.05)")
    ap.add_argument("--shots",  type=int, default=100_000,
                    help="Monte-Carlo shots per pk  (default 1e5)")
    ap.add_argument("--mode", choices=["continuous","discrete"], default="continuous",
                    help="sampling mode (see docstring)")
    ap.add_argument("--outdir", default="./figs", help="where to save CSV + PNG")
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)

    pk_default = load_pk(Path(args.sync))
    print(f"[info] default pk in JSON = {pk_default}")

    pks = range(args.range[0], args.range[1]+1, args.range[2])
    rows = []
    for pk in pks:
        if args.mode == "discrete" and pk < 4:
            rows.append((pk, math.nan)); continue
        p = mc_overlap(pk, args.radius, args.shots, args.mode)
        rows.append((pk, p))
        print(f"  pk={pk:3d}   overlap={p:.4%}")

    # --- save CSV ---------------------------------------------------------
    df = pd.DataFrame(rows, columns=["pk","overlap"])
    stem   = Path(args.sync).stem + f"_pk_overlap_mc"
    csv_fn = outdir / f"{stem}.csv"
    df.to_csv(csv_fn, index=False);     print("[saved]", csv_fn)

    # --- plot -------------------------------------------------------------
    plt.figure(figsize=(5,4))
    plt.plot(df["pk"], df["overlap"], "o-")
    plt.xlabel("pk  (phase slots)")
    plt.ylabel("overlap probability")
    plt.title(f"Monte-Carlo overlap  (r={args.radius}, mode={args.mode})")
    plt.grid(True); plt.tight_layout()
    png_fn = outdir / f"{stem}.png"
    plt.savefig(png_fn, dpi=300); plt.close(); print("[saved]", png_fn)

if __name__ == "__main__":
    main()
