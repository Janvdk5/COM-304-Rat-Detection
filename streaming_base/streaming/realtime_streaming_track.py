"""
realtime_streaming_track.py
---------------------------
Human-tracking-style real-time consumer for the rat detection project.

Compared to `realtime_streaming_task3.py`:
  * No ad-hoc EMA pipe-ROI logic. Detection -> GTrack -> PresenceZone2D
    handles "object in pipe" with proper Kalman state and hysteresis.
  * Single-radar. (Human tracking's version does dual-radar fusion;
    we don't have a second radar wired here.)
  * Expects a `bf_output` shaped (num_phi, num_range), normalized to [0, 1].
    The producer's *tracking* pipeline uses motion-dense beamforming (Doppler-style
    max-over-velocity collapse + dense `beamform_2d` + optional post-CFAR), same idea
    as legacy `--doppler`.

How to invoke
-------------
From the existing realtime entry point (`src/realtime.py`), import this
module instead of `realtime_streaming_task3` and call:
    realtime_streaming_track.main(cfg_radar, cfg_cfar)

Set `cfg_cfar['pipeline'] = 'tracking'` on the producer side to get the
human-tracking-style RD-domain CFAR + sparse beamform feeding this consumer.
"""

import os
import time
import numpy as np
from multiprocessing import Process, Queue, Event
from datetime import datetime

from streaming_base.streaming.prod_dca import producer_real_time_1843
from streaming_base.gtrack.config import GTrackConfig2D, PresenceZone2D, Detection
from streaming_base.gtrack.module import GTrackModule2D
from streaming_base.processing.processing import make_detection_list


# ---------------------------------------------------------------------------
# Rat-tuned GTrack configuration
#
# Tuned defaults are *starting points*; expect to iterate against recordings.
# See `human_tracking_porting_plan.md` for the reasoning behind each value.
# ---------------------------------------------------------------------------
def build_rat_gtrack_config(dt: float = 0.1):
    """
    Build a GTrackConfig2D pre-tuned for the rat-in-pipe scenario.

    Parameters
    ----------
    dt : float
        Producer frame period in seconds (1 / FPS). The Kalman F matrix uses
        this directly; a wrong dt biases predictions and shrinks the gate.
        Default 0.1 corresponds to 10 FPS.

    Returns
    -------
    GTrackConfig2D
    """
    return GTrackConfig2D(
        # ---- Capacity ----
        # Cap points fed to GTrack so CFAR speckle does not flood DBSCAN.
        max_points=120,
        # Single rat in pipe: one Kalman slot avoids 4 parallel ghosts on clutter.
        # Raise to 2 only if you need a brief handoff when one track splits.
        max_tracks=1,

        # ---- Kinematics ----
        dt=dt,
        # Slightly lower Q than before: less state diffusion into random clutter.
        process_noise=2.5,

        # ---- Measurement noise (range in m^2, az in rad^2) ----
        meas_noise_range=0.01,  # ~10 cm 1-sigma in range
        meas_noise_az=0.01,     # ~5.7 deg 1-sigma in azimuth

        # ---- Gating ----
        # Tighter than 12: fewer wrong associations between nearby clutter blobs.
        gating_threshold=9.0,

        # ---- Allocation (DBSCAN normalization gates) ----
        # Slightly tighter normalized gates: noise pixels less often merge into a "cluster".
        alloc_range_gate=0.28,
        alloc_az_gate=0.18,
        alloc_vel_gate=1.0,
        # Need several pixels in (range, az, doppler)-normalized space to start a track.
        min_cluster_points=4,
        # Summed normalized SNR for the cluster; cuts weak random shapes.
        alloc_snr_threshold=0.65,

        # ---- Per-point threshold ----
        # Fewer weak pixels -> fewer phantom seeds (raise if the real rat disappears).
        min_snr_threshold=0.14,

        # ---- Initial covariance ----
        init_state_cov=0.5,

        # ---- Lifecycle counters ----
        det_to_active_count=4,  # more consistent hits before ACTIVE
        det_to_free_count=4,    # drop tentative ghosts quickly
        act_to_free_count=12,   # drop lost ACTIVE faster so one slot frees for the rat

        # ---- Presence zone (the pipe ROI) ----
        # GTrack uses sph2cart_2d(r, az) = (r*cos(az), r*sin(az)). With phi in
        # [0, pi], az = pi/2 is "straight ahead", so +y is forward.
        # Adjust these to match your physical setup. Units are meters.
        presence_zones=[
            PresenceZone2D(
                x_min=-0.60, x_max=0.60,    # +/- 60 cm laterally
                y_min=1.00,  y_max=1.40,    # 1.0-1.4 m forward (pipe at ~1.2 m, 40 cm deep)
            ),
        ],
        pres_on_count=3,        # consecutive frames with ACTIVE in zone before presence on
        pres_off_count=5,       # consecutive frames without before presence off
    )


