#!/usr/bin/env python3
"""
scan_ch_plot.py
---------------
Parse *_scan_report.txt files produced by the multi-radius CH runs and
plot CH-norm versus radius (with +/-1-sigma error bars) for each run.

Usage
-----
python scan_ch_plot.py --reports /out/scan --outdir /out/diagnostics/ch_scan
"""

import re
import sys
import argparse
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

# Patterns to extract the radius from a line that contains the '--radius'
# flag, and to extract CH-norm together with sigma from the SUMMARY block
RADIUS_RE = re.compile(r'--radius\s+([0-9.]+)', re.IGNORECASE)
CH_BLOCK_RE = re.compile(
    r'CH-norm.*?=\s*([-+0-9.eE]+)\s*\+/-\s*([0-9.]+)',
    re.IGNORECASE
)

def parse_report(path: Path) -> list[dict]:
    """
    Return a list of records {run, radius, CH_norm, sigma} parsed from
    a single *_scan_report.txt file.
    """
    lines = path.read_text().splitlines()
    run = path.stem.replace('_scan_report', '')
    last_radius = None
    records = []

    for line in lines:
        # Search for a line with the --radius
        m_r = RADIUS_RE.search(line)
        if m_r:
            last_radius = float(m_r.group(1))
            continue

        # Search for a line with CH-norm = ... +/- ...
        m_ch = CH_BLOCK_RE.search(line)
        if m_ch and last_radius is not None:
            ch_norm = float(m_ch.group(1))
            sigma   = float(m_ch.group(2))
            records.append({
                'run':     run,
                'radius':  last_radius,
                'CH_norm': ch_norm,
                'sigma':   sigma,
            })

    if not records:
        print(f'Warning: no CH-norm entries parsed in {path.name}', file=sys.stderr)
    return records

def build_dataframe(report_dir: Path) -> pd.DataFrame:
    """
    Collect all *_scan_report.txt files into a single DataFrame.
    """
    records = []
    files = sorted(report_dir.glob('*_scan_report.txt'))
    print(f'Found report files: {[f.name for f in files]}')
    for rpt in files:
        recs = parse_report(rpt)
        records.extend(recs)

    if not records:
        raise RuntimeError(f'No valid scan reports parsed in {report_dir}')
    return pd.DataFrame.from_records(records)

def plot_runs(df: pd.DataFrame, outdir: Path) -> None:
    """
    For each run draw CH-norm +/- sigma versus radius and save the figure
    both as PDF and PNG.
    """
    for run, sub in df.groupby('run'):
        sub = sub.sort_values('radius')

        plt.figure(figsize=(4.5, 3.5))
        plt.errorbar(
            sub['radius'],
            sub['CH_norm'],
            yerr=sub['sigma'],
            capsize=3,
            marker='o',
            linestyle='-',
            linewidth=1,
        )
        plt.axhline(0, color='grey', linestyle='--', linewidth=0.8)
        plt.xlabel('radius (m)')
        plt.ylabel('CH-norm')
        plt.title(f'CH-norm vs radius - {run}')
        plt.tight_layout()

        pdf_path = outdir / f'fig_ch_scan_{run}.pdf'
        png_path = outdir / f'fig_ch_scan_{run}.png'
        plt.savefig(pdf_path)
        plt.savefig(png_path, dpi=300)
        plt.close()
        print(f'[saved] {pdf_path}')
        print(f'[saved] {png_path}')

def main() -> None:
    ap = argparse.ArgumentParser(description='Plot CH-norm vs radius scan.')
    ap.add_argument('--reports', default='/out/scan', help='Directory containing *_scan_report.txt files')
    ap.add_argument('--outdir',  default='/out/diagnostics/ch_scan', help='Directory to save figures and CSV')
    args = ap.parse_args()

    report_dir = Path(args.reports)
    outdir     = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    df = build_dataframe(report_dir)

    csv_path = outdir / 'ch_scan.csv'
    df.to_csv(csv_path, index=False)
    print(f'[saved] {csv_path}')

    plot_runs(df, outdir)

if __name__ == '__main__':
    main()
