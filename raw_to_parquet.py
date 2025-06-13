#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
raw_to_parquet.py
=================
Convert one NIST 24-byte raw pair (Alice + Bob) into a compact Parquet table
using the *good-sync* indices produced by **build_sync_table.py**.

Input
-----
alice_raw.dat, bob_raw.dat : binary streams (24 bytes / record)
sync_table.json            : contains
    delta_ticks            - FPGA-tick period Delta between GPS pulses
    pk                     - pulses-per-trial (90 for 100 kHz data)
    alice_sync_idx         - indices of "good" sync records (Alice)
    bob_sync_idx           - same for Bob

Output
------
<name>.parquet (ZSTD-compressed) with the columns

    trial  : uint32   sequential trial index
    pulse  : uint16   0 ... pk-1, position of pulse within trial
    time   : uint64   original timestamp (FPGA ticks, 320 ps each)
    side   : uint8    0 = Alice, 1 = Bob
    chan   : uint8    detector / RNG channel number

Algorithm
---------
1.  Read all records for each side (chan, timetag).
2.  Assign trial = index of most recent *good-sync*.
3.  Compute
        pulse = floor((timetag - timetag_sync) / Delta)
    where Delta = delta_ticks.
4.  Keep records with 0 <= pulse < pk.  
5.  Concatenate Alice + Bob and write a Parquet file
    with ZSTD compression level 6.

Extra safety checks
-------------------
* sync arrays non-empty and strictly increasing;
* 100 000 <= Delta <= 140 000;
* 0 < pk <= 65 535 (fits uint16).

The numerical output matches the NIST data format; the
asserts merely stop execution early on corrupt inputs.
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from numpy.typing import NDArray

# ---------------------------------------------------------------------------
REC_SZ               = 24                    # bytes per raw record
SYNC_CH              = 6                     # GPS-sync channel
DELTA_MIN, DELTA_MAX = 100_000, 140_000      # plausible Delta range
# ---------------------------------------------------------------------------


# ----------------------------- helpers ------------------------------------ #
def read_field(path: Path, field: str) -> NDArray:
    """Return numpy array of 'chan' or 'tag' from 24-byte raw file."""
    buf = np.fromfile(path, dtype=np.uint8)
    if buf.size % REC_SZ:
        raise RuntimeError(f"{path.name}: size not multiple of {REC_SZ}")
    rec = buf.reshape(-1, REC_SZ)
    if field == "chan":
        return rec[:, 0].copy()
    if field == "tag":
        return rec[:, 8:16].view("<u8").ravel().copy()
    raise ValueError("field must be 'chan' or 'tag'")


def convert_side(raw_path: Path,
                 good_sync: NDArray[np.int64],
                 delta: int,
                 pk: int,
                 side_id: int
                 ) -> pd.DataFrame:
    """
    Build DataFrame for one detector side.

    Parameters
    ----------
    good_sync : ndarray[int64]
        Indices of sync pulses (length = #trials + 1).
    delta : int
        Period Delta in FPGA ticks.
    """
    n_rec = raw_path.stat().st_size // REC_SZ
    chan_all = read_field(raw_path, "chan")
    tag_all  = read_field(raw_path, "tag")

    # -------- assign trial number to every record -------------------------
    trial_no   = np.searchsorted(good_sync, np.arange(n_rec), side="right") - 1
    valid_sync = trial_no >= 0

    # ---------------------------------------------------------------------
    # pulse index inside the trial:
    #     pulse = floor((tag - tag_sync) / Delta)
    # Out-of-window pulses (pulse >= pk) will be discarded later by `keep`.
    # ---------------------------------------------------------------------
    sync_tag      = np.full(n_rec, -1, dtype=np.int64)
    sync_tag[good_sync] = tag_all[good_sync]
    sync_tag      = np.maximum.accumulate(sync_tag)

    pulse_idx     = np.zeros_like(tag_all, dtype=np.uint16)
    idx           = valid_sync

    diff = (tag_all[idx] - sync_tag[idx]) // delta
    diff = np.where(diff < 0, pk, diff)
    pulse_idx[idx] = diff.astype(np.uint16)

    # keep only pulses within first pk windows
    keep = valid_sync & (pulse_idx < pk)

    df = pd.DataFrame({
        "trial": trial_no[keep].astype(np.uint32),
        "pulse": pulse_idx[keep],
        "time":  tag_all[keep],
        "side":  np.full(np.count_nonzero(keep), side_id, np.uint8),
        "chan":  chan_all[keep],
    })
    return df


# ------------------------------ main -------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("alice_raw")
    ap.add_argument("bob_raw")
    ap.add_argument("sync_json")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    # -------- load sync-table --------------------------------------------
    sync   = json.loads(Path(args.sync_json).read_text())
    delta  = int(sync["delta_ticks"])
    pk     = int(sync["pk"])
    good_A = np.array(sync["alice_sync_idx"], dtype=np.int64)
    good_B = np.array(sync["bob_sync_idx"],   dtype=np.int64)

    # -------- sanity checks ----------------------------------------------
    assert good_A.size and good_B.size, "sync table is empty"
    assert np.all(np.diff(good_A) > 0) and np.all(np.diff(good_B) > 0), \
           "sync indices must be strictly ascending"
    if delta <= 0:
        raise RuntimeError(f"{args.sync_json}: delta_ticks must be > 0")
    assert DELTA_MIN <= delta <= DELTA_MAX, "delta_ticks out of expected range"
    assert 0 < pk <= 65_535, "pk must fit into uint16"
    # ---------------------------------------------------------------------

    print(f"PK={pk}, Delta={delta}  |  good-sync: Alice {len(good_A):,}  |  Bob {len(good_B):,}")

    # Alice ----------------------------------------------------------------
    df_a = convert_side(Path(args.alice_raw), good_A, delta, pk, side_id=0)

    # Bob ------------------------------------------------------------------
    df_b = convert_side(Path(args.bob_raw),   good_B, delta, pk, side_id=1)

    # ---------------- concatenate & write Parquet -------------------------
    df_all = pd.concat([df_a, df_b], ignore_index=True)

    print(f"rows = {len(df_all):,}  |  unique trials = {df_all['trial'].nunique():,}")
    pq.write_table(
        pa.Table.from_pandas(df_all, preserve_index=False),
        args.out,
        compression="zstd",
        compression_level=6
    )
    print("Parquet saved to:", args.out)


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    main()
