#!/bin/bash
# run_all_t3.sh - helper to execute the ACR-T3 pipeline over 8 data sets
# Usage: ./run_all_t3.sh   (must be in repo root; assumes ./out already populated)
set -euo pipefail

FILES=(run00_44 run02_54 run03_31 run03_43 run19_45 run21_15 run22_20 run23_55)
RADII="0.02,0.03,0.04,0.05,0.06,0.07" # radii for scan mode

for tag in "${FILES[@]}"; do
    for mode in any alice bob; do
        python \
            t3_pipeline.py \
                --parquet  /out/${tag}_raw.parquet \
                --sync     /out/${tag}_sync.json \
                --name     ${tag}_${mode} \
                --out-dir  /out/t3 \
                --radius   0.05 \
                --r-mode   ${mode} \
                --cluster 50 \
                --azuma \
                --shuffle  5000 \
                --bootstrap 5000 \
                --threads 16 \
                --shuffle-mode pair \
                --seed 42
    done
    python \
        t3_pipeline.py \
            --parquet  /out/${tag}_raw.parquet \
            --sync     /out/${tag}_sync.json \
            --name     ${tag}_scan \
            --out-dir  /out/t3 \
            --scan-radius ${RADII} \
            --r-mode   any
done

python \
    combine_t3.py '/out/t3/run*_any_t3_data.npz'  --out /out/t3/combined_t3_any_report.txt
