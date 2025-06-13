#!/usr/bin/env python3
"""
build_sync_table.py
===================
Generate a JSON file that lists the *good* GPS-sync pulses found in one
Alice/Bob raw pair.  
In addition to the integer indices stored earlier, the file now also
keeps the exact FPGA-tick timestamps of those pulses (*_sync_tag).

Good-sync definition (follows the procedure implied by NIST data structure):

1. In the T1 / T2 *find-sync* file pick the channel that occurs most
   often (for 2015-09-18/19 data it must be channel 6).
2. Delta = median period between successive sync pulses.
3. phi0  = timestamp of the **first** sync pulse in the find-sync file.
4. A sync record in the raw file is *good* when its phase

        phase = (tag_raw - phi0) mod Delta

   is within +/-5 FPGA ticks (320 ps) of 0.
   That leaves exactly one GPS pulse - hence one trial - per period Delta.

The JSON output is later consumed by `raw_to_parquet.py`.

JSON schema
-----------
{
    "delta_ticks"    : int,      # median Delta in FPGA ticks
    "pk"             : int,      # pulses per trial (90 for 100 kHz files); metadata
    "alice_sync_idx" : [int, ...], # good-sync indices in (Alice)
    "bob_sync_idx"   : [int, ...], # same for (Bob)
    "alice_sync_tag" : [int, ...], # corresponding 64-bit timestamps for (Alice)
    "bob_sync_tag"   : [int, ...]  # and same for (Bob)
}
"""

from __future__ import annotations
import argparse
import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

# --------------------------------------------------------------------------- #
SYNC_CH_EXPECTED     = 6
PHASE_TOL_TICKS      = 5                  # +/-5 ticks = +/-1.6 ns
DELTA_MIN, DELTA_MAX = 100_000, 140_000   # plausible FPGA period range
PK_DEFAULT           = 90                 # pulses per trial for 100 kHz data; stored as metadata for downstream analysis
REC_SZ               = 24                 # bytes per raw record
# --------------------------------------------------------------------------- #


# ----------------------------- low-level IO -------------------------------- #
def read_field(path: Path, field: str, *, tag_offset: int) -> NDArray:
    """Return numpy array of 'chan' or 'tag' for a 24-byte record file."""
    buf = np.fromfile(path, dtype=np.uint8)
    if buf.size % REC_SZ:
        raise RuntimeError(f"{path.name}: size not multiple of {REC_SZ}")
    rec = buf.reshape(-1, REC_SZ)
    if field == "chan":
        return rec[:, 0].copy()
    if field == "tag":
        return rec[:, tag_offset : tag_offset + 8].view("<u8").ravel().copy()
    raise ValueError("field must be 'chan' or 'tag'")


# -------------------------- find good-sync -------------------------------- #
def find_good_sync(chan_fsync: NDArray[np.uint8],
                   tag_fsync:  NDArray[np.uint64],
                   chan_raw:   NDArray[np.uint8],
                   tag_raw:    NDArray[np.uint64],
                   *,
                   label: str
                   ) -> tuple[int, NDArray[np.int64]]:
    """Return (delta_ticks, indices_of_good_sync) for one detector side."""

    # 1) choose sync channel (most frequent in find-sync)
    uniq, cnt = np.unique(chan_fsync, return_counts=True)
    sync_ch   = int(uniq[np.argmax(cnt)])
    print(f"  {label:<6}  chosen sync channel = {sync_ch}")
    assert sync_ch == SYNC_CH_EXPECTED, "unexpected GPS-sync channel"

    # 2) locate sync events in raw file
    sync_idx = np.flatnonzero(chan_raw == sync_ch)
    if sync_idx.size == 0:
        raise RuntimeError(f"{label}: sync channel {sync_ch} not found in raw")
    sync_tag = tag_raw[sync_idx]

    # 3) Delta = median period
    delta = int(np.median(np.diff(sync_tag)))
    print(f"           Delta (median) = {delta} ticks")
    assert DELTA_MIN <= delta <= DELTA_MAX, "Delta out of expected range"

    # 4) phase test relative to first find-sync pulse
    phi0  = tag_fsync[np.flatnonzero(chan_fsync == sync_ch)[0]]
    phase = (sync_tag - phi0) % delta
    good_mask = (phase <= PHASE_TOL_TICKS) | (phase >= delta - PHASE_TOL_TICKS)
    good_idx  = sync_idx[good_mask]

    print(f"           good-sync in raw: {len(good_idx):,}")
    return delta, good_idx.astype(np.int64)


# --------------------------------- main ----------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description="Create sync_table.json")
    ap.add_argument("find_t1")
    ap.add_argument("raw_alice")
    ap.add_argument("find_t2")
    ap.add_argument("raw_bob")
    ap.add_argument("--out", required=True, help="output JSON file")
    ap.add_argument("--pk", type=int, default=PK_DEFAULT, help="pulses per trial")
    args = ap.parse_args()

    # -------- Alice --------------------------------------------------------
    chan_f_A = read_field(Path(args.find_t1), "chan", tag_offset=16)
    tag_f_A  = read_field(Path(args.find_t1), "tag",  tag_offset=8)
    chan_r_A = read_field(Path(args.raw_alice), "chan", tag_offset=8)
    tag_r_A  = read_field(Path(args.raw_alice), "tag",  tag_offset=8)
    delta_A, good_A = find_good_sync(chan_f_A, tag_f_A,
                                     chan_r_A, tag_r_A,
                                     label="ALICE")
    good_tag_A = tag_r_A[good_A]

    # -------- Bob ----------------------------------------------------------
    chan_f_B = read_field(Path(args.find_t2), "chan", tag_offset=16)
    tag_f_B  = read_field(Path(args.find_t2), "tag",  tag_offset=8)
    chan_r_B = read_field(Path(args.raw_bob), "chan", tag_offset=8)
    tag_r_B  = read_field(Path(args.raw_bob), "tag",  tag_offset=8)
    delta_B, good_B = find_good_sync(chan_f_B, tag_f_B,
                                     chan_r_B, tag_r_B,
                                     label="BOB")
    good_tag_B = tag_r_B[good_B]

    # -------- final checks -------------------------------------------------
    assert good_A.size and good_B.size, "no good-sync pulses found"
    assert abs(delta_A - delta_B) <= 1, "Delta mismatch > 1 tick"

    delta_avg = int(round(0.5 * (delta_A + delta_B)))
    print(f"\nAverage Delta = {delta_avg} ticks   |   pk = {args.pk}")

    out = {
        "delta_ticks"    : delta_avg,
        "pk"             : args.pk,
        "alice_sync_idx" : good_A.tolist(),
        "alice_sync_tag" : good_tag_A.tolist(),
        "bob_sync_idx"   : good_B.tolist(),
        "bob_sync_tag"   : good_tag_B.tolist()
    }

    Path(args.out).write_text(json.dumps(out, indent=2))
    print("JSON written:", args.out)


if __name__ == "__main__":
    main()
