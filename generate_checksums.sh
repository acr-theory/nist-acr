#!/usr/bin/env bash
# generate_checksums.sh
# ---------------------
# This script generates SHA-256 checksums for files in specified directories

set -euo pipefail

directories=(/data /out /out/t3 /out/scan)
extensions=(dat json parquet hdf5 txt)

checksum_file="/out/checksums.txt"

# Abort if the checksum file already exists
if [[ -f "$checksum_file" ]]; then
    echo "Error: $checksum_file already exists. Aborting to prevent overwrite."
    exit 1
fi

mkdir -p "$(dirname "$checksum_file")"

for dir in "${directories[@]}"; do
    for ext in "${extensions[@]}"; do
        find "$dir" -type f -name "*.${ext}" -print0 | \
        while IFS= read -r -d '' file; do
            if [[ $file != $checksum_file ]]; then
                echo "Processing file: $file"
                sha256sum "$file" >> "$checksum_file"
            fi
        done
    done
done

echo "Checksums have been written to $checksum_file"
