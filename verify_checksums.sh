#!/usr/bin/env bash
# verify_checksums.sh
# -------------------
# This script verifies SHA-256 checksums for files listed in a specified file.

set -euo pipefail

checksum_file="/out/checksums.txt"

# Check if checksum file exists
if [[ ! -f "$checksum_file" ]]; then
    echo "Error: checksums file not found at $checksum_file"
    exit 1
fi

echo "Verifying checksums from $checksum_file..."
echo

error_count=0

while IFS= read -r line || [[ -n "$line" ]]; do
    recorded_hash="${line%%[[:space:]]*}"
    file_path="${line#*  }"

    if [[ ! -e "$file_path" ]]; then
        echo "MISSING: $file_path"
        ((error_count++))
        continue
    fi

    actual_hash=$(sha256sum "$file_path" | awk '{print $1}')

    if [[ "$actual_hash" == "$recorded_hash" ]]; then
        echo "OK:       $file_path"
    else
        echo "MISMATCH: $file_path"
        ((error_count++))
    fi
done < "$checksum_file"

echo

if (( error_count > 0 )); then
    echo "Verification completed: $error_count error(s) detected."
    exit 1
else
    echo "All files verified successfully."
    exit 0
fi
