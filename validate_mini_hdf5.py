#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_mini_hdf5.py
=====================
Quick integrity check for a *mini-HDF5* file produced by
build_clicks_hdf5.py before running the CH / Eberhard test.

For each detector side ("alice", "bob") the script verifies:

1.  `clicks` and `settings` arrays have identical length  
    -> same number of trials
2.  Every clicks value fits in 16 bits (0 ... 65535) - multi-bit patterns
    are allowed; each bit marks one detector slot
3.  Every settings value is 0, 1 or 2  
    (0 means "no RNG pulse recorded in this trial")

Exit code 0 = OK, exit code 1 = failure.  Diagnostic messages are printed
to stdout so they can be redirected or piped through `tee`.

Usage example
-------------
    python validate_mini_hdf5.py hdf5/mini_23_55.hdf5

Note: this validator targets the compact *mini* files produced by the
build_clicks_hdf5.py helper. A full raw *build* file may legitimately
fail the length test and should be processed directly by the CH-analysis
script instead.
"""

from __future__ import annotations
import argparse
import sys
from pathlib import Path

import h5py
import numpy as np
from numpy.typing import NDArray


def check_side(hf: h5py.File, side: str) -> bool:
    """Return True if all checks pass for the given side."""
    clk: NDArray[np.uint16] = hf[f"{side}/clicks"][()]
    st:  NDArray[np.uint8]  = hf[f"{side}/settings"][()]

    if clk.size != st.size:
        print(f"{side.upper()}: [FAIL] clicks / settings length mismatch")
        return False

    # clicks must fit into 16 bits (0...65535)
    if (clk >= 1 << 16).any():
        n_bad = int((clk >= 1 << 16).sum())
        print(f"{side.upper()}: [FAIL] {n_bad} clicks exceed 16-bit mask")
        return False

    # settings allowed values
    if (~np.isin(st, (0, 1, 2))).any():
        inv: NDArray = np.unique(st[~np.isin(st, (0, 1, 2))])
        print(f"{side.upper()}: [FAIL] invalid settings values {inv.tolist()}")
        return False

    print(f"{side.upper()}: [OK]   trials = {clk.size:,}")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description="Validate mini-HDF5 integrity")
    ap.add_argument("hdf5", type=Path, help="mini_*.hdf5 to validate")
    args = ap.parse_args()

    with h5py.File(args.hdf5, "r") as hf:
        ok = check_side(hf, "alice") & check_side(hf, "bob")

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
