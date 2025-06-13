#!/usr/bin/env python3
"""
pipeline.py
===========

Run the complete CH analysis pipeline in one command.

Steps executed
--------------
1. build_sync_table.py   -> sync_table.json
2. raw_to_parquet.py     -> raw.parquet
3. build_clicks_hdf5.py  -> one or more mini.hdf5 files
4. validate_mini_hdf5.py -> structure check for every mini.hdf5
5. acr_ch_test.py      -> CH / Eberhard test (optionally with permutation shuffle and/or bootstrap resampling)

Key command-line options
------------------------
  --radius R                analyse a single phase window (default 0.05)
  --scan-radius r1,r2,..    analyse several radii in one run; a separate mini.hdf5 and CH test is produced for each value
  --shuffle N               forward to acr_ch_test.py for an N-fold permutation test
  --bootstrap M             forward to acr_ch_test.py for an M-fold bootstrap confidence interval

Outputs
-------
  {name}_sync.json            (GPS synchronisation table)
  {name}_raw.parquet          (compressed raw events)
  {name}_{radius}.hdf5        (one per radius)
  {name}_report.txt           full console log of every step

All paths are written inside --out-dir (created if absent).
"""

import subprocess
import argparse
import sys
from pathlib import Path
from typing import List

def run(cmd: List[str], log_lines: List[str]) -> None:
    """
    Run the given command, streaming its stdout/stderr to console
    and accumulating it in log_lines.
    """
    header = ">>> " + " ".join(cmd)
    print(header)
    log_lines.append(header)

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.stdout:
        print(proc.stdout, end="")
        log_lines.append(proc.stdout)
    if proc.stderr:
        print(proc.stderr, end="", file=sys.stderr)
        log_lines.append(proc.stderr)
    if proc.returncode != 0:
        sys.exit(proc.returncode)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--find-t1",   required=True, help="T1 find-sync file")
    ap.add_argument("--find-t2",   required=True, help="T2 find-sync file")
    ap.add_argument("--raw-alice", required=True, help="Alice raw.dat file")
    ap.add_argument("--raw-bob",   required=True, help="Bob   raw.dat file")
    ap.add_argument("--name",      required=True, help="basename for outputs")
    ap.add_argument("--out-dir",   required=True, help="directory for outputs")
    ap.add_argument("--pk",    type=int,   default=90,   help="pulses per trial")
    # mutually-exclusive: either --radius 0.05  OR  --scan-radius 0.02,0.03,0.04
    group = ap.add_mutually_exclusive_group()
    group.add_argument("--radius", type=float, help="single phase-window radius (default 0.05)")
    group.add_argument("--scan-radius", help="comma-separated list of radii to scan")
    ap.add_argument("--shuffle",   type=int, default=0, help="permutation test iterations")
    ap.add_argument("--bootstrap", type=int, default=0, help="bootstrap iterations")
    ap.add_argument("--threads", type=int, default=0, help="number of worker processes, default 16")
    ap.add_argument("--seed", type=int, default=None, help="RNG seed for shuffle / bootstrap (default: None)")
    args = ap.parse_args()

    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    # prepare common output paths
    sync_json   = out / f"{args.name}_sync.json"
    parquet_out = out / f"{args.name}_raw.parquet"
    report_txt  = out / f"{args.name}_report.txt"

    # we'll accumulate all console output here and dump it at the end
    log_lines: List[str] = []

    # 1) build sync table
    run([
        "python", "build_sync_table.py",
        args.find_t1, args.raw_alice,
        args.find_t2, args.raw_bob,
        "--out", str(sync_json),
        "--pk", str(args.pk),
    ], log_lines)

    # 2) raw -> parquet
    run([
        "python", "raw_to_parquet.py",
        args.raw_alice,
        args.raw_bob,
        str(sync_json),
        "--out", str(parquet_out)
    ], log_lines)

    # decide which radii to run
    if args.scan_radius:
        radii = [float(r) for r in args.scan_radius.split(",") if r.strip()]
    else:
        radii = [args.radius if args.radius is not None else 0.05]

    for R in radii:
        h5_out = out / f"{args.name}_{R:.3f}_mini.hdf5"

        # 3) parquet -> mini-HDF5 for radius R
        run([
            "python", "build_clicks_hdf5.py",
            str(parquet_out),
            str(sync_json),
            "--radius", str(R),
            "--out",   str(h5_out)
        ], log_lines)

        # 4) validate mini-HDF5
        run(["python", "validate_mini_hdf5.py", str(h5_out)], log_lines)

        # 5) final CH/Eberhard test
        cmd_nist = [
            "python", "acr_ch_test.py",
            str(h5_out)
        ]
        if args.shuffle > 0:
            cmd_nist += ["--shuffle", str(args.shuffle)]
        if args.bootstrap > 0:
            cmd_nist += ["--bootstrap", str(args.bootstrap)]
        if args.threads > 0:
            cmd_nist += ["--threads", str(args.threads)]
        if args.seed is not None:
            cmd_nist += ["--seed", str(args.seed)]
        run(cmd_nist, log_lines)

    # write full log to report file
    with report_txt.open("w") as f:
        f.write("\n".join(log_lines) + "\n")
    print(f"\nReport saved to: {report_txt}")

if __name__ == "__main__":
    main()
