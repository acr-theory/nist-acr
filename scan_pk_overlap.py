#!/usr/bin/env python3
"""
scan_pk_overlap.py
------------------
Scan phase-slot parameter pk vs. basis-overlap and plot results.

Usage
-----
python scan_pk_overlap.py --sync ./out/scan_sync.json --range 30 150 10 --outdir ./figs
"""

import json, argparse
from pathlib import Path
import pandas as pd, matplotlib.pyplot as plt

# ------------------------------------------------------------------------- #
def load_sync(sync_path: Path) -> tuple[int, int]:
    """
    Return (pk, delta_ticks) from a sync_table.json produced by
    build_sync_table.py.
    """
    js = json.loads(sync_path.read_text())
    return int(js["pk"]), int(js["delta_ticks"])

def compute_overlap(pk: int, radius: float) -> float:
    """
    Analytical estimate of the fraction of trials in which *any two* of
    the four bases (A0,A1,B0,B1) fall into the same pk-slot.

    Each basis lives in a time window of full width 2 r delta.
    C-approximation: overlap length per period  = 4*(2 r)  (four windows).
    Fraction  =  overlap / total period  = 8 r / pk.
    """
    ov = 8.0 * radius / pk
    return min(ov, 1.0) # cannot exceed 1

def main():
    ap = argparse.ArgumentParser(description='Scan pk vs. basis-overlap.')
    ap.add_argument('--sync',   required=True,
                    help='sync_table.json from build_sync_table.py')
    ap.add_argument('--range',  nargs=3, type=int, metavar=('MIN','MAX','STEP'),
                    default=[30,150,10],
                    help='pk range: min, max (inclusive), step')
    ap.add_argument('--radius', type=float, default=0.05,
                    help='phase-window radius used in build_clicks_hdf5.py '
                         '(default 0.05 = +/-5 %)')
    ap.add_argument('--outdir', default='./figs',
                    help='directory for CSV + PNG')
    args = ap.parse_args()

    sync_path = Path(args.sync)
    outdir    = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    # Load pk (delta not needed in the analytic formula)
    pk0, _ = load_sync(sync_path)

    pk_values = range(args.range[0], args.range[1] + 1, args.range[2])

    results = []
    for pk in pk_values:
        overlap = compute_overlap(pk, args.radius)
        results.append(dict(pk=pk, overlap=overlap))

    # Save to CSV
    df = pd.DataFrame(results)
    csv_path = outdir / 'pk_vs_overlap.csv'
    df.to_csv(csv_path, index=False)
    print(f'[saved] {csv_path}')

    # Draw the plot
    plt.figure(figsize=(5,4))
    plt.plot(df['pk'], df['overlap'], marker='o', linestyle='-')
    plt.xlabel('pk (number of phase slots)')
    plt.ylabel('Basis-overlap fraction')
    plt.title('pk vs. basis overlap')
    plt.grid(True)
    plt.tight_layout()

    png_path = outdir / 'pk_vs_overlap.png'
    plt.savefig(png_path, dpi=300)
    plt.close()
    print(f'[saved] {png_path}')

if __name__ == '__main__':
    main()
