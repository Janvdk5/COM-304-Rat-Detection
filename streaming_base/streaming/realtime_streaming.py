# Info:
#
# ------------------------------------

# top-level: only safe, non-GUI imports
import time
import joblib
import numpy as np
from multiprocessing import Process, Queue, Event
import os
import cv2
from datetime import datetime
import json
from collections import deque

# import the producer (should not import GUI libs)
from streaming_base.streaming.prod_dca import producer_real_time_1843


# -------------------------------
# NOTE: Jan - new detector attempt
# -------------------------------
class JerryClassifier:
    """
    Simple heuristic classifier to detect presence of "Jerry" the rat in the pipe ROI.

    Parameters:
    - range_bins: list or array of range bin indices corresponding to the pipe ROI
    - sensitivity: multiplier on noise floor to set detection threshold (lower = more sensitive)
    - min_active_bins: minimum number of bins in the ROI that must exceed the threshold for a frame to be considered "active"
    - frame_window: number of recent frames to consider in the moving window for detection
    - num_frames_thresh: fraction of frames in the window that must be active to trigger detection
        - NB: for wood + foam, set to 0.15

    Funcs:
    - init: initializes the classifier with the specified parameters and an empty deque for recent frame activity
    - updateDetection(bf_output): takes the latest beamforming output (1D array of length num_bins), applies the detection logic, and returns:
        - jerry_detected: boolean indicating if Jerry is detected in the current window
        - detection_rate: fraction of frames in the window that are active (for logging/analysis)
        - active_bins: number of bins in the current frame's ROI that exceed the threshold (for logging/analysis)
    """
    def __init__(self, range_bins, sensitivity=1.0, min_active_bins=1, frame_window=10, num_frames_thresh=0.35):
        self.range_bins = range_bins
        self.sensitivity = sensitivity
        self.min_active_bins = min_active_bins
        self.active_frames = deque(maxlen=frame_window) #use queue so we can easy keep moving window
        self.num_frames_thresh = num_frames_thresh
                
    def updateDetection(self, bf_output):
        active_bins = 0
        jerry_detected = False

        # setup noise baseline#
        outside_roi = np.delete(np.abs(bf_output), self.range_bins)
        nonzero_vals = outside_roi[outside_roi > 0]
        
        # get of zeroing out issues
        if len(nonzero_vals) > 0:
            noise_floor = float(np.mean(nonzero_vals))
        else: 
            noise_floor = 1.0

        #noise_floor = np.median(np.abs(bf_output)) 
        bin_threshold = self.sensitivity * noise_floor

        # each bin above thresh?
        roi = np.abs(bf_output[self.range_bins])
        active_bins = int(np.sum(roi > bin_threshold))
        
        # Is frame good?
        if active_bins >= self.min_active_bins:
            active_frame_flag = 1
        else:
            active_frame_flag = 0

        # enough prev frames agree?
        self.active_frames.append(active_frame_flag)
        detection_rate = float(np.mean(self.active_frames))

        if detection_rate >= self.num_frames_thresh:
            jerry_detected = True
        
        print(f"noise={noise_floor:.4f}  threshold={bin_threshold:.4f}  ")
        print(f"roi_max={roi.max():.4f}  active_bins={active_bins}  ")
        print(f"detection_rate={detection_rate:.2f}")


        return jerry_detected, detection_rate, active_bins



