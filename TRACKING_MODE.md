# Tracking Mode — quick reference

This is the human-tracking-style pipeline ported into the rat project. It replaces single-argmax detection with a proper Kalman tracker.

## How to run it

From the rat project root, with the radar/DCA1000 connected:

```bash
python src/realtime.py --track
```

Useful combinations:

```bash
# Tracking mode while also saving raw ADC data for offline analysis
python src/realtime.py --track --save_raw_dt --exp_name rat_run_01

# Run mmWave Studio config from Python first, then tracking
python src/realtime.py --config --track
```

The `--doppler` and `--cfar` flags are ignored in tracking mode; the tracking pipeline always does its own Doppler FFT and CFAR (in the right place — on the range-Doppler map, before beamforming).

Two figures will open:

- **Polar heatmap** — beamformed magnitude in (angle, range), same as the legacy view.
- **Cartesian GTrack view** — tracks rendered as circles with velocity arrows, colored by ID. The cyan dashed rectangle is the pipe `PresenceZone2D`. When a track sits inside the rectangle long enough, an `OBJECT IN PIPE` banner appears above the plot.

Close either figure to shut everything down cleanly.

## What changed under the hood

Three pieces:

1. **Producer (`streaming_base/streaming/prod_dca.py`)** — added an opt-in `cfg_cfar['pipeline']` mode. When set to `'tracking'`, the producer runs: range FFT → background subtraction → Doppler FFT → zero-velocity notch → CFAR on the (Doppler, range) power map → sparse beamform. The legacy code path is untouched and remains the default.

2. **Processing helpers (`streaming_base/processing/processing.py`)** — added `cfar_ca_2d_mask` (boolean-mask variant of existing CFAR), `build_rd_power_map`, `notch_zero_velocity`, `beamform_2d_s` (sparse beamformer), and `make_detection_list` (convert a beamformed map into a list of `Detection` objects for GTrack).

3. **Consumer (`streaming_base/streaming/realtime_streaming_track.py`)** — new file. Receives `bf_output`, builds a `Detection` list, calls `GTrackModule2D.step()`, renders tracks on a Cartesian axis next to the polar heatmap, and lights up the `OBJECT IN PIPE` banner when the tracker's presence flag is set.

GTrack itself is unchanged; it was already in your repo at `streaming_base/gtrack/`, byte-identical to the human tracking version.

## Parameters worth tuning first

All in `build_rat_gtrack_config(...)` inside `realtime_streaming_track.py`:

- `dt` — must match your actual FPS. The default 0.1 assumes 10 FPS. If you're closer to 15 FPS, set `dt=0.067`. Wrong `dt` puts the Kalman prediction in the wrong place and shrinks the gate.
- `min_snr_threshold` (default `0.25`) — pixels in the normalized `bf_output` below this don't become detections. Lower it if the tracker doesn't pick up the tinfoil rat; raise it if you get phantom tracks.
- `process_noise` (default `4.0`) — how much the Kalman believes the rat can deviate from constant velocity. Raise if the rat keeps falling outside the gate during sharp turns.
- `act_to_free_count` (default `25`) — how many frames a track can coast through a signal dropout (the tangential dead zone) before being killed. Increase if good tracks die during tangential motion.
- `presence_zones` — set `x_min/x_max/y_min/y_max` (in meters) to match your physical pipe. Coordinates use `+y = forward`, `+x = right`, with the radar at the origin.

`cfg_cfar` parameters in `src/realtime.py` that affect the tracking pipeline:

- `num_train_r / num_train_d / num_guard_r / num_guard_d` — CFAR window sizes on the range-Doppler map. The defaults (10/10/4/2) are sane starting points.
- `threshold_scale` (default `1e-3`) — CFAR false alarm rate. Lower = fewer (but more confident) detections. If you're not seeing the rat at all, raise to `1e-2`; if you're getting noise floods, lower to `1e-4`.
- `doppler_notch_bins` (default `2`) — ±N Doppler bins around DC to suppress (static clutter / the pipe). Set to `0` to disable the notch — useful for diagnostics or for tangential-motion-heavy scenes where the notch hurts more than helps.

## Troubleshooting (reading the diagnostics)

When you run with `--track` you should see two streams of lines in the console:

```
[prod]  pipeline=tracking  bg_sub=True  doppler_notch_bins=1  threshold_scale=0.01  ...
[prod]  N fps | CFAR cells/frame avg=X.X | bf_max avg (pre-norm)=X.XXX
[track] N fps | dets/frame avg=X.X | bf_max avg=X.XXX | tracks=N (active=N) | presence=False
```

The `[prod]` lines come from the producer (pre-beamform stage); the `[track]` lines come from the consumer (post-beamform / tracker stage). Reading them in order tells you where in the chain detections drop off.

**If `CFAR cells/frame avg` is 0:** CFAR isn't firing. Either the target's return is below the CFAR threshold, or the zero-velocity notch is killing it. Try, in order:
1. Raise `threshold_scale` in `src/realtime.py` from `1e-2` to `5e-2`.
2. Set `doppler_notch_bins` to `0` (disable the notch entirely) — useful sanity check.
3. Look at the polar heatmap: is the moving target visible there at all? If not, the issue is upstream of CFAR (background subtraction, antenna pattern, target distance).

**If `CFAR cells/frame avg > 0` but `dets/frame avg` is 0:** CFAR fires, but no beamformed pixel exceeds `min_snr_threshold`. The signal is reaching the consumer but normalizes to a value below `0.10`. This usually means the sparse-beamform output has very few cells lit, so per-frame max-normalization makes the threshold proportionally hard to cross — or CFAR is firing only on noise. Try:
1. Lower `min_snr_threshold` in `build_rat_gtrack_config` (in `realtime_streaming_track.py`) from `0.10` to `0.05`.
2. Check `bf_max avg` in the `[track]` line. If it's very low (< 0.1), the producer is sending mostly empty maps.

**If `dets/frame avg` is moderate (10-100) but `tracks` is 0:** Detections exist but DBSCAN isn't forming clusters big enough to spawn a new track. Try:
1. Lower `min_cluster_points` from `2` to `1` (will accept singleton clusters).
2. Lower `alloc_snr_threshold` from `0.2` to `0.1`.
3. Widen `alloc_range_gate` from `0.40` to `0.80` and `alloc_az_gate` from `0.30` to `0.50`.

**If `tracks > 0` but `active=0` permanently:** Tracks are being created (status `DETECTION`) but never promoted to `ACTIVE`. They need `det_to_active_count` consecutive hits. Try lowering `det_to_active_count` from `3` to `1`.

**If `presence` stays False but a track is sitting inside the pipe area:** The `PresenceZone2D` doesn't cover the track's position. Print the track position from the `[track]` line by editing the diagnostic to include `tracks[0]['pos']`, or just widen `presence_zones` in `build_rat_gtrack_config` until presence flips True.

**Sanity test without the radar:** A windup toy is a small, slow, low-RCS target. If `--track` fails on it but you want to validate the wiring before the rat is ready, walk in front of the radar instead — a moving human gives a much stronger return and should appear as a single high-confidence track within a couple of seconds.

## Comparing legacy vs. tracking on the same recording

If you've saved raw data with `--save_raw_dt`, the file is in `data/<exp_name>_Raw_0_<timestamp>.bin`. You can't replay it through this realtime path directly (the producer reads from the DCA1000 hardware), but it's exactly what you'd point an offline replay script at to A/B the two pipelines.

For live A/B, just run with and without `--track` in two sessions — `--track` keeps the legacy code paths completely intact, so flipping the flag doesn't risk breaking the existing pipeline.
