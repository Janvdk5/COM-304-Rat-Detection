import numpy as np
import queue
import time

# from streaming_base.mmwave.dataloader.adc import DCA1000 
from streaming_base.processing.processing import process_frame, get_accumulated_time_data, process_frame_2d

from task4_vital_signs_TODO import get_freq, get_br_hr
from task3_tracking_TODO import beamform_2d

from streaming_base.utils.utils import get_ant_pos_2d 
from streaming_base.mmwave.dataloader.adcv3 import DCA1000

def producer_real_time_1843(q, cfg_radar, cfg_cfar, config_port, data_port, static_ip, system_ip):
    """
    Producer function for real-time data acquisition from the DCA1000 connected to the AWR1843 radar.

    Parameters
    ----------
    q : queue.Queue
        The queue to which the processed data will be sent.
    cfg_radar : dict
        Configuration parameters for the radar, including range indices, number of transmitters, receivers, chirp loops, and ADC samples.
    cfg_cfar : dict
        Configuration parameters for the CFAR processing, including number of training and guard cells, and threshold scale.
    config_port : str
        The port for the DCA1000 configuration.
    data_port : str
        The port for the DCA1000 data.
    static_ip : str
        The static IP address for the DCA1000.
    system_ip : str
        The system IP address.
    """

    # Parameters
    r_idxs = cfg_radar["range_idx"]
    num_tx = cfg_radar["num_tx"]
    num_rx = cfg_radar["num_rx"]
    chirp_loops = cfg_radar["num_doppler"]
    adc_samples = cfg_radar["samples_per_chirp"]

    last_frame = np.zeros((num_rx * num_tx, chirp_loops, adc_samples), dtype=np.complex64)
    last_frames = np.zeros((5, num_rx * num_tx, chirp_loops, adc_samples), dtype=np.complex64)

    # Get the antenna positions
    x_locs, _, _ = get_ant_pos_2d(num_tx*num_rx, adc_samples, num_rx)

    # Setup the DCA1000
    print("Starting producer for DCA1000 with ip " + static_ip + " and system ip " + system_ip)
    dca = DCA1000()
    dca.sensor_config(chirps=num_tx, chirp_loops=chirp_loops, num_rx=num_rx, num_samples=adc_samples)
    # dca = DCA1000(config_port=config_port, data_port=data_port, static_ip=static_ip, system_ip=system_ip)
    print("DCA1000 initialized.")
    try:
        while True:
            # Read data from DCA1000
            # raw = dca.read(timeout=0.5, chirps=chirp_loops, rx=num_rx, tx=num_tx, samples=adc_samples)
            # raw = read_packet(num_rx, num_tx, adc_samples)
            adc_data = dca.read()
            raw = dca.organize(raw_frame=adc_data, num_chirps=num_tx*chirp_loops,
            num_rx=num_rx, num_samples=adc_samples, num_frames=1, model='1843') # frames x chirps x samples x rx
            if raw is None:
                continue
            if not q.empty():
                continue
            
            # raw = dca.organize(raw, chirp_loops, num_tx, num_rx, adc_samples) # shape = (chirp_loops*tx, rx, samples)
            # Apply Hamming window
            adc_windowed = raw * np.hamming(adc_samples)

            # Reshape the data to (num_tx*num_rx, chirp_loops, adc_samples)
            adc_windowed = adc_windowed.reshape(chirp_loops, num_tx, num_rx, adc_samples)
            adc_windowed = adc_windowed.transpose(1, 2, 0, 3) # tx, rx, loops, adc samples
            adc_windowed = adc_windowed.reshape(num_tx*num_rx, chirp_loops, adc_samples)

            # Apply FFT along the range dimension
            range_fft = np.fft.fft(adc_windowed, axis=-1)
            last_frame_fft = np.fft.fft(last_frame, axis=-1)

            # Update the last frame
            last_frame = adc_windowed

            # Substract the last frame and keep only the corresponding range indices
            if cfg_cfar['bg_sub']:
                range_fft = range_fft - last_frame_fft
            range_fft_s = range_fft[:, :, r_idxs]

            # Set the static range indices to zero
            range_fft_s[:, :, 0:4] = 0 

            # append current frame
            last_frames[:-1] = last_frames[1:]
            last_frames[-1] = range_fft_s

            # Compute CFAR
            # if cfg_cfar['before_bf'] == 2:
            #     dets = process_frame(range_fft_s, cfg_cfar)
            #     # # Compute beamforming
            #     bf_output = beamform_2d_s(range_fft_s, cfg_radar, x_locs[:,0], dets)
            #     dets = process_frame_2d(abs(bf_output), cfg_cfar)
            #     bf_output = dets
            
            bf_input = np.mean(last_frames,axis=0)
            bf_output = beamform_2d(bf_input.squeeze(), cfg_radar, x_locs[:,0])
            max_output = abs(bf_output).max()
            if cfg_cfar['cfar_on']: 
                dets = process_frame_2d(abs(bf_output)**2, cfg_cfar)
                bf_output = dets / max_output
            else:
                bf_output /= max_output

            # Send the data to the queue
            try:
                q.put_nowait(("bev", (bf_output)))
            except queue.Full:
                continue

    except KeyboardInterrupt:
        print("Producer for DCA1000 with ip " + static_ip + " and system ip " + system_ip + " stopped by user.")
    # finally:
        # dca.close()