# ---------------------------------------------------------------------------
# Visualization process body (GUI imports happen lazily so the producer
# subprocess never accidentally imports matplotlib/Qt/Panda3D).
# ---------------------------------------------------------------------------
def run_visualization(q1, cfg_radar, cfg_gtrack, stop_event):
    import warnings
    warnings.simplefilter("ignore", UserWarning)

    from direct.showbase.ShowBase import ShowBase
    from direct.task import Task

    import matplotlib
    matplotlib.use('Qt5Agg')
    matplotlib.rcParams['toolbar'] = 'None'
    import matplotlib.pyplot as plt
    plt.style.use('seaborn-v0_8-dark')

    from panda3d.core import loadPrcFileData
    loadPrcFileData('', 'window-type none')
    loadPrcFileData('', 'audio-library-name null')

    from PyQt5 import QtWidgets

    from streaming_base.visualization.visualization import (
        configure_ax_bf,
        configure_ax_gtrack,
        update_ax_gtrack,
    )

    class MyApp(ShowBase):
        def __init__(self, queue_1, cfg_radar, cfg_gtrack, stop_event):
            ShowBase.__init__(self)

            self.q1 = queue_1
            self.cfg_radar = cfg_radar
            self.cfg_gtrack = cfg_gtrack
            self.stop_event = stop_event
            self.is_closing = False

            self.phi = cfg_radar["phi"]
            self.r_idxs = cfg_radar["range_idx"]
            self.range_res = cfg_radar["range_res"]  # meters per range bin
            self.r_meters = self.r_idxs * self.range_res

            # ----- Polar beamform plot (existing visualization) -----
            self.fig_bf = plt.figure(figsize=(6, 6))
            self.ax_bf = self.fig_bf.add_subplot(111, projection='polar')
            self.im = configure_ax_bf(self.ax_bf, self.phi, self.r_idxs, 0, 1.0)

            # Show range ticks in meters on the polar plot.
            num_ticks = 7
            radial_bins = np.linspace(self.r_idxs.min(), self.r_idxs.max(), num_ticks)
            radial_labels = [f"{rb * self.range_res:.2f} m" for rb in radial_bins]
            self.ax_bf.set_rticks(radial_bins)
            self.ax_bf.set_yticklabels(radial_labels)
            self.ax_bf.set_title("Beamformed magnitude (polar)")

            # ----- Cartesian GTrack plot -----
            # Width / depth set by farthest range so all tracks fit on screen.
            far_m = float(self.r_meters.max())
            self.fig_gt = plt.figure(figsize=(7, 6), constrained_layout=True)
            self.ax_gt = self.fig_gt.add_subplot(111)
            configure_ax_gtrack(self.ax_gt, width=far_m, rgd=far_m)

            # Pipe outline drawn on the Cartesian plot for visual reference.
            for zone in cfg_gtrack.presence_zones:
                self.ax_gt.add_patch(
                    plt.Rectangle(
                        (zone.x_min, zone.y_min),
                        zone.x_max - zone.x_min,
                        zone.y_max - zone.y_min,
                        fill=False,
                        edgecolor='cyan',
                        linewidth=2,
                        linestyle='--',
                        label='Pipe ROI',
                    )
                )

            # "OBJECT IN PIPE" banner toggled by tracker.presence_flag.
            self._presence_text = self.ax_gt.text(
                0.0, far_m * 1.02,
                '',
                ha='center', va='bottom',
                color='red', fontsize=14, fontweight='bold',
                zorder=10,
            )

            # FPS counter + 1-Hz diagnostic accumulators
            self.frame_counter = 0
            self.fps = 0.0
            self.last_fps_time = time.time()
            self._diag_dets_sum = 0
            self._diag_bf_max_sum = 0.0
            self._fps_text = self.ax_gt.text(
                0.01, 0.98,
                "",
                transform=self.ax_gt.transAxes,
                fontsize=10, color='blue',
                va='top',
            )

            # Track-rendering scratch state (passed in/out of update_ax_gtrack).
            self._track_artists = []

            # GTrack module
            self.tracker = GTrackModule2D(cfg_gtrack)

            # Close handlers
            self.fig_bf.canvas.mpl_connect('close_event', self._on_close)
            self.fig_gt.canvas.mpl_connect('close_event', self._on_close)
            self.accept('escape', self._request_shutdown)

            self.taskMgr.add(self._update_task, "trackUpdateTask")

        # ---- Shutdown plumbing ----------------------------------------------
        def _request_shutdown(self, event=None):
            if self.is_closing:
                return
            self.is_closing = True
            print("Visualization closing, stopping producer...")
            self.stop_event.set()
            try:
                plt.close(self.fig_bf)
                plt.close(self.fig_gt)
            except Exception:
                pass
            self.destroy()

        def _on_close(self, event):
            self._request_shutdown()

        # ---- Main per-frame update ------------------------------------------
        def _update_task(self, task):
            if self.stop_event.is_set():
                return Task.done

            # Drain the queue, keep the latest 'bev' message only.
            latest_bf = None
            try:
                while not self.q1.empty():
                    msg = self.q1.get_nowait()
                    if msg[0] == 'bev':
                        latest_bf = msg[1]
            except Exception:
                pass

            if latest_bf is None:
                return Task.cont

            # bf_output may be complex (from sparse beamform) or already
            # magnitude. Take |.| to be safe; the producer normalizes to [0, 1].
            bf_mag = np.abs(latest_bf)
            mx = float(bf_mag.max())
            bf_norm = bf_mag / mx if mx > 0 else bf_mag

            # ---- Update polar heatmap ----
            self.im.set_array(bf_norm.ravel())

            # ---- Build Detection list (range in METERS so PresenceZone2D
            #      and track state come out in meters) ----
            detections = make_detection_list(
                bf_norm,
                phi=self.phi,
                r_idxs=self.r_meters,
                min_snr_threshold=self.cfg_gtrack.min_snr_threshold,
                max_points=self.cfg_gtrack.max_points,
            )

            # ---- Step the tracker ----
            out = self.tracker.step(detections)
            tracks = out['tracks']
            presence = out['presence']

            # ---- Update Cartesian track view ----
            update_ax_gtrack(self.ax_gt, tracks, self._track_artists)

            # ---- Presence banner ----
            self._presence_text.set_text('OBJECT IN PIPE' if presence else '')

            # ---- FPS + per-second console diagnostic ----
            self.frame_counter += 1
            self._diag_dets_sum += len(detections)
            self._diag_bf_max_sum += float(bf_mag.max())
            now = time.time()
            if now - self.last_fps_time >= 1.0:
                window = now - self.last_fps_time
                self.fps = self.frame_counter / window
                avg_dets = self._diag_dets_sum / max(1, self.frame_counter)
                avg_bf_max = self._diag_bf_max_sum / max(1, self.frame_counter)
                n_active = sum(1 for t in tracks if t['status'] == 'ACTIVE')
                # Console line so the user can see all stages at a glance.
                print(
                    f"[track] {self.fps:.1f} fps | dets/frame avg={avg_dets:.1f} | "
                    f"bf_max avg={avg_bf_max:.3g} | tracks={len(tracks)} "
                    f"(active={n_active}) | presence={presence}"
                )
                self.last_fps_time = now
                self.frame_counter = 0
                self._diag_dets_sum = 0
                self._diag_bf_max_sum = 0.0
            self._fps_text.set_text(
                f"FPS: {self.fps:.1f} | tracks: {len(tracks)} | dets: {len(detections)} | "
                f"bf_max: {float(bf_mag.max()):.2g} | presence: {presence}"
            )

            # ---- Render ----
            self.fig_bf.canvas.draw_idle()
            self.fig_gt.canvas.draw_idle()
            QtWidgets.QApplication.processEvents()
            plt.pause(0.001)

            return Task.cont

    app = MyApp(q1, cfg_radar, cfg_gtrack, stop_event)
    app.run()


