import numpy as np
from scipy.signal import convolve2d

# implement this function to accumulate the time domain data 
def get_accumulated_time_data(current_range_data, range_fft_s):
    
    afx = np.squeeze(range_fft_s)

    # append current frame
    current_range_data[:-1] = current_range_data[1:]
    current_range_data[-1] = afx

    return current_range_data

def cfar_ca_2d(power_map,
               num_train_range: int = 10,
               num_train_doppler: int = 8,
               num_guard_range: int = 2,
               num_guard_doppler: int = 2,
               rate_fa: float = 1e-5):
    """
    2D Cell-Averaging CFAR on a (range × Doppler) power map.

    Parameters
    ----------
    power_map : 2D np.ndarray
        The incoherent power map |X|^2 over (range, Doppler).
    num_train_range : int
        # of training cells on each side in range
    num_train_doppler : int
        # of training cells on each side in Doppler
    num_guard_range : int
        # of guard cells on each side in range
    num_guard_doppler : int
        # of guard cells on each side in Doppler
    rate_fa : float
        Desired probability of false alarm

    Returns
    -------
    detection_map : 2D bool np.ndarray
        True where power_map exceeds the CFAR threshold.
    """

    Tr, Td = num_train_range, num_train_doppler
    Gr, Gd = num_guard_range, num_guard_doppler

    # full window half–sizes
    Wr = Tr + Gr
    Wd = Td + Gd

    # number of training cells total
    Nwin = (2*Wr+1)*(2*Wd+1)
    Nguard = (2*Gr+1)*(2*Gd+1)
    Ntrain = Nwin - Nguard

    # build convolution kernels
    kernel_win   = np.ones((2*Wr+1, 2*Wd+1), dtype=float)
    kernel_guard = np.ones((2*Gr+1,2*Gd+1), dtype=float)

    # sum over full window
    sum_win   = convolve2d(power_map, kernel_win,   mode='same', boundary='fill', fillvalue=0)
    # sum over guard+CUT region
    sum_guard = convolve2d(power_map, kernel_guard, mode='same', boundary='fill', fillvalue=0)

    # training‐cell sum = window minus guard (which includes the CUT)
    sum_train = sum_win - sum_guard

    # noise estimate (average of training cells)
    noise_level = sum_train / float(Ntrain)

    # CFAR threshold multiplier (cell–averaging formula)
    alpha = Ntrain * (rate_fa**(-1.0/Ntrain) - 1.0)
    threshold = alpha * noise_level

    detection_map = np.where(power_map > threshold, power_map, 0)

    return detection_map

def process_frame(range_fft, cfar_params):
    """
    Process a single frame of range FFT data to detect targets using CFAR.

    Parameters
    ----------
    range_fft : np.ndarray
        The range FFT data, typically a 2D array of shape (N_ant, N_R).
    cfar_params : dict
        A dictionary containing CFAR parameters such as number of training cells, guard cells, and threshold scale.

    Returns
    -------
    dets : np.ndarray
        A 2D boolean array indicating detected targets, where True indicates a detection.
    """

    # Doppler FFT
    rd_cube = np.fft.fft(range_fft, axis=1)    # → (N_ant, N_D=N_adc, N_R=N_chirps)

    # Build RD magnitude for CFAR (average across antennas)
    rd_map = np.mean(np.abs(rd_cube)**2, axis=0)  # shape (N_R, N_D)

    # CFAR detections
    dets = cfar_ca_2d(rd_map,
                    cfar_params["num_train_r"],
                    cfar_params["num_train_d"],
                    cfar_params["num_guard_r"],
                    cfar_params["num_guard_d"],
                    cfar_params["threshold_scale"])

    return dets

def process_frame_2d(range_fft, cfar_params):
    """
    Process a single frame of range FFT data to detect targets using CFAR.

    Parameters
    ----------
    range_fft : np.ndarray
        The range FFT data, typically a 2D array of shape (N_ant, N_R).
    cfar_params : dict
        A dictionary containing CFAR parameters such as number of training cells, guard cells, and threshold scale.

    Returns
    -------
    dets : np.ndarray
        A 2D boolean array indicating detected targets, where True indicates a detection.
    """

    # Doppler FFT
    # rd_cube = np.fft.fft(range_fft, axis=1)    # → (N_ant, N_D=N_adc, N_R=N_chirps)

    # Build RD magnitude for CFAR (average across antennas)
    # rd_map = np.mean(np.abs(rd_cube)**2, axis=0)  # shape (N_R, N_D)

    # CFAR detections
    dets = cfar_ca_2d(range_fft,
                    cfar_params["num_train_r"],
                    cfar_params["num_train_d"],
                    cfar_params["num_guard_r"],
                    cfar_params["num_guard_d"],
                    cfar_params["threshold_scale"])

    return dets

