#!/bin/bash
# run_all_ch.sh - helper to execute the CH pipeline over 8 NIST data sets
# Usage: ./run_all_ch.sh
set -euo pipefail

FILES=(
    "run00_44 00_03_find_sync.T1.dat 00_03_find_sync.T2.dat 00_44_CH_pockel_100kHz.run3.alice.dat 00_43_CH_pockel_100kHz.run3.bob.dat"
    "run02_54 02_24_find_sync.T1.dat 02_24_find_sync.T2.dat 02_54_CH_pockel_100kHz.run4.afterTimingfix2.alice.dat 02_54_CH_pockel_100kHz.run4.afterTimingfix2.bob.dat"
    "run03_31 02_24_find_sync.T1.dat 02_24_find_sync.T2.dat 03_31_CH_pockel_100kHz.run4.afterTimingfix2_training.alice.dat 03_31_CH_pockel_100kHz.run4.afterTimingfix2_training.bob.dat"
    "run03_43 02_24_find_sync.T1.dat 02_24_find_sync.T2.dat 03_43_CH_pockel_100kHz.run4.afterTimingfix2_afterfixingModeLocking.alice.dat 03_43_CH_pockel_100kHz.run4.afterTimingfix2_afterfixingModeLocking.bob.dat"
    "run19_45 19_44_find_sync.T1.dat 19_44_find_sync.T2.dat 19_45_CH_pockel_100kHz.run.nolightconeshift.alice.dat 19_44_CH_pockel_100kHz.run.nolightconeshift.bob.dat"
    "run21_15 21_05_find_sync.T1.dat 21_04_find_sync.T2.dat 21_15_CH_pockel_100kHz.run.200nsadditiondelay_lightconeshift.alice.dat 21_15_CH_pockel_100kHz.run.200nsadditiondelay_lightconeshift.bob.dat"
    "run22_20 23_27_find_sync.T1.dat 23_26_find_sync.T2.dat 22_20_CH_pockel_100kHz.run.200nsreduceddelay_lightconeshift.alice.dat 22_20_CH_pockel_100kHz.run.200nsreduceddelay_lightconeshift.bob.dat"
    "run23_55 23_44_find_sync.T1.dat 23_44_find_sync.T2.dat 23_55_CH_pockel_100kHz.run.ClassicalRNGXOR.alice.dat 23_55_CH_pockel_100kHz.run.ClassicalRNGXOR.bob.dat"
)

PK=90
SCAN="0.02,0.03,0.04,0.05,0.06,0.07"

# create output directory if it doesn't exist
mkdir -p "/out"

for line in "${FILES[@]}"; do
    read tag fT1 fT2 aliceRAW bobRAW <<<"${line}"

    # ---------- single radius 0.05 m ----------
    python \
        pipeline.py \
            --find-t1   /data/${fT1} \
            --find-t2   /data/${fT2} \
            --raw-alice /data/${aliceRAW} \
            --raw-bob   /data/${bobRAW} \
            --name      ${tag} \
            --out-dir   /out \
            --pk        ${PK} \
            --radius    0.05

    # ---------- scan radius 0.02-0.07 m -------
    python \
        pipeline.py \
            --find-t1   /data/${fT1} \
            --find-t2   /data/${fT2} \
            --raw-alice /data/${aliceRAW} \
            --raw-bob   /data/${bobRAW} \
            --name      ${tag}_scan \
            --out-dir   /out/scan \
            --pk        ${PK} \
            --scan-radius "${SCAN}"
done
