#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: NIST-PD
# Derived from NIST public-domain script `calc_ch_from_hdf5.py`
# (Bell-test analysis code, 2015). Ported & extended by Azat Ahmedov, 2025:
# identical CH logic, plus block I/O, shuffle and bootstrap diagnostics.
# See NOTICE_NIST.txt for the full NIST-PD notice.
"""
acr_ch_test.py - Exact reproduction of the NIST-2015 CH / Eberhard test
with optional shuffle & bootstrap, using a two-step approach
=========================================================================

By default, this script runs exactly the original NIST logic from
calc_ch_from_hdf5.py, available in bell_analysis_code.zip at
https://www.nist.gov/pml/applied-physics-division/bell-test-research-software-and-data/repository-bell-test-research-0
It prints the same CH-norm, sigma, and LR p-value
(identical on the official NIST HDF5 files).

Additionally, you can specify:
  --shuffle  N       # N permutation iterations
  --bootstrap M      # M bootstrap iterations
  --threads  T       # number of worker processes (default 16)

to obtain extra statistics:
  - shuffle-based p-value (p_shuffle)
  - bootstrap confidence intervals for CH.
"""

import argparse, hashlib, sys, math, os
from pathlib import Path
import multiprocessing as mp

import h5py
import numpy as np

# ---------------------------------------------------------------------------
def sha256_hex(path: Path, buf: int = 1 << 20) -> str:
    """Compute SHA-256 of the given file."""
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(buf)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

# ---------------------------------------------------------------------------
def extract_patterns(files: list[Path], block: int=4_000_000):
    """
    Single pass: read each HDF5 and extract:
      pattA, pattB (4-bit)  [0..15]
      setA, setB   (0..2)
    Then concatenate across all files in order.
    """
    mask = 0x3C0
    arrA_patt, arrB_patt = [], []
    arrA_set,  arrB_set  = [], []

    for f in files:
        with h5py.File(f, "r") as hf:
            clkA = hf["/alice/clicks"]
            clkB = hf["/bob/clicks"]
            setA = hf["/alice/settings"]
            setB = hf["/bob/settings"]

            N = len(clkA)
            start = 0
            while start < N:
                stop  = min(start + block, N)
                a_clk = clkA[start:stop]
                b_clk = clkB[start:stop]
                a_set = setA[start:stop]
                b_set = setB[start:stop]

                # extract 4-bit patterns
                a_patt = ((a_clk & mask) >> 6).astype(np.uint8)
                b_patt = ((b_clk & mask) >> 6).astype(np.uint8)

                arrA_patt.append(a_patt)
                arrB_patt.append(b_patt)
                arrA_set.append(a_set.astype(np.uint8))
                arrB_set.append(b_set.astype(np.uint8))

                start = stop

    pattA = np.concatenate(arrA_patt)
    pattB = np.concatenate(arrB_patt)
    setA_  = np.concatenate(arrA_set)
    setB_  = np.concatenate(arrB_set)

    return pattA, pattB, setA_, setB_

