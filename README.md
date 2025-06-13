# nist-acr : ACR analysis pipeline for NIST 2015 Bell test data

This Docker image reproduces the **Architecture of Coherent Reality** (ACR) analysis workflow on the loophole-free NIST 2015 Bell test data. It converts native `.dat` files into Parquet, builds compact HDF5 "mini" files, and computes

* the **normalized Clauser-Horne (CH)** statistic, and
* the **third-order T3** statistic (radius scan + permutation / bootstrap).

All steps are scriptable and deterministic; anyone can rebuild the numbers published in the ACR CH/T3 report.

## Prerequisites

* Docker >= 24 and Docker Compose v2 (`docker compose` command).
* ~15 GB of free disk space (raw files + intermediate Parquet/HDF5 + output) for a single data pair (`*_sync.T1.dat`, `*_sync.T2.dat`, `*alice.dat`, `*bob.dat`).
* ~105 GB total required if you plan to run all 8 recommended ACR analysis runs.
* Place the [NIST raw](https://www.nist.gov/pml/applied-physics-division/bell-test-research-software-and-data/repository-bell-test-research-3) `.dat` files and corresponding `*_find_sync.T{1,2}.dat` in `./data` directory.

List of `.dat` files used for all 8 recommended ACR analysis runs:

|**Series**| **NIST raw `.dat` files**|
|----------|---------------|
|`run00_44`|`00_03_find_sync.T1.dat`<br>`00_03_find_sync.T2.dat`<br>`00_44_CH_pockel_100kHz.run3.alice.dat`<br>`00_43_CH_pockel_100kHz.run3.bob.dat`|
|`run02_54`|`02_24_find_sync.T1.dat`<br>`02_24_find_sync.T2.dat`<br>`02_54_CH_pockel_100kHz.run4.afterTimingfix2.alice.dat`<br>`02_54_CH_pockel_100kHz.run4.afterTimingfix2.bob.dat`|
|`run03_31`|`02_24_find_sync.T1.dat`<br>`02_24_find_sync.T2.dat`<br>`03_31_CH_pockel_100kHz.run4.afterTimingfix2_training.alice.dat`<br>`03_31_CH_pockel_100kHz.run4.afterTimingfix2_training.bob.dat`|
|`run03_43`|`02_24_find_sync.T1.dat`<br>`02_24_find_sync.T2.dat`<br>`03_43_CH_pockel_100kHz.run4.afterTimingfix2_afterfixingModeLocking.alice.dat`<br>`03_43_CH_pockel_100kHz.run4.afterTimingfix2_afterfixingModeLocking.bob.dat`|
|`run19_45`|`19_44_find_sync.T1.dat`<br>`19_44_find_sync.T2.dat`<br>`19_45_CH_pockel_100kHz.run.nolightconeshift.alice.dat`<br>`19_44_CH_pockel_100kHz.run.nolightconeshift.bob.dat`|
|`run21_15`|`21_05_find_sync.T1.dat`<br>`21_04_find_sync.T2.dat`<br>`21_15_CH_pockel_100kHz.run.200nsadditiondelay_lightconeshift.alice.dat`<br>`21_15_CH_pockel_100kHz.run.200nsadditiondelay_lightconeshift.bob.dat`|
|`run22_20`|`23_27_find_sync.T1.dat`<br>`23_26_find_sync.T2.dat`<br>`22_20_CH_pockel_100kHz.run.200nsreduceddelay_lightconeshift.alice.dat`<br>`22_20_CH_pockel_100kHz.run.200nsreduceddelay_lightconeshift.bob.dat`|
|`run23_55`|`23_44_find_sync.T1.dat`<br>`23_44_find_sync.T2.dat`<br>`23_55_CH_pockel_100kHz.run.ClassicalRNGXOR.alice.dat`<br>`23_55_CH_pockel_100kHz.run.ClassicalRNGXOR.bob.dat`|

Tested under Windows 11 (WSL 2). Docker version 27.0.3, build 7d4bcd8

---

## Quick start

1. Build the image (Python 3.12-slim base)
```bash
docker compose build          # produces image "nist-acr:latest"
```

2. Prepare host folders
```bash
mkdir -p data out             # make sure "data" and "out" directories exists
```

3. Download and copy all [NIST raw](https://www.nist.gov/pml/applied-physics-division/bell-test-research-software-and-data/repository-bell-test-research-3) `*.dat` and `*find_sync.T*.dat` files listed in the table above into the `./data` directory.

4. Run all tests + diagnostics
```bash
# Run CH test pipeline for all 8 recommended ACR analysis runs
docker compose run --rm nist-acr \
    bash run_all_ch.sh

# Then run T3 test pipeline for all 8 recommended ACR analysis runs
docker compose run --rm nist-acr \
    bash run_all_t3.sh

# Then run all diagnostics (optional)
docker compose run --rm nist-acr \
    bash run_all_diag.sh
```

## Clauser-Horne test pipeline

Main CH test pipeline. By default, the container is set to execute `pipeline.py`, which is the main CH pipeline, so you don't have to specify it manually.

run a single data pair -> CH statistic
```bash
docker compose run --rm nist-acr \
  --find-t1   /data/00_03_find_sync.T1.dat \
  --find-t2   /data/00_03_find_sync.T2.dat \
  --raw-alice /data/00_44_CH_pockel_100kHz.run3.alice.dat \
  --raw-bob   /data/00_43_CH_pockel_100kHz.run3.bob.dat \
  --name      run00_44 \
  --out-dir   /out
```

The standard list of supported parameters for the CH test pipeline:

```bash
--find-t1   /data/${fT1} \          # location of the find sync T1 `.dat` file
--find-t2   /data/${fT2} \          # location of the find sync T2 `.dat` file
--raw-alice /data/${aliceRAW} \     # location of the raw Alice `.dat` file
--raw-bob   /data/${bobRAW} \       # location of the raw Bob `.dat` file
--name      ${tag} \                # name to use for output result files
--out-dir   /out \                  # output directory
--pk        ${PK} \                 # pk value, default is 90
```

There are also 2 more parameters available, but they cannot be used together. Only one of these options can be used at a time.
```bash
--radius    0.05                    # phase window radius, default is 0.05
# or
--scan-radius "0.02,0.03,0.04,0.05,0.06,0.07" # comma-separated list of radii to scan
```

Additionally, a couple of extra parameters are available:
```bash
--shuffle   5000                    # permutation test iterations
--bootstrap 5000                    # bootstrap iterations
--threads   16                      # number of worker processes, used only in shuffle/bootstrap mode. Default is 16 or the maximum available CPU count.
--seed      42                      # RNG seed for shuffle / bootstrap. Default: None.
```

## Third-order T3 test pipeline

T3 pipeline expects that CH run has already been completed and uses files from `/out` directory to conduct the T3 test further.

Base run (radius 0.05, r-mode any)
```bash
docker compose run --rm nist-acr \
    t3_pipeline.py \
        --parquet /out/run00_44_raw.parquet \
        --sync    /out/run00_44_sync.json \
        --name    run00_44_any \
        --out-dir /out/t3 \
        --radius 0.05 \
        --r-mode any \
        --shuffle 5000 \
        --bootstrap 5000 \
        --seed 42
```

Checking the sign (Alice-only)
```bash
docker compose run --rm nist-acr \
    t3_pipeline.py \
        --parquet /out/run00_44_raw.parquet \
        --sync    /out/run00_44_sync.json \
        --name    run00_44_alice \
        --out-dir /out/t3 \
        --radius 0.05 \
        --r-mode alice \
        --shuffle 5000 \
        --bootstrap 5000 \
        --seed 42
```

Checking the sign (Bob-only)
```bash
docker compose run --rm nist-acr \
    t3_pipeline.py \
        --parquet /out/run00_44_raw.parquet \
        --sync    /out/run00_44_sync.json \
        --name    run00_44_bob \
        --out-dir /out/t3 \
        --radius 0.05 \
        --r-mode bob \
        --shuffle 5000 \
        --bootstrap 5000 \
        --seed 42
```

Radius-scan (produces run00_44_scan_t3_counts.json)
```bash
docker compose run --rm nist-acr \
    t3_pipeline.py \
        --parquet /out/run00_44_raw.parquet \
        --sync    /out/run00_44_sync.json \
        --name    run00_44_scan \
        --out-dir /out/t3 \
        --scan-radius 0.02,0.03,0.04,0.05,0.06,0.07 \
        --r-mode any
```

Additionally, a couple of extra parameters are available:
```bash
--cluster 50            # cluster-robust sigma with non-overlapping blocks of 50 trials (0 = off)
--azuma                 # append Azuma-Hoeffding two-sided tail-bound p-value
--shuffle-mode pair     # pair or side shuffle mode options available. Default value is "pair".
--threads      16       # number of worker processes, used only in shuffle/bootstrap mode. Default is 16 or the maximum available CPU count.
--seed         42       # RNG seed for shuffle / bootstrap. Default: None.
```

After T3 test runs complete, you can run `combine_t3.py` script to generate combined T3 results report:

```bash
docker compose run --rm nist-acr \
    combine_t3.py '/out/t3/run*_any_t3_data.npz'
```

## Diagnostics pipeline

The following scripts are available for diagnostics and plot generation.
* gps_jitter_check.py
* pk_overlap_mc.py
* scan_pk_overlap.py
* phase_peak_scan.py
* check_covariance.py
* cumulative_ch_plot.py
* bitmask_coverage.py
* scan_ch_plot.py

### Usage example
This will execute all 7 diagnostic scripts except `scan_ch_plot.py`:
```bash
docker compose run --rm nist-acr \
    diagnostic_pipeline.py run02_54_0.050_mini.hdf5 run02_54_sync.json --radius 0.05 --outdir /out/diagnostics
```

To run `scan_ch_plot.py` separately:
```bash
docker compose run --rm nist-acr \
    scan_ch_plot.py --reports /out/scan --outdir /out/diagnostics/ch_scan
```

## Additional helper scripts/files

* `run_all_ch.sh` – runs all 8 recommended ACR CH test runs.
* `run_all_t3.sh` – runs all 8 recommended ACR T3 test runs.
* `run_all_diag.sh` – runs all 7 diagnostics on the 8 recommended ACR CH test runs, and then runs `scan_ch_plot.py`.
* `generate_checksums.sh` – generates checksums for `dat`, `json`, `parquet`, `hdf5`, and `txt` files in `./data` and `./out`, then stores them in `./out/checksums.txt`. This script will stop execution with an error if `./out/checksums.txt` exists, to prevent overwriting. Make sure that `./out/checksums.txt` does not exist before executing this script.
* `verify_checksums.sh` – verifies that SHA256 sums from `./out/checksums.txt` match the actual SHA256 sum of each listed file.

Usage example:
```bash
# Run all 8 CH tests
docker compose run --rm nist-acr \
    bash run_all_ch.sh

# Then run all 8 T3 tests
docker compose run --rm nist-acr \
    bash run_all_t3.sh

# Then run all diagnostics (optional)
docker compose run --rm nist-acr \
    bash run_all_diag.sh

# Generate checksums
docker compose run --rm nist-acr \
    bash generate_checksums.sh

# Verify checksums
docker compose run --rm nist-acr \
    bash verify_checksums.sh
```

## Data provenance & NIST disclaimer

This pipeline re-analyses the public-domain data set **"Bell Test Research Software and Data"** published by NIST (2015).

* Upstream algorithms: original NIST script `calc_ch_from_hdf5.py`  
* Complete NIST Software Disclaimer is reproduced in
  [`NOTICE_NIST.txt`](NOTICE_NIST.txt)
  NIST page: <https://www.nist.gov/oism/copyrights#software>

_Raw `.dat` streams are **not redistributed** here; download them from the URL in the table above and run the pipeline to reproduce every result._

## AI Usage Disclosure

Preliminary code skeletons in this repository were generated with ChatGPT 
(OpenAI; versions o1-pro, o3, o4-mini-high, GPT-4o, used between May 2024–June 2025).
All final scripts were reviewed, tested, and approved by the human author (A. Ahmedov).
No AI model is listed as a co-author.

## License
All code in this repository is released under the [MIT License](LICENSE).  
The upstream NIST scripts are in the public domain (NIST-PD); see
[NOTICE_NIST.txt](NOTICE_NIST.txt) for the full disclaimer.