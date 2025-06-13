#!/usr/bin/env python3
"""
check_covariance.py
===================
Compute an 8 x 8 empirical covariance matrix for one mini-HDF5 file.

The script rebuilds the four singles counters

    A0  A1  B0  B1

and the four coincidence counters

    C00 C01 C10 C11

exactly as they are defined in the NIST CH analysis, but now on a
trial-by-trial basis.  Trials are grouped into non-overlapping blocks
(default 500). For every block the counters are summed, and the sample
covariance matrix of these block sums is calculated.

Outputs
-------
* <stem>_cov.csv - 8 x 8 covariance matrix
* <stem>_cov.png - color heat-map of the same matrix

Usage
-----
python check_covariance.py run{tag}_{radius}_mini.hdf5 \
       --block 500 --outdir ./diagnostics
"""
from pathlib import Path
import argparse, itertools, h5py, numpy as np, pandas as pd, seaborn as sns
import matplotlib.pyplot as plt

S_LABELS = ['A0','A1','B0','B1']
C_LABELS = ['C00','C01','C10','C11']

def load_counts(h5: Path):
    # extract clicks and settings from mini-HDF5
    with h5py.File(h5, 'r') as f:
        a_clicks   = f['alice/clicks'][:]
        a_settings = f['alice/settings'][:]
        b_clicks   = f['bob/clicks'][:]
        b_settings = f['bob/settings'][:]

    # bit mask for slots 6..9
    mask = 0x3C0
    patt_a = (a_clicks & mask) >> 6
    patt_b = (b_clicks & mask) >> 6

    # singles by basis
    sA0 = ((a_settings == 1) & (patt_a > 0)).astype(int)
    sA1 = ((a_settings == 2) & (patt_a > 0)).astype(int)
    sB0 = ((b_settings == 1) & (patt_b > 0)).astype(int)
    sB1 = ((b_settings == 2) & (patt_b > 0)).astype(int)

    # coincidences by basis
    c00 = ((a_settings == 1) & (b_settings == 1) & (patt_a > 0) & (patt_a == patt_b)).astype(int)
    c01 = ((a_settings == 1) & (b_settings == 2) & (patt_a > 0) & (patt_a == patt_b)).astype(int)
    c10 = ((a_settings == 2) & (b_settings == 1) & (patt_a > 0) & (patt_a == patt_b)).astype(int)
    c11 = ((a_settings == 2) & (b_settings == 2) & (patt_a > 0) & (patt_a == patt_b)).astype(int)

    # assemble the final matrix (N_trials, 8)
    return np.vstack([sA0, sA1, sB0, sB1, c00, c01, c10, c11]).T

def compute_cov(arr: np.ndarray, block: int = 500):
    # drop tail so that total trials is multiple of block
    nblocks = arr.shape[0] // block
    if nblocks == 0:
        raise ValueError(f"Not enough trials ({arr.shape[0]}) for one block of size {block}")
    trimmed = arr[: nblocks * block]
    blocks  = trimmed.reshape(nblocks, block, arr.shape[1])
    sums    = blocks.sum(axis=1)                     # shape (nblocks, 8)
    df     = pd.DataFrame(sums, columns=S_LABELS+C_LABELS)
    return df.cov()

def main():
    ap = argparse.ArgumentParser(description='Covariance diagnostics')
    ap.add_argument('hdf5')
    ap.add_argument('--block', type=int, default=500, help='trials per block')
    ap.add_argument('--outdir', default='./diagnostics')
    args = ap.parse_args()

    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    mat = compute_cov(load_counts(Path(args.hdf5)), args.block)
    csv = outdir / (Path(args.hdf5).stem + '_cov.csv')
    mat.to_csv(csv); print('[saved]', csv)

    # heat-map
    plt.figure(figsize=(6.5,5.5))
    sns.heatmap(
        mat,
        annot=True,
        fmt='.2e',
        cmap='coolwarm',
        square=True,
        annot_kws={'size': 7}
    )
    plt.title(f'Empirical covariance – {Path(args.hdf5).stem}', fontsize=10)
    plt.tight_layout()
    png = csv.with_suffix('.png')
    plt.savefig(png, dpi=300); plt.close(); print('[saved]', png)

if __name__ == '__main__': main()
