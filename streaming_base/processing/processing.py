# Info:
# This file contains the main processing functions for the radar data, 
# including range FFT, beamforming, CFAR detection and doppler helps..
# -----

import numpy as np
from scipy.signal import convolve2d
from scipy.ndimage import median_filter

from sklearn.cluster import DBSCAN

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

def compute_dbscan(output_top, r_idxs, phi, eps=0.5, min_samples=5, p_treshold= 98):
    """
    Compute DBSCAN clustering on the output of the beamforming process.

    Parameters
    ----------
    output_top : np.ndarray
        The output of the beamforming process, typically a 2D array.
    r_idxs : np.ndarray
        The range indices corresponding to the output.
    phi : np.ndarray
        The azimuth angles corresponding to the output.
    eps : float
        The maximum distance between two samples for one to be considered as in the neighborhood of the other.
    min_samples : int
        The number of samples in a neighborhood for a point to be considered as a core point.

    Returns
    -------
    db : DBSCAN
        The fitted DBSCAN model containing the cluster labels.
    """

    # Build full coordinate grid
    phi_rad_2d, r_idxs_2d = np.meshgrid(phi, r_idxs, indexing='ij')  # shape: (180, 140)

    x_coords_m = np.cos(phi_rad_2d) * r_idxs_2d  # shape: (180, 140)
    z_coords_m = np.sin(phi_rad_2d) * r_idxs_2d  # shape: (180, 140)

    # Flatten for DBSCAN
    points = np.stack([x_coords_m.ravel(), z_coords_m.ravel()], axis=1)
    powers = output_top.ravel()

    # Keep only high-power points
    threshold = np.percentile(powers, p_treshold)
    valid_mask = powers > threshold
    points_thresh = points[valid_mask]

    # DBSCAN
    db = DBSCAN(eps = 0.5, min_samples=min_samples).fit(points_thresh)

    return db


def rangefft(raw_data):
    """
    Performs a range FFT on the raw data.

    Parameters
    ----------
    raw_data : np.ndarray
        The raw data from FMCW radar. (Size: frames x tx x rx x samples per chirp (adc_samples))

    Returns
    -------
    fft_data : np.ndarray
        The range fft (Note: keep the output of the same size as the input.) 
    """
    # TODO: take the range fft on the raw_data, you should keep the output the same size as the input
    #fft_data = np.zeros(raw_data.shape)

    fft_data = np.fft.fft(fft_data,axis=-1)

    return fft_data # must be of size frames x tx x rx x samples per chirp (adc_samples)


def beamform_2d(beat_freq_data, radar_params, x_locs):
    """
    Performs 2D beamforming along the azimuth (horizontal) dimension, this results in a bird eye view image.

    Parameters
    ----------
    beat_freq_data : np.ndarray
        The beat frequency data, typically a 3D array.
    x_locs : np.ndarray
        The x-coordinates of the antennas.
    radar_params : dict
        A dictionary containing radar parameters such as sample rate, number of range samples, etc. 

    Returns
    -------
    sph_pwr : np.ndarray
        The spherical power array after beamforming, with shape (num_phi, samples_per_chirp).
    """

    # Radar parameters
    lm = radar_params["lm"]

    # Get the azimuth angles and range indices
    phi = radar_params["phi"]
    num_phi = len(phi)
    r_idxs = radar_params["range_idx"]

    # Initialize the spherical power array 
    sph_pwr = np.zeros((num_phi, r_idxs.shape[0]), dtype=np.complex64)

    # TODO: compute array for phase shifts for angles  (size: phi x x_locs)
    # this is essentially calculating d_n * cos(phi) from the README
    angles = x_locs * np.cos(phi[:, np.newaxis])

    # TODO: compute h_phi for each phase shift (size same as angles)
    # this is calculates the complex valued h_phi from the README
    #steering_vec = np.zeros(angles.shape) 
    steering_vec = np.exp(1j*2*np.pi/lm * angles)

    # Apply the phase shifts to the beat frequency data and sum over the antennas
    for r, rval in enumerate(r_idxs):
        beat = beat_freq_data[:, r]
        beamformed_signal = beat[np.newaxis, :] * steering_vec
        sph_pwr[:, r] = np.maximum(sph_pwr[:, r], np.abs(np.sum(beamformed_signal, axis=-1)))

    return sph_pwr