def run_visualization(q1, cfg_radar, cfg_cfar, stop_event):
    """
    Runs the real-time visualization in the main process. 

    Params:
    - q1: multiprocessing.Queue for receiving data from the producer
    - cfg_radar: radar configuration dictionary
    - cfg_cfar: CFAR configuration dictionary
    - stop_event: multiprocessing.Event to signal stopping of the visualization
    """
    import warnings
    warnings.simplefilter("ignore", UserWarning)

    from scipy.interpolate import RegularGridInterpolator
    from direct.showbase.ShowBase import ShowBase
    from direct.task import Task

    import matplotlib
    matplotlib.use('Qt5Agg')
    matplotlib.rcParams['toolbar'] = 'None'         #  NOTE : DISABLE TOOL BAR (saving fig crashes run-time sinc frame gets refreshed rapidly)

    from matplotlib.animation import FFMpegWriter   #  NOTE : TO RECORD VISUALISATION

    import matplotlib.pyplot as plt
    plt.style.use('seaborn-v0_8-dark')

    from panda3d.core import loadPrcFileData
    loadPrcFileData('', 'window-type none')   # no native GL window
    loadPrcFileData('', 'audio-library-name null')

    from PyQt5 import QtWidgets

    # GUI-related helpers (move these imports here too)
    from streaming_base.visualization.visualization import (
        configure_ax_bf,
    )
    from streaming_base.utils.utils import cart2pol

    # PIPE DETECTION CONFIG
    # The "pipe" is modeled as a rectangular ROI lying perpendicular to radar
    DETECTION_THRESHOLD  = 0.35     # the pipe ROI. Range [0, 1]; lower => more sensitive.
    DETECTION_EMA_ALPHA  = 0.5      # Temporal smoothing for the in-ROI amplitude (0 = no smoothing, 1 = frozen).
    MARKER_MIN_AMP       = 0.25     # Minimum absolute peak height (normalized) required before drawing a per-object marker on top of the heatmap.       

    class MyApp(ShowBase):
        """
        The main application class for the real-time radar visualization. Inherits from Panda3D's ShowBase.

        Parameters:
        - queue_1: multiprocessing.Queue for receiving data from the producer
        - cfg_radar: radar configuration dictionary (contains parameters like phi, range_idx, etc.)
        - stop_event: multiprocessing.Event to signal stopping of the visualization
        """
        def __init__(self, queue_1, cfg_radar, stop_event):
            ShowBase.__init__(self)
            self.q1 = queue_1
            self.latest_msg = {}
            self.msg_count = set()

            self.phi = cfg_radar["phi"]
            self.r_idxs = cfg_radar["range_idx"]

            # range the detector bins so we focus on pipe area
            n_range_bins = len(self.r_idxs)
            pipe_range_bins = np.arange(15, min(40, n_range_bins))
            self.detector = JerryClassifier(range_bins=pipe_range_bins)

            self.fig = plt.figure(figsize=(6, 6))
            self.ax = self.fig.add_subplot(111, projection='polar')
            self.ax.set_ylabel('')
            self.im = configure_ax_bf(self.ax, self.phi, self.r_idxs, 0, 0.1)

            # stop even nicely with ctrl+c or window close (instead of hard kill)
            self.stop_event = stop_event
            self.is_closing = False

            self.fig.canvas.mpl_connect('close_event', self.on_close)
            self.accept('escape', self.request_shutdown)   # optional: press Esc to stop cleanly

            timestamp = datetime.today().strftime("%m-%d-%Y_%H-%M-%S")


            # setup new window for detector output
            self.det_fig, self.det_ax = plt.subplots()
            self.det_text = self.det_ax.text(0.5, 0.5, "",
                                             ha='center', va='center', fontsize=20)
            
            self.last_frame_time = time.time()
            self.frame_counter = 0
            self.fps = 0
            self.last_fps_time = time.time()

            self.taskMgr.add(self.updateTask, "updateTask")

            self.x = np.arange(-cfg_radar["width"], cfg_radar["width"], 1)
            self.y = self.r_idxs
            self.X, self.Y = np.meshgrid(self.x, self.y, indexing='xy')

            self.cart2pol = cart2pol(self.X.ravel(), self.Y.ravel())

            # Initialize pipe mask (ROI mask for detection region) - all ones by default
            self._pipe_mask = np.ones(self.X.shape, dtype=bool)

            # Initialize EMA for ROI detection smoothing
            self._roi_ema = 0.0

            self.last_artists = []
            num_ticks = 6

            # Visual zoom: clip the polar plot to 0 
            VIEW_RANGE_M = 1.2      # so the rat is easier to make out. 
            max_bin_visible = min(VIEW_RANGE_M / cfg_radar['range_res'], float(self.r_idxs.max()))

            # Radial ticks across the visible (clipped) range only
            radial_bins = np.linspace(0.0, max_bin_visible, num_ticks)
            radial_labels = [f"{rb * cfg_radar['range_res']:.2f}" for rb in radial_bins]

            # Apply ticks AND hard r-axis limit
            self.ax.set_rticks(radial_bins)
            self.ax.set_yticklabels(radial_labels)
            self.ax.set_ylim(0.0, max_bin_visible)


        # HELPERS -------------------------------------------------------------------------

        def request_shutdown(self, event=None):
            """
            Handles ongoing visualisation recording tasks termination.
            """
            if self.is_closing:
                return

            self.is_closing = True
            print("Visualization closing, stopping producer...")
            self.stop_event.set()

            try:
                import matplotlib.pyplot as plt
                plt.ion()                     # NOTE : turns on interactive mode (create/show/update it as the program runs )
                plt.close(self.fig)
            except Exception:
                pass

            # Shut down Panda3D so app.run() can return
            self.destroy()


        def on_close(self, event):
            self.request_shutdown()


        def update_log(self, confidence):
            """
            Updates the log file with the latest detection confidence. 
            Log files found in src/logs/jerry_log.jsonl
            """
            event = {
                "time": datetime.now().isoformat(),
                "confidence": float(confidence),
                "station": "station_1"
            }

            # Use relative path from current file location
            log_dir = os.path.join(os.path.dirname(__file__), "../../src/logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "jerry_log.jsonl")

            with open(log_file, "a") as f:
                f.write(json.dumps(event) + "\n")


        def update_signal_log(self, detection_rate, n_active_bins):
            """
            Updates the signal log file with the latest detection metrics.
            Log files found in src/logs/signal_log.jsonl
            """
            event = {
                "time"           : datetime.now().isoformat(),
                "detection_rate" : round(detection_rate, 3),
                "active_bins"    : n_active_bins,
            }
            log_dir  = os.path.join(os.path.dirname(__file__), "../../src/logs")
            os.makedirs(log_dir, exist_ok=True)
            with open(os.path.join(log_dir, "signal_log.jsonl"), "a") as f:
                f.write(json.dumps(event) + "\n")
            



        def updateTask(self, task):
            """
            Updates visualiser to newly acquired frame.
            """

            if self.stop_event.is_set():
                return Task.done

            # NOTE: single queue, so don't enumerate tuples — just use it
            try:
                q = self.q1
                while not q.empty():
                    msg = q.get_nowait()
                    if msg[0] == 'bev':
                        self.latest_msg[0] = msg[1]
                        self.msg_count.add(0)
            except Exception:
                pass

            if self.msg_count == {0}:
                bf_1 = self.latest_msg[0]

                self.x1 = getattr(self, "x1", 0.0)
                self.y1 = getattr(self, "y1", 0.0)

                phi1 = np.arctan2((self.Y - self.y1).ravel(), (self.X - self.x1).ravel())
                r1 = np.hypot(self.X.ravel() - self.x1, self.Y.ravel() - self.y1)
                cart2pol1 = np.column_stack((phi1, r1))

                interp1 = RegularGridInterpolator(
                    (self.phi, self.r_idxs),
                    bf_1,
                    method='linear', bounds_error=False, fill_value=0
                )
                Z1 = interp1(cart2pol1).reshape(self.X.shape)
                Z_cart = Z1

                # -------------------------------------------------------
                # PIPE DETECTION
                # -------------------------------------------------------
                Z_cart_mag = np.abs(Z_cart)
                _zmax = Z_cart_mag.max()
                if _zmax > 0:
                    Z_cart_norm = Z_cart_mag / _zmax
                else:
                    Z_cart_norm = Z_cart_mag

                roi_vals = Z_cart_norm[self._pipe_mask]
                if roi_vals.size > 0:
                    roi_max = float(roi_vals.max())
                else:
                    roi_max = 0.0

                # EMA smoothing
                self._roi_ema = (
                    DETECTION_EMA_ALPHA * self._roi_ema
                    + (1.0 - DETECTION_EMA_ALPHA) * roi_max
                )

                detected = self._roi_ema > DETECTION_THRESHOLD
                peak_phi = None
                peak_r   = None
                if detected and roi_max > MARKER_MIN_AMP:
                    # Locate the brightest pixel inside the ROI.
                    masked = Z_cart_norm * self._pipe_mask
                    flat_idx = int(np.argmax(masked))
                    iy, ix = np.unravel_index(flat_idx, Z_cart_norm.shape)
                    x_peak = float(self.X[iy, ix])
                    y_peak = float(self.Y[iy, ix])
                    peak_phi = np.arctan2(x_peak, y_peak)
                    peak_r   = np.hypot(x_peak, y_peak)

                interp_cart2pol = RegularGridInterpolator(
                    (self.y, self.x),
                    Z_cart,
                    method='linear',
                    bounds_error=False,
                    fill_value=0
                )

                PHI, R = np.meshgrid(self.phi, self.r_idxs, indexing='ij')
                pts_back = np.column_stack(((R * np.sin(PHI)).ravel(), (R * np.cos(PHI)).ravel()))
                Z_polar = interp_cart2pol(pts_back).reshape(PHI.shape)
                Z_polar = np.flip(Z_polar, axis=0)

                to_plot = np.abs(Z_polar)
                mx = np.max(to_plot) if np.max(to_plot) != 0 else 1.0
                to_plot /= mx 

                # ------------------------------------
                # NOTE: Jan - jerry detector classifier
                # ------------------------------------
                bf_output_1d = np.abs(bf_1).max(axis=0) # need 1d
                
                rat_detected, detection_rate, active_bins = self.detector.updateDetection(bf_output_1d)

                # update bf log:               

                if rat_detected:
                    colour = "red"
                    label = f"Jerry Detected ({detection_rate:.0%} of frames)!"

                    # update logs for gui stream
                    self.update_log(detection_rate)
                    self.update_signal_log(detection_rate, active_bins)

                else:
                    label = f"No Jerry ({detection_rate:.0%} of frames)"
                    colour = "green"

                # new window
                self.det_text.set_text(label)
                self.det_ax.set_facecolor(colour)
                self.det_fig.canvas.draw_idle()

                self.im.set_array(to_plot.ravel())
                
                self.fig.canvas.draw_idle() 
                QtWidgets.QApplication.processEvents()
 
                self.msg_count.clear()
                plt.pause(0.001)

            return Task.cont        

    # instantiate and run
    app = MyApp(q1, cfg_radar, stop_event)
    app.run()



# -------------------------
# main guard: run producer in child, GUI in main
# -------------------------
def main(cfg_radar, cfg_cfar):
    q_main_1 = Queue(maxsize=1)
    stop_event = Event()

    # launch the visualization in the main process, and handle graceful shutdown on Ctrl+C or window close
    producer = Process(
        target=producer_real_time_1843,
        args=(q_main_1, cfg_radar, cfg_cfar, 4096, 4098, "192.168.33.30", "192.168.33.180", stop_event),
        daemon=True
    )
    producer.start()
    print("Producer started, launching visualization in main process...")

    try:
        run_visualization(q_main_1, cfg_radar, cfg_cfar, stop_event)

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
