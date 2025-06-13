#!/usr/bin/env python3
"""
bitmask_coverage.py
===================
Check that exactly the four expected detector slots
(6..9 -> masks 0x40,0x80,0x100,0x200) occur with uniform
probability. Works on mini-HDF5 produced by build_clicks_hdf5.py.

Outputs
-------
* <stem>_mask_stats.csv  - side,mask_hex,count,fraction
* <stem>_mask_hist.png   - bar-plot per side
The script prints a warning if
  (i) an unexpected mask appears, or
  (ii) any expected mask has fraction < --threshold (default 1e-6).
"""

from pathlib import Path
import argparse, h5py, numpy as np, pandas as pd, matplotlib.pyplot as plt

EXPECT_SIDE = {
    "Alice": {0x0040, 0x0080},      # A-side uses only bits 6,7
    "Bob"  : {0x0100, 0x0200},      # B-side - bits 8,9
}
# bitwise OR for fast test "is there a foreign bit"
ALLOWED_MASK = {
    side: int(np.bitwise_or.reduce(list(masks)))
    for side, masks in EXPECT_SIDE.items()
}
# fixed set of columns for the plot
CATS = ["0x40", "0x80", "0x100", "0x200", "BAD"]

def load_clicks(h5: Path):
    with h5py.File(h5, "r") as f:
        return {
            "Alice": f["alice/clicks"][:].astype(np.uint16),
            "Bob"  : f["bob/clicks"][:].astype(np.uint16)
        }

def analyse(side: str, arr: np.ndarray, thr: float) -> pd.DataFrame:
    """Return DataFrame with frequency table for one side
       and print warnings if something looks suspicious."""
    allowed = np.uint16(ALLOWED_MASK[side]) # allowed bits for this side
    ok_mask = (arr & ~allowed) == 0         # True => all set bits are allowed
    bad_frac = 1.0 - ok_mask.mean()

    # --- frequencies of "OK" masks (relative to the whole array) ---------
    vals, cnts = np.unique(arr[ok_mask], return_counts=True)
    fr_ok      = dict(zip(vals, cnts / arr.size))   # global normalization

    # -------- warnings ---------------------------------------------------
    if bad_frac > thr:
        print(f"[warn] {side}: fraction of masks with OUT-of-range bits = {bad_frac:.2e}")

    expect = EXPECT_SIDE[side]
    for m in expect:
        if fr_ok.get(m, 0.0) < thr:
            print(f"[warn] {side}: rare expected mask {hex(m)} -> {fr_ok.get(m,0):.2e}")

    # -------- DataFrame (global scale) -----------------------------------
    df_ok = pd.DataFrame({
        "side"     : side,
        "mask_hex" : [hex(v) for v in vals],
        "count"    : cnts,
        "fraction" : [fr_ok[v] for v in vals],
    })
    bad_cnt  = arr.size - cnts.sum()
    df_bad   = pd.DataFrame({
        "side":     [side],
        "mask_hex": ["BAD"],
        "count":    [bad_cnt],
        "fraction": [bad_frac],          # = bad_cnt / arr.size
    })
    df = pd.concat([df_ok, df_bad], ignore_index=True)
    return df

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hdf5")
    ap.add_argument("--threshold", type=float, default=1e-6,
                    help="relative fraction below which a mask is flagged")
    ap.add_argument("--outdir", default="./diagnostics")
    args = ap.parse_args()

    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    stem = Path(args.hdf5).stem.replace(".hdf5","")

    dfs = []
    for side, arr in load_clicks(Path(args.hdf5)).items():
        dfs.append(analyse(side, arr, args.threshold))
    df_all = pd.concat(dfs, ignore_index=True)

    # save CSV
    csv = out/f"{stem}_mask_stats.csv"
    df_all.to_csv(csv, index=False); print("[saved]", csv)

    # bar-plot per side
    plt.figure(figsize=(6,3.3))
    CATS = ["0x40","0x80","0x100","0x200","BAD"]   # fixed order
    x = np.arange(len(CATS))
    width = 0.35
    for i,(side, sub) in enumerate(df_all.groupby("side")):
        frac = sub.set_index("mask_hex").reindex(CATS)["fraction"].fillna(0.0)
        plt.bar(x + i*width, frac, width=width, label=side)
    plt.xticks(x + width/2, CATS)
    plt.ylabel("fraction"); plt.title("Mask coverage")
    plt.legend(); plt.tight_layout()
    png = csv.with_suffix(".png")
    plt.savefig(png, dpi=300); plt.close(); print("[saved]", png)

if __name__ == "__main__":
    main()
