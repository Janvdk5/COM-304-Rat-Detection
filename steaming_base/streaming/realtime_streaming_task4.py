# top-level: only safe, non-GUI imports
import time
import numpy as np
from multiprocessing import Process, Queue

# import the producer (should not import GUI libs)
from streaming_base.streaming.prod_dca import producer_real_time_1843_task4

# -------------------------
# Visualization code is moved into a function so it is only imported/run
# in the main process (no GUI imports at module top-level)
# -------------------------

def run_visualization(q1, cfg_radar):
    # GUI imports done here (main process only)
    import warnings
    warnings.simplefilter("ignore", UserWarning)

    from scipy.interpolate import RegularGridInterpolator
    from direct.showbase.ShowBase import ShowBase
    from direct.task import Task

    import matplotlib
    matplotlib.use('Qt5Agg')
    import matplotlib.pyplot as plt
    plt.style.use('seaborn-v0_8-dark')

    from panda3d.core import loadPrcFileData
    loadPrcFileData('', 'window-type none')   # no native GL window
    loadPrcFileData('', 'audio-library-name null')

    from PyQt5 import QtWidgets

    from streaming_base.utils.utils import cart2pol


    class MyApp(ShowBase):
        def __init__(self, queue_1, cfg_radar):
            ShowBase.__init__(self)
            self.q1 = queue_1
            self.latest_msg = {}
            self.msg_count = set()
            self.num_frames = cfg_radar['num_frames']
            # self.phi = cfg_radar["phi"]
            self.r_idxs = cfg_radar["range_idx"]
            self.fft_range = [0, 1]
            self.freq_range = [0, 1]
            self.phase_range = [-0.5,0.5]

            self.fig = plt.figure(figsize=(18, 6))
            self.ax_rfft = self.fig.add_subplot(131) 
            self.ax_rfft.set_xlabel('Range Bin')
            self.ax_rfft.set_ylabel('Power')
            self.ax_rfft.set_title('Range FFT')
            self.ax_time = self.fig.add_subplot(132)
            self.ax_time.set_xlabel('Time Index')
            self.ax_time.set_ylabel('Relative Distance')
            self.ax_time.set_title('Phase Data')
            self.ax_freq = self.fig.add_subplot(133) 
            self.ax_freq.set_xlabel('Times per Minute (Hz * 60)')
            self.ax_freq.set_ylabel('Power')
            self.ax_freq.set_title('Frequency on Phase Data')

            # initialize phase plot
            self.phase_x_data = np.arange(self.num_frames)
            self.phase_y_data = np.zeros_like(self.phase_x_data) 
            self.line_phase, = self.ax_time.plot(self.phase_x_data, self.phase_y_data)
            self.ax_time.set_ylim(self.phase_range)
            self.ax_time.set_title('Phase Data')

            # # initialize the freq spectrum plot
            self.freq_x_data = np.arange(self.num_frames)
            self.freq_y_data = np.zeros_like(self.freq_x_data)
            self.line_freq, = self.ax_freq.plot(self.freq_x_data, self.freq_y_data)
            self.ax_freq.set_ylim(self.freq_range)
            self.text_freq = self.ax_freq.text(0.90, 0.85, "0" , fontsize=40, transform=self.ax_freq.transAxes, verticalalignment='top', ha='right')
            self.ax_freq.set_title('Freq Data')

            # self.ax_freq.set_xticks(np.arange(0, self.num_frames , 20)) 
            # self.ax_freq.set_xticklabels(np.arange(0, self.num_frames, 20))

            # initalize range fft plot
            self.fft_x_data = np.arange(len(self.r_idxs))
            self.fft_y_data = np.zeros_like(self.fft_x_data)
            self.line_fft, = self.ax_rfft.plot(self.fft_x_data, self.fft_y_data) 
            # self.line_fft = self.ax_rfft.stem(self.fft_x_data, self.fft_y_data) 
            self.ax_rfft.set_ylim(self.fft_range)
            self.ax_rfft.set_title('Range FFT')
            self.point_x = 0      # you will choose this
            self.point_y = 0      # you will update this live

            # Add marker (red dot)
            self.point_plot, = self.ax_rfft.plot(
                [self.point_x], 
                [self.point_y], 
                marker='o'
            )
            self.taskMgr.add(self.updateTask, "updateTask")

            self.x = np.arange(0, 1)
            self.y = self.r_idxs 

            self.last_artists = []

        def updateTask(self, task):
            # NOTE: single queue, so don't enumerate tuples — just use it
            try:
                q = self.q1
                while not q.empty():
                    msg = q.get_nowait()
                    if msg[0] == 'data':
                        # store with a fixed pid 0 (you only have q1)
                        self.latest_msg[0] = msg[1]
                        self.msg_count.add(0) 
            except Exception:
                pass

            if self.msg_count == {0}:
                rfft = self.latest_msg[0][0]
                phase = self.latest_msg[0][1]
                max_idx = self.latest_msg[0][2]
                freq = self.latest_msg[0][3]
                freq_inds = self.latest_msg[0][4]
                bpm = self.latest_msg[0][5]  

                self.phase_y_data = phase                       
                self.line_phase.set_ydata(self.phase_y_data)
                self.ax_time.set_ylim([np.min(self.phase_y_data)-0.001, np.max(self.phase_y_data)+0.001])

                self.fft_y_data = rfft
                self.line_fft.set_ydata(self.fft_y_data) 
                self.ax_rfft.set_ylim([np.min(self.fft_y_data)-1, np.max(self.fft_y_data)+1]) 
                self.point_x = max_idx
                self.point_y = rfft[self.point_x]   
                self.point_plot.set_data([self.point_x], [self.point_y])

                self.freq_y_data = freq
                self.freq_x_data = freq_inds
                self.line_freq.set_ydata(self.freq_y_data)
                self.line_freq.set_xdata(self.freq_x_data)
                self.ax_freq.set_xlim([self.freq_x_data[0]-1e-5, self.freq_x_data[-1]+1e-5])
                self.ax_freq.set_ylim([0,max(1e-5,np.max(self.freq_y_data))])
                self.text_freq.remove()
                self.text_freq = self.ax_freq.text(0.5, 0.95,"BR and HR in XPM is " + str(bpm),fontsize=20,transform=self.ax_freq.transAxes,ha='center',va='top')
                num_ticks = 7

                # Pick evenly spaced radial ticks across your range bins
                bins = np.linspace(self.freq_x_data.min(), self.freq_x_data.max(), num_ticks)

                # Convert them to meter labels (or whatever 0.04 means)
                labels = [f"{rb * 60:.2f}" for rb in bins]

                # Apply ticks to the polar axis
                self.ax_freq.set_xticks(bins)
                self.ax_freq.set_xticklabels(labels)

                self.fig.canvas.draw_idle() 
                QtWidgets.QApplication.processEvents()
                self.msg_count.clear()
                plt.pause(0.0025)

            return Task.cont
         
    # instantiate and run (this stays in the main process)
    app = MyApp(q1, cfg_radar)
    app.run()


# -------------------------
# main guard: run producer in child, GUI in main
# -------------------------
def main(cfg_radar, cfg_cfar):
    q_main_1 = Queue(maxsize=1)

    producer = Process(
        target=producer_real_time_1843_task4,
        args=(q_main_1, cfg_radar, cfg_cfar, 4096, 4098, "192.168.33.30", "192.168.33.180"),
        daemon=True
    )
    producer.start()
    print("Producer started, launching visualization in main process...")

    # run visualization (no GUI imports in child process)
    run_visualization(q_main_1, cfg_radar)

    # if run_visualization ever returns, do cleanup
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        producer.terminate()
        producer.join()
        print("Shutdown complete.")

