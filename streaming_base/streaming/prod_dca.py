import numpy as np
import queue
import signal
import time
from datetime import datetime
import os

# from streaming_base.mmwave.dataloader.adc import DCA1000 
from streaming_base.processing.processing import process_frame, get_accumulated_time_data, process_frame_2d, beamform_2d, get_freq, get_br_hr


from streaming_base.utils.utils import get_ant_pos_2d 
from streaming_base.mmwave.dataloader.adcv3 import DCA1000

def producer_real_time_1843(q, cfg_radar, cfg_cfar, config_port, data_port, static_ip, system_ip, stop_event):
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
    stop_event : Event
        Handles Ctrl-c Event and nicely closes (child-)processes 
    """

    # Ignore Ctrl+C in the child; main process handles shutdown
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Parameters
    r_idxs = cfg_radar["range_idx"]
    num_tx = cfg_radar["num_tx"]
    num_rx = cfg_radar["num_rx"]
    chirp_loops = cfg_radar["num_doppler"]
    adc_samples = cfg_radar["samples_per_chirp"]

    #   -------------------------------------------------------------
    #
    #   NOTE :  I ADDED THIS -- 4/20/2026 KERIM
    #   HERE :  WE SETUP THINGS SO THAT REAL-TIME RAW DATA GETS SAVED 
    #

    save_raw_dt = cfg_radar["save_raw_dt"]      # NOTE :    think of this like an on/off switch 
    bin_file = None                             #       -- decides whether we "trigger" the "save proceedure" or not

    timestamp = datetime.today().strftime("%m-%d-%Y_%H-%M-%S")

    if save_raw_dt:
        #   NOTE :  this block sets up things so that we record and save the incoming data 
        #           if 'save_raw_dt' field was entered in the terminal
        exp_path = cfg_radar["exp_path"]
        exp_name = cfg_radar["exp_name"]

        os.makedirs(exp_path, exist_ok=True)

        bin_path = os.path.join(exp_path, f"{exp_name}_Raw_0_{timestamp}.bin")

        # overwrite file with same name if it exists

        if os.path.exists(bin_path):
            os.remove(bin_path)

        bin_file = open(bin_path, "ab")
        print(f"Saving raw data stream to {bin_path}")

    #
    #   -------------------------------------------------------------




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
        #while True:
        while not stop_event.is_set():

            # Read data from DCA1000
            # raw = dca.read(timeout=0.5, chirps=chirp_loops, rx=num_rx, tx=num_tx, samples=adc_samples)
            # raw = read_packet(num_rx, num_tx, adc_samples)$


            adc_data = dca.read(timeout=3.0)       #  NOTE :  (kerim 4/20/2024) 
                                        #         -- THIS CORRESPONDS TO THE FRESHLY CAPTURED 
                                        #         -- FRAME COMING FROM THE DCA1000 READ CALL
            #
            #  NOTE : It is supposed to return 'int16' dtype (according to its doc) 
            #   -------------------------------------------------------------


            #   -------------------------------------------------------------
            #
            #   NOTE :  I ADDED THIS -- 4/20/2026 KERIM
            #   HERE :  WE SETUP THINGS SO THAT REAL-TIME RAW DATA GETS SAVED 
            

            #   NOTE :  here we make sure we want to save the data ('save_raw_dt' = True)
            #           and that there is a valid freshly captured frame (else 'None').
            if save_raw_dt and adc_data is not None:

                adc_data.astype(np.int16).tofile(bin_file)      
                #   NOTE : ".tofile(bin_file)" appends that frame to 
                #           the ".bin" file in which we store incoming raw data 
                #   
                #   NOTE : "int16" is standard saveable binary format

            #
            #   -------------------------------------------------------------




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


            if cfg_radar['doppler']:
                # NOTE : this part was added (Kasper's Doppler Algo)

                current = last_frames[-1]                  # (num_ant, chirp_loops, range_bins)
                
                # Doppler FFT across chirp_loops axis.
                N_CHIRPS = current.shape[1]                # e.g. 32
                doppler = np.fft.fftshift(np.fft.fft(current, n=N_CHIRPS, axis=1), axes=1) # (num_ant, N_CHIRPS, range_bins)
                
                # Zero-velocity notch: kill bins near DC (the static pipe).
                mid = N_CHIRPS // 2                        # bin 16 == zero velocity
                n_notch = 3                                # ±3 bins of velocity zeroed (tune to taste)

                doppler[:, mid-n_notch:mid+n_notch+1, :] = 0

                # Coherent across antennas: pick the strongest moving velocity bin per range
                # using power summed across antennas (same velocity bin for all antennas at
                # each range, so cross-antenna phase is preserved for beamforming).
                power = np.sum(np.abs(doppler), axis=0)            # (N_CHIRPS, range_bins)
                best_vel = np.argmax(power, axis=0)                # (range_bins,)
                r_idx = np.arange(doppler.shape[2])
                bf_input = doppler[:, best_vel, r_idx]             # (num_ant, range_bins) COMPLEX

                # Noise mask: only keep range bins whose peak moving-power exceeds an
                # adaptive noise floor. Without this, every empty range bin still picks
                # *some* argmax velocity (just noise) and gets beamformed to a random angle,
                # producing scattered speckle across the whole heatmap.
                peak_power = power[best_vel, r_idx]                # (range_bins,)
                noise_floor = np.median(peak_power) * 3.0          # 3x median (tune: 2–5)
                mask = peak_power > noise_floor                    # (range_bins,) bool
                bf_input = bf_input * mask[np.newaxis, :]

            else:      
                # NOTE : this part (and all that follows) was there (w/o current cond. statement) originally
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


    #   -------------------------------------------------------------
    #   -------------------------------------------------------------
    #
    #   NOTE : (kerim 4/20/2024) -- I ADDED THIS !!!!!
    #   Purpose : safely close file in which we were saving real-time captured raw data.
    #

    finally:
        # dca.close()   # this was there originally (not me)
        if bin_file is not None:
            bin_file.close()
            print("Data has been recorded and file has been safely closed.")

    #
    #   -------------------------------------------------------------
    #   -------------------------------------------------------------
    





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