def producer_real_time_1843_task4(q, cfg_radar, cfg_cfar, config_port, data_port, static_ip, system_ip):
    """
    Producer function for real-time data acquisition from the DCA1000 connected to the AWR1843 radar.

    Parameters
    ----------
    q : queue.Queue
        The queue to which the processed data will be sent.
    cfg_radar : dict
        Configuration parameters for the radar, including range indices, number of transmitters, receivers, chirp loops, and ADC samples. 
    config_port : str
        The port for the DCA1000 configuration.
    data_port : str
        The port for the DCA1000 data.
    static_ip : str
        The static IP address for the DCA1000.
    system_ip : str
        The system IP address.
    """

    # Parameters
    r_idxs = cfg_radar["range_idx"]
    num_tx = cfg_radar["num_tx"]
    num_rx = cfg_radar["num_rx"]
    chirp_loops = cfg_radar["num_doppler"]
    adc_samples = cfg_radar["samples_per_chirp"]

    # Setup the DCA1000
    print("Starting producer for DCA1000 with ip " + static_ip + " and system ip " + system_ip)
    dca = DCA1000()
    dca.sensor_config(chirps=num_tx, chirp_loops=chirp_loops, num_rx=num_rx, num_samples=adc_samples)

    print("DCA1000 initialized.")
            

    last_frame = np.zeros((1, chirp_loops, adc_samples), dtype=np.complex64)
    acc_time_data = np.zeros(shape=(cfg_radar['num_frames'], cfg_radar['samples_per_chirp']), dtype=np.complex128)
    second_p = 0
    try:
        while True:
            # Read data from DCA1000
            # raw = read_packet(num_rx, num_tx, adc_samples)

            adc_data = dca.read()
            raw = dca.organize(raw_frame=adc_data, num_chirps=num_tx*chirp_loops,
            num_rx=num_rx, num_samples=adc_samples, num_frames=1, model='1843') # frames x chirps x samples x rx
            if raw is None:
                continue
            if not q.empty():
                continue
            
            # Apply Hamming window
            # adc_windowed = raw * np.hamming(adc_samples)

            # Reshape the data to (num_tx*num_rx, chirp_loops, adc_samples)
            raw = raw.reshape(chirp_loops, num_tx, num_rx, adc_samples)
            raw = raw.transpose(1, 2, 0, 3) # tx, rx, loops, adc samples
            # raw = raw.reshape(num_tx*num_rx, chirp_loops, adc_samples)
            raw_all = raw.squeeze() # for heatrate/breathing rate we can just use one antenna
            range_fft = np.fft.fft(np.sum(raw_all, axis=(0,1)), axis=-1)
            raw = raw[0,-1,:,:].squeeze() # for heatrate/breathing rate we can just use one antenna
            # raw = np.sum(raw[[0,2],:,:,:], axis=(0,1,2)) # for heatrate/breathing rate we can just use one antenna


            # Compute breathing rate/heartrate 
            acc_time_data  = get_accumulated_time_data(acc_time_data, range_fft)
            range_fft = abs(range_fft)
            phase_data, second_p, max_idx = get_br_hr(range_fft, acc_time_data, second_p)
            freq_data, freqs, bpm = get_freq(phase_data, cfg_radar['periodicity'])
            
            # Send the data to the queue
            try:
                # q.put_nowait(("time", (acc_time_data)))
                q.put(("data", (range_fft/np.max(range_fft), phase_data, max_idx, freq_data/np.max(freq_data), freqs, bpm))) 
                # q.put_nowait(("freq", (freq_data)))
            except queue.Full:
                continue

    except KeyboardInterrupt:
        print("Producer for DCA1000 with ip " + static_ip + " and system ip " + system_ip + " stopped by user.")
    # finally:
        # dca.close()