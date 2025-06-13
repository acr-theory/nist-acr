#!/usr/bin/env bash
# run_all_diag.sh - helper to execute the diagnostic pipeline over 8 runs
set -euo pipefail

FILES=(run00_44 run02_54 run03_31 run03_43 run19_45 run21_15 run22_20 run23_55)
RADIUS=0.05
RADIUS_FMT=$(printf "%.3f" "$RADIUS")

mkdir -p "/out/diagnostics"

for tag in "${FILES[@]}"; do
    mini="/out/${tag}_${RADIUS_FMT}_mini.hdf5"
    sync="/out/${tag}_sync.json"
    report_file="/out/${tag}_diag_report.txt"
    if [[ ! -f "$mini" ]]; then
        echo "mini file $mini not found, skip"
        continue
    fi
    python \
        diagnostic_pipeline.py "$mini" "$sync" --radius "$RADIUS" --outdir /out/diagnostics
    python \
        acr_ch_test.py "$mini" --shuffle 5000 --bootstrap 5000 --seed 42 2>&1 | tee "$report_file"
done

python \
    scan_ch_plot.py --reports /out/scan --outdir /out/diagnostics/ch_scan
