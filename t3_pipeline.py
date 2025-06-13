#!/usr/bin/env python3
"""
t3_pipeline.py
==============

One-shot wrapper that runs the entire ACR T3 pipeline for a single data set.

It performs two steps:

1.  Calls **build_t3_counts.py** to compute the seven T3 counters
    (and, optionally, shuffle / bootstrap / radius-scan).
2.  Passes the resulting JSON to **acr_t3_test.py** to print the human-readable
    report.  The combined console output of both steps is saved to a *.txt*
    file inside *--out-dir*.

Command-line flags
------------------
  --parquet <file>        input raw Parquet file (Alice + Bob clicks)
  --sync    <file>        matching *_sync.json that contains *delta_ticks*
  --name    <tag>         short label used in file names and report header
  --out-dir <folder>      where to place the output *.json / *.txt

Flags forwarded to *build_t3_counts.py*
  --radius       <float>              single phase-window radius (default 0.05)
  --scan-radius  r1,r2,...            comma-separated radii to scan
  --r-mode       any|alice|bob        definition of R_i (default any)

Flags forwarded to *acr_t3_test.py*
  --shuffle      <int>                permutation test iterations
  --bootstrap    <int>                bootstrap iterations
  --threads      <int>                worker processes for heavy jobs
  --shuffle-mode pair|side            permutation strategy (default pair)
  --seed         <int>                RNG seed

Output files
------------
  <out-dir>/<name>_t3_data.npz   all raw A/B arrays + basic counts
  <out-dir>/<name>_t3_report.txt full console log of both steps

The script writes only these two files and exits with a non-zero status
if either sub-process returns a failure code.
"""
import argparse, pathlib, subprocess, sys

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parquet", required=True)
    ap.add_argument("--sync", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out-dir", required=True)
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--radius", type=float, default=None, help="single phase-window radius (default 0.05)")
    group.add_argument("--scan-radius", help="comma-separated list of radii to scan")
    ap.add_argument("--r-mode", choices=["any","alice","bob"], default="any")
    ap.add_argument("--cluster", type=int, default=0, help="Block length for cluster-robust sigma (0 = off)")
    ap.add_argument("--azuma", action="store_true", help="Also report Azuma-Hoeffding tail bound p-value")
    ap.add_argument("--shuffle", type=int, default=0)
    ap.add_argument("--bootstrap", type=int, default=0)
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--shuffle-mode", choices=["pair","side"], default="pair")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed (optional)")
    args = ap.parse_args()

    out_dir = pathlib.Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    counts_npz  = out_dir / f"{args.name}_t3_data.npz"
    report_txt  = out_dir / f"{args.name}_t3_report.txt"

    # 1. build raw A/B arrays + base counts
    build_cmd = [
        "python", "/app/build_t3_counts.py",
        "--parquet", args.parquet,
        "--sync",    args.sync,
        "--r-mode",  args.r_mode,
        "--out",     str(counts_npz)
    ]
    if args.radius is not None:
        build_cmd += ["--radius", str(args.radius)]
    if args.scan_radius:
        build_cmd += ["--scan-radius", args.scan_radius]

    build_proc = subprocess.run(
        build_cmd, check=True, capture_output=True, text=True
    )

    # 2. run statistical test (analytical + optional shuffle / bootstrap)
    test_cmd = [
        "python", "/app/acr_t3_test.py",
        "--counts", str(counts_npz),
        "--name",   args.name
    ]
    if args.cluster > 0:
        test_cmd += ["--cluster", str(args.cluster)]
    if args.azuma:
        test_cmd += ["--azuma"]
    if args.shuffle:
        test_cmd += ["--shuffle", str(args.shuffle)]
    if args.bootstrap:
        test_cmd += ["--bootstrap", str(args.bootstrap)]
    if args.threads and args.threads > 0:
        test_cmd += ["--threads", str(args.threads)]
    if args.shuffle_mode:
        test_cmd += ["--shuffle-mode", args.shuffle_mode]
    if args.seed is not None:
        test_cmd += ["--seed", str(args.seed)]

    test_proc = subprocess.run(
        test_cmd, check=True, capture_output=True, text=True
    )

    full_log = (
        build_proc.stdout + build_proc.stderr +
        test_proc.stdout  + test_proc.stderr
    )
    report_txt.write_text(full_log)
    print(full_log)

if __name__ == "__main__":
    sys.exit(main())
