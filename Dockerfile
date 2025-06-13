FROM python:3.12-slim

ENV MPLBACKEND=Agg

# native libs for h5py / pyarrow
RUN apt-get update && \
    apt-get install --no-install-recommends -y build-essential libhdf5-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1. Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. CH pipeline scripts
COPY pipeline.py build_sync_table.py raw_to_parquet.py \
     build_clicks_hdf5.py validate_mini_hdf5.py acr_ch_test.py ./

# 3. T3 pipeline scripts
COPY t3_pipeline.py build_t3_counts.py acr_t3_test.py combine_t3.py ./

# 4. Diagnostics scripts
COPY diagnostic_pipeline.py check_covariance.py gps_jitter_check.py \
     scan_pk_overlap.py pk_overlap_mc.py phase_peak_scan.py \
     cumulative_ch_plot.py bitmask_coverage.py \
     scan_ch_plot.py ./

# 5. Helper scripts
COPY run_all_ch.sh run_all_t3.sh run_all_diag.sh \
     generate_checksums.sh verify_checksums.sh ./
RUN chmod +x run_all_ch.sh run_all_t3.sh run_all_diag.sh \
    generate_checksums.sh verify_checksums.sh

COPY entrypoint.sh ./
RUN chmod +x entrypoint.sh

# default entrypoint = CH pipeline
ENTRYPOINT ["./entrypoint.sh"]