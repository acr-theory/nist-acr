#!/usr/bin/env python3
"""
build_clicks_hdf5.py
====================
Convert one or several *raw*.parquet files (produced by `raw_to_parquet.py`)
plus a `sync_table.json` into a compact "mini-HDF5" that contains only the
information needed for the CH/Eberhard analysis.

HDF5 layout
-----------
/alice|bob/clicks    uint16  - bit-mask OR of detector pulses 0..15
/alice|bob/settings  uint8   - 1 (SETTING0) or 2 (SETTING1)
/phase_ticks         int64   - phase residual of each kept trial (0..Delta-1)
/period_ticks        int64   - scalar FPGA period Delta (same for all)

Algorithm
--------------------------------------------
1. Centre of the phase peak is found from a 400-bin histogram.
2. All detector events (channel 0) whose phase is within +/-`radius`*Delta are
   OR-reduced into a 16-bit word  (bit = pulse mod 16).
3. Settings are taken from the **first** RNG pulse in each trial
   (channel 2 -> 1, channel 4 -> 2).
4. Only trials where both sides have a non-zero RNG setting are kept.
5. The file also stores "phase_ticks" and "period_ticks".  These extra
   datasets are read by diagnostic tools such as phase_peak_scan.py and
   gps_jitter_check.py.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

import h5py
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from numpy.typing import NDArray

# --------------------------- detector / RNG channels ---------------------- #
DETECTOR_CH  = 0          # detector click
SETTING0_CH  = 2          # RNG "0"  -> setting 1
SETTING1_CH  = 4          # RNG "1"  -> setting 2
# -------------------------------------------------------------------------- #


def peak_center(ph: NDArray[np.float64]) -> float:
    """Return centre of the highest bin in a 400-bin phase histogram."""
    hist, bins = np.histogram(ph, bins=400, range=(0.0, 1.0))
    idx = hist.argmax()
    return 0.5 * (bins[idx] + bins[idx + 1])


def build_side(df: pd.DataFrame,
               centre: float,
               delta:  int,
               radius: float
               ) -> tuple[NDArray[np.uint16], NDArray[np.uint8]]:
    """Return clicks[] and settings[] for one detector side."""
    phase = ((df["time"] % delta) / delta).to_numpy()
    in_peak = (np.abs(phase - centre) < radius) | (np.abs(phase - centre + 1) < radius)

    # -- detector rows inside the phase window ---------------------------------
    det_rows = df[in_peak & (df["chan"] == DETECTOR_CH)].copy()
    det_rows["bit"] = (det_rows["pulse"] % 16).astype(np.uint8)

    # -- first RNG pulse per trial ---------------------------------------------
    rng_rows  = df[df["chan"].isin([SETTING0_CH, SETTING1_CH])]
    first_rng = rng_rows.groupby("trial").first()

    n_trials = int(df["trial"].max()) + 1
    clicks   = np.zeros(n_trials, np.uint16)
    settings = np.zeros(n_trials, np.uint8)

    # settings: 1 if channel 2 else 2
    settings[first_rng.index] = np.where(first_rng["chan"] == SETTING0_CH, 1, 2)

    # clicks: OR-reduce over all detector pulses in the trial
    for t, grp in det_rows.groupby("trial"):
        clicks[t] = np.bitwise_or.reduce(1 << grp["bit"].to_numpy())

    # --- sanity info: how many trials have >1 bit -------------------------
    multi = (clicks != 0) & ((clicks & (clicks - 1)) != 0)
    n_multi = int(multi.sum())
    if n_multi:
        print(f"   [info] {n_multi:,} trials contain >1 detector bit "
              f"({n_multi / clicks.size:.2%}) - expected for radius {radius}")

    return clicks, settings


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("parquet", nargs="+", help="raw*.parquet (one or many)")
    ap.add_argument("sync_json",          help="sync_table.json")
    ap.add_argument("--radius", type=float, default=0.05, help="phase window (fraction of Delta), default 0.05 = +/- 5 %")
    ap.add_argument("--out", default="mini.hdf5", help="output HDF5 filename (default mini.hdf5)")
    args = ap.parse_args()

    # ---------------------------------------------------------------------- #
    if not (0.0 < args.radius < 0.5):
        raise ValueError("--radius must be between 0 and 0.5")

    sync = json.loads(Path(args.sync_json).read_text())
    delta = int(sync["delta_ticks"])

    # concatenate all parquet tables
    df_all = pd.concat(
        [pq.read_table(p).to_pandas() for p in args.parquet],
        ignore_index=True)

    # --------------------------- build both sides ------------------------- #
    phase_list: list[np.ndarray] = []

    for label, side in [("Alice", 0), ("Bob", 1)]:
        df_side = df_all[df_all["side"] == side]
        centre  = peak_center(((df_side["time"] % delta) / delta).to_numpy())
        print(f"{label} phase peak @ {centre:.4f}")
        if side == 0:
            clicks_a, settings_a = build_side(df_side, centre, delta, args.radius)
        else:
            clicks_b, settings_b = build_side(df_side, centre, delta, args.radius)

        # accumulate the phases of "good" clicks for this side
        phase_side = ((df_side["time"] % delta)) / delta
        in_peak    = (np.abs(phase_side - centre) < args.radius) | (
                     np.abs(phase_side - centre + 1) < args.radius)
        det_mask   = (df_side["chan"] == DETECTOR_CH) & in_peak
        phase_list.append((df_side.loc[det_mask, "time"] % delta).to_numpy())

    # trials where both settings are non-zero
    common = np.intersect1d(np.nonzero(settings_a)[0], np.nonzero(settings_b)[0])

    # ---------- save HDF5 --------------------------------------------------
    phase_residual = np.concatenate(phase_list).astype(np.int64)
    period_ticks   = np.int64(delta)

    with h5py.File(args.out, "w") as h:
        g_a = h.create_group("alice")
        g_b = h.create_group("bob")
        g_a["clicks"]   = clicks_a  [common]
        g_a["settings"] = settings_a[common]
        g_b["clicks"]   = clicks_b  [common]
        g_b["settings"] = settings_b[common]

        # --- datasets for diagnostics ---
        h["phase_ticks"]  = phase_residual    # only valid clicks
        h["period_ticks"] = period_ticks      # scalar, same for all

    print("HDF5 saved to:", args.out)


if __name__ == "__main__":
    main()
