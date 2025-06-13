#!/usr/bin/env python3
"""
combine_t3.py
-------------
Combine several ``*_t3_counts.npz`` files into one aggregated T3 result.

Usage examples
--------------
# all files matching the glob pattern
python combine_t3.py /out/t3/run*_t3_counts.npz

# explicit list of files
python combine_t3.py result1.npz result2.npz
"""
import sys, glob, math, pathlib, argparse, numpy as np

def expand_patterns(patterns):
    """Expand shell-style wildcards in *patterns* and return a flat list of files."""
    files = []
    for p in patterns:
        if any(ch in p for ch in "*?[]"):
            files.extend(glob.glob(p))
        else:
            files.append(p)
    return files

def load_counts(path):
    """
    Load a ``*_t3_counts.npz`` file and return its first ``counts`` dict.
    """
    p = pathlib.Path(path)
    if p.suffix != ".npz":
        raise ValueError(f"Unsupported file type: {p} (expected .npz)")
    npz = np.load(p, allow_pickle=True)
    # counts is an object array; grab the first element
    return npz["counts"][0]

def main():
    """Aggregate multiple *_t3_counts.npz files and print combined totals."""
    ap = argparse.ArgumentParser(description="Combine *_t3_counts.npz results")
    ap.add_argument("patterns", nargs="*", default=["*_t3_counts.npz"], help="file names or glob patterns matching *.npz")
    ap.add_argument("--out", default="combined_t3_report.txt", help="save full console log here [default: %(default)s]")
    args       = ap.parse_args()
    patterns   = args.patterns
    report_txt = pathlib.Path(args.out)
    file_list = expand_patterns(patterns)

    if not file_list:
        sys.exit("combine_t3: no files match given pattern(s)")

    T_sum, var_sum = 0.0, 0.0
    rows = []

    for fname in file_list:
        c = load_counts(fname)
        T = (c["N_ABC"] - c["N_AB"] - c["N_AC"] - c["N_BC"]
             + c["N_A"] + c["N_B"] + c["N_C"])
        sigma = c["sigma"]
        rows.append((pathlib.Path(fname).name, T, sigma, T/sigma))
        T_sum   += T
        var_sum += sigma**2

    # collect all console lines so we can also write them to disk
    log_lines: list[str] = []
    def emit(line=""):
        print(line)
        log_lines.append(line)

    emit("PER-FILE SUMMARY")
    for name,T,sig,z in rows:
        emit(f"{name:30s}  T3={T:9.1f}  sigma={sig:7.2f}  Z={z:7.2f}")

    Sigma_tot = math.sqrt(var_sum)
    Z_tot     = T_sum / Sigma_tot

    emit()
    emit("COMBINED RESULT")
    emit(f"T_total       = {T_sum:.1f}")
    emit(f"sigma_total   = {Sigma_tot:.2f}")
    emit(f"Z_total       = {Z_tot:.2f}")

    # write report
    try:
        report_txt.write_text("\n".join(log_lines) + "\n")
        print(f"\nReport saved to: {report_txt}")
    except Exception as e:
        print(f"\n[WARNING] could not write report file: {e}")

if __name__ == "__main__":
    main()
