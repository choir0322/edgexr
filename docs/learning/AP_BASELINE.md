# Follow one AP baseline sample through the code

This is a measurement path beside the live camera path, not another worker in
the preview. Read [the run procedure](../AP_BASELINE.md) before operating the Pi.

1. `app.live_preview.start_workers()` launches FFmpeg. `State.ffmpeg_pid`
   remembers its PID; the HTTP handler's `/api/telemetry` response adds that
   PID and `os.getpid()` for Python, then removes `pixels_b64`. The ordinary
   `/api/frame` browser response is unchanged. Read
   [`live_preview.py`](../../src/app/live_preview.py).
2. `profiling.ap_baseline.main()` validates CLI arguments and calls
   `run_baseline()`. It first asks `vision.tracking_trial.fetch_snapshot()` for
   metrics-only JSON. `validate_preview()` requires camera `live`, detector
   `ready` in `basic` mode, IMU `ready`, and positive PIDs. This is why an
   existing motion-aware run cannot accidentally become the baseline.
3. `read_process()` reads `/proc/<pid>/stat` for cumulative user+system CPU
   ticks and process start ticks, then `/proc/<pid>/status` for parent PID and
   RSS in KiB. `read_counters()` rejects an FFmpeg PID that is not the preview's
   child. Start ticks protect against Linux recycling a PID mid-run. It also
   reads the aggregate `/proc/stat` CPU counters.
4. `model_paths()` uses the running preview's command line and working
   directory to find graph/weight files. `sha256_file()` hashes them once
   before warm-up; no model is loaded into the collector. Metadata records
   host/commit, requested mode, scene, power/cooling, file hashes and protocol.
5. After the warm-up, the collector samples at one-second target spacing.
   `one_sample()` joins the latest HTTP state with differences between two
   process/host CPU counter readings, current RSS, thermal zone 0 and raw
   `vcgencmd get_throttled` output. CPU ticks divided by elapsed monotonic
   seconds become percent. Because reads occur one after another, these are
   approximate contemporaneous observations, not one atomic sensor snapshot.
6. Each metrics-only sample is appended to ignored `samples.jsonl`.
   `summarize()` calculates medians/p95s for sampled metrics, counts distinct
   detector sequences for compute time and first-polled box age, calculates
   cumulative skipped-frame growth, and compares first/last minute
   temperatures. `summary.json` is a compact analysis input; raw traces
   remain uncommitted. `metadata.json` becomes `complete` only after the
   summary is written.

Important distinctions: `capture_fps` and `analysis_fps` are recent app rates,
not poll frequencies. `detector_rate_hz` measures completed detector updates;
the 2 Hz target is a scheduling limit, not a guaranteed achieved rate.
`imu_rate_hz` is a host read rate, not the IMU chip's internal data rate.
`analysis_ms_latest` and `detector_compute_ms_latest` describe worker compute,
not full camera-to-display latency. `box_source_age_ms` measures from host
receipt. `preview_cpu_pct_one_core` and `ffmpeg_cpu_pct_one_core` can both be
nonzero and add beyond 100%, because 100% means **one** logical core in each
field. `system_cpu_busy_pct_all_cores` uses a different denominator. The
collector does not measure electrical power draw.

The tests in [`test_ap_baseline.py`](../../tests/unit/test_ap_baseline.py) use
fake `/proc` files to check field positions, PID identity, CPU math, mode
rejection and distinct detector-result summary. They cannot prove the Pi's
real CPU, cooling or negotiated USB mode; only the Pi run can do that.
