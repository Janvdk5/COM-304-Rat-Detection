# top-level: only safe, non-GUI imports
import time
import joblib
import numpy as np
from multiprocessing import Process, Queue, Event
import os
from datetime import datetime

# import the producer (should not import GUI libs)
from streaming_base.streaming.prod_dca import producer_real_time_1843

# -------------------------
# Visualization code is moved into a function so it is only imported/run
# in the main process (no GUI imports at module top-level)
# -------------------------
def run_visualization(q1, cfg_radar, cfg_cfar, stop_event):
    # GUI imports done here (main process only)
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


    class MyApp(ShowBase):
        def __init__(self, queue_1, cfg_radar, stop_event):
            ShowBase.__init__(self)
            self.q1 = queue_1
            self.latest_msg = {}
            self.msg_count = set()

            self.phi = cfg_radar["phi"]
            self.r_idxs = cfg_radar["range_idx"]

            self.fig = plt.figure(figsize=(6, 6))
            self.ax = self.fig.add_subplot(111, projection='polar')
            self.ax.set_ylabel('')
            self.im = configure_ax_bf(self.ax, self.phi, self.r_idxs, 0, 0.3)  


            #   ----------------------------------------------------------------
            #
            #   NOTE : (kerim -- 4/21/2026)
            #   
            #       -- added these to handle stop event nicely in visualisation.
            #

            self.stop_event = stop_event
            self.is_closing = False

            self.fig.canvas.mpl_connect('close_event', self.on_close)
            self.accept('escape', self.request_shutdown)   # optional: press Esc to stop cleanly

            self.record_video = True        # NOTE : True to save video, False otherwise
            self.video_writer = None        # NOTE : Video "Recorder" Instance

            timestamp = datetime.today().strftime("%m-%d-%Y_%H-%M-%S")


            if self.record_video:

                # make sure directory in which we save videos exists within main dir
                os.makedirs("videos", exist_ok=True)

                file_name = f"bf_{cfg_radar['exp_name']}_{timestamp}.mp4"

                self.video_writer = FFMpegWriter(fps=10, bitrate=1800)
                self.video_writer.setup(self.fig, os.path.join("videos", file_name), dpi=120)
                print("Video recording started.")

            #   ----------------------------------------------------------------
            

            # ----------------------------------------------------
            # NOTE: Jan - jerry detector classifier output
            # -------------------------------------------------------
            model_path = "../../data_exploration/model/jerry_detector.pkl"
            self.classifier = joblib.load(model_path)

            self.text = self.ax.text(
                0.02, 0.95, "",
                transform=self.ax.transAxes,
                color="red",
                fontsize=12
            )
            
            self.last_frame_time = time.time()
            self.frame_counter = 0
            self.fps = 0
            self.last_fps_time = time.time() 

            self.taskMgr.add(self.updateTask, "updateTask")

            self.x = np.arange(-cfg_radar["width"], cfg_radar["width"], 1)
            self.y = self.r_idxs
            self.X, self.Y = np.meshgrid(self.x, self.y, indexing='xy')

            self.cart2pol = cart2pol(self.X.ravel(), self.Y.ravel()) 

            self.last_artists = []
            num_ticks = 7

            # Pick evenly spaced radial ticks across your range bins
            radial_bins = np.linspace(self.r_idxs.min(), self.r_idxs.max(), num_ticks)

            # Convert them to meter labels (or whatever 0.04 means)
            #radial_labels = [f"{rb * 0.045352603795783:.2f}" for rb in radial_bins]
            radial_labels = [f"{rb * cfg_radar['range_res']:.2f}" for rb in radial_bins]


            # Apply ticks to the polar axis
            self.ax.set_rticks(radial_bins)
            self.ax.set_yticklabels(radial_labels)


        # HELPERS -------------------------------------------------------------------------

        def request_shutdown(self, event=None):
            """
            Handles ongoing visualisation/video recording tasks termination.
            """
            if self.is_closing:
                return

            self.is_closing = True
            print("Visualization closing, stopping producer...")
            self.stop_event.set()

            try:
                import matplotlib.pyplot as plt
                plt.ion()                           # NOTE : turns on interactive mode (create/show/update it as the program runs )
                plt.close(self.fig)
            except Exception:
                pass

            
            # Make sure to properly handle video file that is being recorded
            if self.video_writer is not None:
                self.video_writer.finish()
                self.video_writer = None
                print("Video recording saved.")

            # Shut down Panda3D so app.run() can return
            self.destroy()


        def on_close(self, event):
            self.request_shutdown()


        def updateTask(self, task):
            """
            Updates visualiser to newly acquired frame. Also handles video recording (of the real time data visualiser).
            """

            if self.stop_event.is_set():
                return Task.done

            # NOTE: single queue, so don't enumerate tuples — just use it
            try:
                q = self.q1
                while not q.empty():
                    msg = q.get_nowait()
                    if msg[0] == 'bev':
                        # store with a fixed pid 0 (you only have q1)
                        self.latest_msg[0] = msg[1]
                        self.msg_count.add(0)
            except Exception:
                pass

            if self.msg_count == {0}:
                bf_1 = self.latest_msg[0]

                # NOTE: you used self.x1/self.y1 in original — ensure those exist.
                # If radars are at origin, set to 0. Adjust as you need.
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
                to_plot = to_plot # NB: Need to be sure this matches model

                # ------------------------------------
                # NOTE: Jan - jerry detector classifier working
                # ------------------------------------
                frame = to_plot
                x = frame.reshape(1, -1)
                
                pred = self.classifier.predict(x)
                label = "Jerry get yo ass outta here!" if pred[0] > 0.8 else "No Jerry"
                print(f"{label} (confidence: {pred[0]:.2f})")
                self.text.set_text(f"{label} (confidence: {pred[0]:.2f})")


                # # FPS update
                # current_time = time.time()
                # self.frame_counter += 1
                # if current_time - self.last_fps_time >= 1.0:
                #     self.fps = self.frame_counter / (current_time - self.last_fps_time)
                #     self.last_fps_time = current_time
                #     self.frame_counter = 0


                self.im.set_array(to_plot.ravel())
                
                self.fig.canvas.draw_idle() 
                QtWidgets.QApplication.processEvents()


                # grabs the current displayed frame (from the visualiser) and appends it to the video recording
                # (note to self : check the doc of '.grab_frame()')
                if self.video_writer is not None:
                    self.video_writer.grab_frame()
 
                self.msg_count.clear()
                plt.pause(0.001)

            return Task.cont        

        # -------------------------------------------------------------------------


    # instantiate and run (this stays in the main process)
    app = MyApp(q1, cfg_radar, stop_event)
    app.run()