# ---------------------------------------------------------------------------
def compute_ch_nist(
    pattA: np.ndarray, pattB: np.ndarray,
    setA:  np.ndarray, setB:  np.ndarray
):
    """
    The official NIST single-run CH calculation, bit-for-bit identical.
    Returns (S_ch, sigma, p_val_lr, dA, zA, dB, zB).
    """
    counts = np.zeros((4,4), dtype=np.int64)

    for A_ in (1,2):
        for B_ in (1,2):
            row = (A_-1)*2 + (B_-1)
            sel = (setA==A_) & (setB==B_)
            if not np.any(sel):
                continue
            pa = pattA[sel]; pb = pattB[sel]
            Sa   = (pa>0).sum()
            Sb   = (pb>0).sum()
            coinc= ((pa>0)&(pa==pb)).sum()
            Ntr  = sel.sum()
            counts[row,0] += Sa
            counts[row,1] += coinc
            counts[row,2] += Sb
            counts[row,3] += Ntr

    Sa0 ,C00 ,Sb0 ,_ = counts[0]   # (A1,B1)
    Sa0_,C01 ,Sb1 ,_ = counts[1]   # (A1,B2)
    Sa1 ,C10 ,Sb0_,_ = counts[2]   # (A2,B1)
    Sa1_,C11 ,Sb1_,_ = counts[3]   # (A2,B2)

    numer = C00 + C01 + C10 - C11
    denom = 0.5 * (Sa0 + Sa1 + Sb0 + Sb1)
    S_ch  = numer / denom
    sigma = 0.5 * math.sqrt(Sa0+Sa1+Sb0+Sb1) / denom

    from math import erfc, sqrt
    p_val = 0.5*erfc((S_ch/sigma)/sqrt(2))

    # no-signaling
    tb1 = counts[0,3] + counts[2,3]
    tb2 = counts[1,3] + counts[3,3]
    ta1 = counts[0,3] + counts[1,3]
    ta2 = counts[2,3] + counts[3,3]
    PAb1 = (Sa0+Sa1)/tb1 if tb1 else 0.0
    PAb2 = (Sa0_+Sa1_)/tb2 if tb2 else 0.0
    PBa1 = (Sb0+Sb1)/ta1 if ta1 else 0.0
    PBa2 = (Sb0_+Sb1_)/ta2 if ta2 else 0.0
    dA = PAb1 - PAb2
    dB = PBa1 - PBa2
    def var_p(p,n): return p*(1-p)/n if n>0 else 0.0
    zA = dA/math.sqrt(var_p(PAb1,tb1)+var_p(PAb2,tb2)) if (tb1 and tb2) else 0.0
    zB = dB/math.sqrt(var_p(PBa1,ta1)+var_p(PBa2,ta2)) if (ta1 and ta2) else 0.0

    return (S_ch, sigma, p_val, dA, zA, dB, zB)

# ---------------------------------------------------------------------------
def _shuffle_worker(args):
    """Worker for parallelized shuffle test."""
    n_iter, seed, setA, setB, Sa_bin, Sb_bin, Co_bin, obs_abs = args
    rng    = np.random.default_rng(seed)
    hits   = 0
    A_tmp  = setA.copy()
    for _ in range(n_iter):
        rng.shuffle(A_tmp)
        row = (A_tmp * 2 + setB) - 3
        Sa  = np.bincount(row, Sa_bin, minlength=4)
        Sb  = np.bincount(row, Sb_bin, minlength=4)
        Co  = np.bincount(row, Co_bin, minlength=4)
        numer= Co[0]+Co[1]+Co[2]-Co[3]
        denom= 0.5*(Sa[0]+Sa[2]+Sb[0]+Sb[1])
        S_p  = numer/denom if denom else 0.0
        if abs(S_p) >= obs_abs:
            hits += 1
    return hits

# ---------------------------------------------------------------------------
def _bootstrap_worker(args):
    """Worker for parallelized bootstrap."""
    n_iter, seed, idx_all, pattA, pattB, setA, setB = args
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n_iter):
        samp = rng.choice(idx_all, size=idx_all.size, replace=True)
        ch, *_ = compute_ch_nist(pattA[samp], pattB[samp], setA[samp], setB[samp])
        out.append(ch)
    return out

# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="NIST CH/Eberhard exact test + optional shuffle/bootstrap"
    )
    parser.add_argument("files",       nargs="+", type=Path, help="NIST build HDF5(s)")
    parser.add_argument("--block",     type=int, default=4_000_000, help="block size for reading large HDF5")
    parser.add_argument("--shuffle",   type=int, default=0, help="number of permutations for shuffle test")
    parser.add_argument("--bootstrap", type=int, default=0, help="number of bootstrap samples")
    parser.add_argument("--threads",   type=int, default=16, help="number of worker processes")
    parser.add_argument("--seed",      type=int, default=None, help="RNG seed for shuffle / bootstrap (default: None)")
    args = parser.parse_args()

    if args.shuffle < 0 or args.bootstrap < 0:
        sys.exit("Error: --shuffle/--bootstrap must be ≥ 0")

    # 1) SHA-256
    print("[1/3] SHA-256")
    for f in args.files:
        print(f"  {f.name} {sha256_hex(f)}")

    # 2) HDF5 integrity + extract
    print("[2/3] HDF5 read/extract (4-bit patt + settings)")
    try:
        pattA, pattB, setA, setB = extract_patterns(args.files, block=args.block)
        print(f"  total length = {len(pattA):,}")
    except Exception as e:
        print(f"  ERROR: {e}")
        sys.exit(1)

    # 3) CH / Eberhard test
    print("[3/3] CH/Eberhard test  (NIST original logic)")
    S_ch, sigma, p_val_lr, dA, zA, dB, zB = compute_ch_nist(pattA, pattB, setA, setB)

    # how many processes will actually be used
    jobs = max(1, min(args.threads, os.cpu_count() or args.threads))

    # --- shuffle
    p_shuffle = None
    if args.shuffle > 0:
        print(f"  running shuffle={args.shuffle} permutations on {jobs} cores …")
        if args.seed is not None:
            print(f"  using seed {args.seed} for shuffle")
        # pre-aggregation
        Sa_bin = (pattA > 0).astype(np.int8)
        Sb_bin = (pattB > 0).astype(np.int8)
        Co_bin = ((pattA>0) & (pattA==pattB)).astype(np.int8)
        obs_abs = abs(S_ch)
        # split by procedures
        base, rem = divmod(args.shuffle, jobs)
        counts = [base + (i < rem) for i in range(jobs)]
        ss = np.random.SeedSequence(args.seed)
        seeds = ss.spawn(jobs)
        tasks = [
            (counts[i], seeds[i], setA, setB, Sa_bin, Sb_bin, Co_bin, obs_abs)
            for i in range(jobs)
        ]
        with mp.Pool(jobs) as pool:
            hits_list = pool.map(_shuffle_worker, tasks)
        hits_tot = sum(hits_list)
        p_shuffle = (hits_tot + 1) / (args.shuffle + 1)

    # --- bootstrap
    ci_lo, ci_hi = None, None
    if args.bootstrap > 0:
        print(f"  running bootstrap={args.bootstrap} samples on {jobs} cores …")
        if args.seed is not None:
            print(f"  using seed {args.seed} for bootstrap")
        idx_all = np.arange(pattA.size)
        base, rem = divmod(args.bootstrap, jobs)
        counts = [base + (i < rem) for i in range(jobs)]
        ss = np.random.SeedSequence(args.seed)
        seeds = ss.spawn(jobs)
        tasks = [
            (counts[i], seeds[i], idx_all, pattA, pattB, setA, setB)
            for i in range(jobs)
        ]
        with mp.Pool(jobs) as pool:
            parts = pool.map(_bootstrap_worker, tasks)
        all_ch = np.concatenate(parts)
        ci_lo, ci_hi = np.percentile(all_ch, [2.5, 97.5])

    # --- final output
    print("\nSUMMARY\n--------")
    print(f"CH-norm (NIST)      = {S_ch:.6f}  +/- {sigma:.6f}")
    print(f"p-value (LR bound)  = {p_val_lr:.3e}")
    if p_shuffle is not None:
        print(f"p-value (shuffle)   = {p_shuffle:.3e}")
    if ci_lo is not None:
        print(f"95% CI (bootstrap)  = [{ci_lo:.4f}, {ci_hi:.4f}]")
    print(f"dA = {dA:+.4e}   (z = {zA:+.2f})")
    print(f"dB = {dB:+.4e}   (z = {zB:+.2f})")
    print("--------\n")

if __name__ == "__main__":
    main()
