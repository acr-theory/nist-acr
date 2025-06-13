#!/usr/bin/env python3
"""
diagnostic_pipeline.py
======================
Run the full diagnostics suite (6 scripts) for one run.

Usage
-----
python diagnostic_pipeline.py  run02_54_0.050_mini.hdf5  run02_54_sync.json
"""

from pathlib import Path
import subprocess, argparse, sys, shlex, datetime

SCRIPTS = [
    ("gps_jitter_check.py",   True,  False),   # positional sync_json
    ("pk_overlap_mc.py",      True,  True),    # --sync flag
    ("scan_pk_overlap.py",    True,  True),    # --sync flag
    ("phase_peak_scan.py",    False, False),
    ("check_covariance.py",   False, False),
    ("cumulative_ch_plot.py", False, False),
    ("bitmask_coverage.py",   False, False),
]

def run_and_log(cmd_str: str, log_handle):
    """Run shell command, tee stdout/stderr to logfile; abort on non-zero RC."""
    print(">>>", cmd_str)
    log_handle.write(f"\n>>> {cmd_str}\n")
    res = subprocess.run(shlex.split(cmd_str), text=True, capture_output=True)
    log_handle.write(res.stdout)
    log_handle.write(res.stderr)
    log_handle.flush()
    if res.returncode:
        print(res.stderr, file=sys.stderr)
        sys.exit(res.returncode)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mini_hdf5")
    ap.add_argument("sync_json")
    ap.add_argument("--outdir", default="diagnostics")
    ap.add_argument("--radius", default="0.05")   # passed to pk_overlap_mc
    args = ap.parse_args()

    h5   = Path(args.mini_hdf5).resolve()
    sync = Path(args.sync_json).resolve()
    stem = h5.stem.replace(".hdf5","")
    out  = Path(args.outdir, stem); out.mkdir(parents=True, exist_ok=True)

    # logfile
    log_path = out / "diagnostic_report.txt"
    with log_path.open("w", encoding="utf-8") as log:
        log.write(f"# Diagnostic report for {stem}\n"
                  f"# generated {datetime.datetime.now()}\n")

        for tool, need_sync, sync_is_flag in SCRIPTS:
            # initial argv: python + script + either sync or mini-file
            if need_sync:
                if sync_is_flag:
                    cmd = ["python", tool, "--sync", str(sync)]
                else:
                    cmd = ["python", tool, str(sync)]
            else:
                cmd = ["python", tool, str(h5)]

            # additional, tool-specific parameters
            if tool == "pk_overlap_mc.py":
                # worst-case MC (discrete), 200k shots
                cmd += [
                    "--range", "60", "120", "5",
                    "--radius", args.radius,
                    "--mode", "discrete",
                    "--shots", "200000",
                    "--outdir", str(out),
                ]
            elif tool == "scan_pk_overlap.py":
                cmd += [
                    "--radius", args.radius,
                    "--outdir", str(out),
                ]
            elif tool == "gps_jitter_check.py":
                cmd += ["--outdir", str(out)]
            elif tool == "phase_peak_scan.py":
                cmd += ["--block", "1000", "--outdir", str(out)]
            elif tool == "check_covariance.py":
                cmd += ["--block", "500", "--outdir", str(out)]
            elif tool == "cumulative_ch_plot.py":
                cmd += ["--step", "100", "--outdir", str(out)]
            elif tool == "bitmask_coverage.py":
                cmd += ["--outdir", str(out)]

            run_and_log(" ".join(cmd), log)

    print(f"[saved] {log_path}")

if __name__ == "__main__":
    main()