# -------------------------
# main guard: run producer in child, GUI in main
# -------------------------
def main(cfg_radar, cfg_cfar):
    q_main_1 = Queue(maxsize=1)
    stop_event = Event()


    #   ----------------------------------------------------------------
    #
    #   NOTE : (kerim -- 4/21/2026)
    #
    #           -- Changed the 'daemon=True' to 'False'.
    #           -- Python doc indicates that daemonic child processes are terminated when the parent exits, 
    #           -- and terminate() on Windows uses TerminateProcess(), which does not run finally blocks or exit handlers
    #
    #   NOTE :  in previous setting, Windows/native-runtime behavior, Ctrl+C is causing a lower-level abort (forrtl: error (200)) 
    #           -- before Python reaches that except
    #

    producer = Process(
        target=producer_real_time_1843,
        args=(q_main_1, cfg_radar, cfg_cfar, 4096, 4098, "192.168.33.30", "192.168.33.180", stop_event),
        daemon=True
    )




    producer.start()
    print("Producer started, launching visualization in main process...")



    #   ----------------------------------------------------------------
    #
    #   NOTE : apparently, trying to handle Ctrl+C is not great on windows, 
    #          the final approach to "properly" close the program during runtime was to 
    #          do trigger termination when user exists real-time visualiser (close tab).
    #
    #   
    #   NOTE : (kerim -- 4/21/2026)
    #           -- closing the plot window becomes the normal shutdown path
    #
    #           -- CHANGED THIS PART TO HANDLE KEYBOARD INTERRUPT CORRECTLY 
    #           -- (so that file in which we save data closes correctly)
    #   IDEA : main process responsible for shutdown (instead of child-process trying to catch Ctrl-C Interrupt)
    #           -- python doc says 'terminate()' does not run 'finally:' blocks !
    #          goal : let 'stop_event' terminate child process first and only force-terminate as fallback 
    #

    # run visualization (no GUI imports in child process)
    # run_visualization(q_main_1, cfg_radar, cfg_cfar)

    # if run_visualization ever returns, do cleanup
    # try:
    #     while True:
    #         time.sleep(1)
    # except KeyboardInterrupt:
    #     producer.terminate()
    #     producer.join()
    #     print("Shutdown complete.")


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

    #   
    #   -----------------------------------------------
    #   -----------------------------------------------