def cfar_ca_2d_mask(power_map,
                    num_train_range: int = 10,
                    num_train_doppler: int = 8,
                    num_guard_range: int = 2,
                    num_guard_doppler: int = 2,
                    rate_fa: float = 1e-5):
    """Boolean-mask variant of cfar_ca_2d. Same math, returns bool ndarray."""
    Tr, Td = num_train_range, num_train_doppler
    Gr, Gd = num_guard_range, num_guard_doppler
    Wr = Tr + Gr
    Wd = Td + Gd
    Nwin = (2*Wr+1)*(2*Wd+1)
    Nguard = (2*Gr+1)*(2*Gd+1)
    Ntrain = Nwin - Nguard
    kernel_win   = np.ones((2*Wr+1, 2*Wd+1), dtype=float)
    kernel_guard = np.ones((2*Gr+1, 2*Gd+1), dtype=float)
    sum_win   = convolve2d(power_map, kernel_win,   mode='same', boundary='fill', fillvalue=0)
    sum_guard = convolve2d(power_map, kernel_guard, mode='same', boundary='fill', fillvalue=0)
    sum_train = sum_win - sum_guard
    noise_level = sum_train / float(Ntrain)
    alpha = Ntrain * (rate_fa**(-1.0/Ntrain) - 1.0)
    threshold = alpha * noise_level
    return power_map > threshold


def build_rd_power_map(rd_cube):
    """Collapse (num_ant, num_doppler, num_range) cube to (num_doppler, num_range) power map."""
    return np.mean(np.abs(rd_cube) ** 2, axis=0)


def notch_zero_velocity(rd_cube, n_notch=2):
    """Zero out +/- n_notch Doppler bins around DC (post-fftshift) on a copy of rd_cube."""
    out = rd_cube.copy()
    if n_notch <= 0:
        return out
    nd = out.shape[1]
    # With very few Doppler bins (e.g. CHIRP_LOOPS=1 in Lua), a ±n_notch mask covers
    # the entire axis and wipes all energy — no CFAR / no tracks. Skip in that case.
    if nd <= 2 * n_notch + 1:
        return out
    mid = nd // 2
    lo = max(0, mid - n_notch)
    hi = min(nd, mid + n_notch + 1)
    out[:, lo:hi, :] = 0
    return out


def beamform_2d_s(rd_cube, radar_params, x_locs, dets):
    """
    Sparse azimuth beamforming: only the (doppler, range) cells flagged by `dets`
    contribute. rd_cube: (num_ant, num_doppler, num_range) complex.
    dets: (num_doppler, num_range) bool. Returns (num_phi, num_range) complex64.
    """
    lm = radar_params["lm"]
    phi = radar_params["phi"]
    num_phi = len(phi)
    r_idxs = radar_params["range_idx"]

    angles = x_locs * np.cos(phi[:, np.newaxis])
    phase_shifts = np.exp((1j * 2 * np.pi / lm) * angles)

    d_idx, r_idx = np.nonzero(dets)
    sph_pwr = np.zeros((num_phi, r_idxs.shape[0]), dtype=np.complex64)
    for d, r in zip(d_idx, r_idx):
        beat = rd_cube[:, d, r]
        beamformed = phase_shifts * beat[np.newaxis, :]
        beam_power = np.abs(np.sum(beamformed, axis=-1))
        sph_pwr[:, r] = np.maximum(sph_pwr[:, r], beam_power)
    return sph_pwr
