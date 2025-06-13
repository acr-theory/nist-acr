#!/usr/bin/env python3
"""
build_t3_counts.py
------------------
Compute the seven T3 counters (+sigma) for one raw *.parquet file
and package the results (including per-trial A/B arrays) into a compressed NPZ.

Command-line flags
------------------
  --parquet        <path>   input raw Parquet file
  --sync           <path>   matching *_sync.json that holds delta_ticks
  --out            <path>   output .npz file

  --radius         <float>  single phase-window radius (default 0.05)
  --scan-radius    r1,r2    comma-separated list of radii to scan

  --r-mode         any|alice|bob   definition of R_i (default: any)

NPZ output
----------
  - mode      : string, the r_mode used
  - radii     : 1D float array of radii
  - counts    : object array of length len(radii), each entry is a dict with keys
                {"N_trials","N_A","N_B","N_C","N_AB","N_AC","N_BC","N_ABC","sigma","radius"}
  - A         : object array of length len(radii), each entry is a 1D boolean array A_i for trials 1..N
  - B         : object array of length len(radii), each entry is a 1D boolean array B_i for trials 1..N

NOTE: We pair trial i with trial i+1, so the last trial is dropped (no R_{N}).
"""

import argparse, json, sys
import numpy as np
import pyarrow.parquet as pq
from pathlib import Path

def compute_counts(tbl, radius: float, delta: int, r_mode: str):
    """
    Return:
      - counts_dict: dict with keys
          "N_trials","N_A","N_B","N_C","N_AB","N_AC","N_BC","N_ABC","sigma"
      - A_bool: 1D numpy boolean array of length N_trials (Alice clicks)
      - B_bool: 1D numpy boolean array of length N_trials (Bob clicks)
    for one phase-window radius.
    """

    # 1) Phase filter
    sync_time = tbl.groupby("trial")["time"].transform("min")
    phase     = ((tbl["time"] - sync_time) / delta) % 1.0
    mask      = (phase <= radius) | (phase >= 1.0 - radius)
    sub       = tbl[mask].sort_values(["trial", "time"], kind="mergesort").copy()

    # 2) Aggregate clicks per trial (trial-level A_i, B_i)
    grp = sub.groupby("trial").agg(
        A=("a_click", "any"),
        B=("b_click", "any")
    ).reset_index(drop=True)

    # 3) Build R_i from trial i+1 ----
    if r_mode == "any":
        R_series = grp["A"].shift(-1, fill_value=False) | grp["B"].shift(-1, fill_value=False)
    elif r_mode == "alice":
        R_series = grp["A"].shift(-1, fill_value=False)
    else:  # "bob"
        R_series = grp["B"].shift(-1, fill_value=False)

    # 4) Drop the last trial (no i+1 pair)
    A_bool = grp["A"].values[:-1]
    B_bool = grp["B"].values[:-1]
    R_bool = R_series.values[:-1]
    N = len(A_bool)

    # 5) Build counts
    N_A   = int(A_bool.sum())
    N_B   = int(B_bool.sum())
    N_C   = int(R_bool.sum())
    N_AB  = int(np.sum(A_bool & B_bool & ~R_bool))
    N_AC  = int(np.sum(A_bool & ~B_bool & R_bool))
    N_BC  = int(np.sum(~A_bool & B_bool & R_bool))
    N_ABC = int(np.sum(A_bool & B_bool & R_bool))

    # 6) Covariance-based sigma
    X = np.stack([
        A_bool & B_bool & R_bool,
        A_bool & B_bool & ~R_bool,
        A_bool & ~B_bool & R_bool,
        ~A_bool & B_bool & R_bool,
        A_bool, B_bool, R_bool
    ], axis=1).astype(int)
    cov   = np.cov(X, rowvar=False, bias=True)
    coeff = np.array([1, -1, -1, -1, 1, 1, 1])
    sigma = float(np.sqrt(N * coeff @ cov @ coeff)) if N > 0 else 0.0

    counts_dict = {
        "N_trials": N,
        "N_A":      N_A,
        "N_B":      N_B,
        "N_C":      N_C,
        "N_AB":     N_AB,
        "N_AC":     N_AC,
        "N_BC":     N_BC,
        "N_ABC":    N_ABC,
        "sigma":    sigma,
        "radius":   radius
    }

    return counts_dict, A_bool, B_bool, R_bool


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True, help="Input raw Parquet file")
    ap.add_argument("--sync", required=True, help="Matching *_sync.json with delta_ticks")
    ap.add_argument("--out", required=True, help="Output .npz file")
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--radius", type=float, default=0.05, help="Phase-window radius (default 0.05)")
    group.add_argument("--scan-radius", help="Comma-separated list of radii, e.g. 0.02,0.03,0.05")
    ap.add_argument("--r-mode", choices=["any", "alice", "bob"], default="any", help="Definition of R_i (default any)")
    args = ap.parse_args()

    # 1) Load raw Parquet and sync
    tbl = pq.read_table(args.parquet).to_pandas()
    # Tag a_click/b_click columns
    tbl["a_click"] = (tbl["side"] == 0) & tbl["chan"].isin([0, 1])
    tbl["b_click"] = (tbl["side"] == 1) & tbl["chan"].isin([0, 1])
    delta = json.load(open(args.sync))["delta_ticks"]

    # 2) Decide radii array
    if args.scan_radius:
        radii = np.array([float(r) for r in args.scan_radius.split(",")], dtype=float)
    else:
        radii = np.array([args.radius], dtype=float)

    # Prepare lists to collect results
    counts_list = []
    A_list      = []
    B_list      = []
    R_list      = []

    # 3) Compute for each radius
    for r in radii:
        counts_dict, A_bool, B_bool, R_bool = compute_counts(tbl.copy(), r, delta, args.r_mode)
        counts_list.append(counts_dict)
        A_list.append(A_bool.astype(bool))
        B_list.append(B_bool.astype(bool))
        R_list.append(R_bool.astype(bool))

    # 4) Pack into object arrays so .npz can store them
    radii_out = radii  # already numpy array
    # Object array for counts (each item is a dict)
    counts_obj = np.empty(len(radii_out), dtype=object)
    for i, cd in enumerate(counts_list):
        counts_obj[i] = cd
    # Object arrays for A and B
    A_obj = np.empty(len(radii_out), dtype=object)
    B_obj = np.empty(len(radii_out), dtype=object)
    R_obj = np.empty(len(radii_out), dtype=object)
    for i in range(len(radii_out)):
        A_obj[i] = A_list[i]
        B_obj[i] = B_list[i]
        R_obj[i] = R_list[i]

    # 5) Save to compressed NPZ
    out_path = Path(args.out)
    np.savez_compressed(
        out_path,
        mode=args.r_mode,
        radii=radii_out,
        counts=counts_obj,
        A=A_obj,
        B=B_obj,
        R=R_obj
    )

    print(f"[build_t3_counts] written {out_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