# ---------------------------------------------------------------------------
# Entry point: launches producer in a child process, runs GUI in main.
# ---------------------------------------------------------------------------
def main(cfg_radar, cfg_cfar, cfg_gtrack=None):
    """
    Main function for the GTrack-driven realtime pipeline.

    Set cfg_cfar['pipeline'] = 'tracking' to run the human-tracking-style
    pre-beamform CFAR + sparse beamform pipeline upstream of this consumer.
    """
    if cfg_gtrack is None:
        dt = cfg_radar.get("dt", 0.1)
        cfg_gtrack = build_rat_gtrack_config(dt=dt)

    q_main_1 = Queue(maxsize=1)
    stop_event = Event()

    producer = Process(
        target=producer_real_time_1843,
        args=(q_main_1, cfg_radar, cfg_cfar, 4096, 4098,
              "192.168.33.30", "192.168.33.180", stop_event),
        daemon=True,
    )
    producer.start()
    print("Producer started, launching GTrack visualization in main process...")

    try:
        run_visualization(q_main_1, cfg_radar, cfg_gtrack, stop_event)
    except KeyboardInterrupt:
        print("Main interrupted, stopping producer...")
        stop_event.set()
    finally:
        stop_event.set()
        producer.join(timeout=5)
        if producer.is_alive():
            print("Producer did not stop in time, forcing termination...")
            producer.terminate()
            producer.join()
        print("Shutdown complete.")
