import os
import numpy as np
import matplotlib.pyplot as plt
import os
import scipy
import utils.save_adc_data as sd
import utils.utility as utility
from utils.singlechip_raw_data_reader_example import TI_PROCESSOR
from streaming_base.processing.processing import process_frame_2d
from streaming_base.utils.utils import get_ant_pos_2d
# from task3_tracking_TODO import  beamform_2d
from task2_ranging_TODO import rangefft
import argparse
'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself)
    Technically, you do not have to change anything this this file other thatn those paths (so that we can extract chirp parameters correctly and so on).
    This file is for DEBUGGING your function: beamform_2d.
    Goal of this task: debug your beamforming code.
'''

current_dir = os.path.dirname(os.getcwd()) # one level up for this repo

# ----------------------------------------------------------------------------------------- #
#                             Processing function to complete                               #
# ----------------------------------------------------------------------------------------- #

# TODO; complete the 2D beamforming image as describe as Algorithm 2 in the lecture
def beamform_2d(beat_freq_data, radar_params, x_locs):
    """
    Performs 2D beamforming along the azimuth (horizontal) dimension, this results in a bird eye view image.

    Parameters
    ----------
    beat_freq_data : np.ndarray
        The beat frequency data, typically a 3D array.
    phi_s : float
        The starting azimuth angle in degrees.
    phi_e : float
        The ending azimuth angle in degrees.
    phi_res : float
        The azimuth angle resolution in degrees.
    x_locs : np.ndarray
        The x-coordinates of the antennas.
    r_idxs : np.ndarray
        The range indices corresponding to the beat frequency data.
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
    angles = np.zeros((phi.shape[0], x_locs.shape[0]))
    for i, phi_val in enumerate(phi):
        angles[i, :] = x_locs[:, 0] * np.cos(phi_val)

    # TODO: compute h_phi for each phase shift (size same as angles)
    # this is calculates the complex valued h_phi from the README
    steering_vec = np.zeros(angles.shape) 
    for i in range(angles.shape[0]):
        for j in range(angles.shape[1]):
            steering_vec[i, j] = np.exp(1j * 2 * np.pi/ lm * angles[i, j])

    # Apply the phase shifts to the beat frequency data and sum over the antennas
    for r, rval in enumerate(r_idxs):
        beat = beat_freq_data[:, r]
        beamformed_signal = beat[np.newaxis, :] * steering_vec
        sph_pwr[:, r] = np.maximum(sph_pwr[:, r], np.abs(np.sum(beamformed_signal, axis=-1)))

    return sph_pwr


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Configure and capture radar data from mmWave Studio.")
    parser.add_argument("--config",type=str, default='scripts/1843_config_debug_task3',help="Run the radar configuration Lua script before capturing.",)
    parser.add_argument("--exp_name",type=str, default='task3_gt',help="Run the radar configuration Lua script before capturing.",)

    return parser.parse_args()

# ----------------------------------------------------------------------------------------- #
#                                        Main function                                      #
# ----------------------------------------------------------------------------------------- #
# This functions runs the pipeline, just not in real time for debugging purposes, you should not have to edit
# anything in this function
def main(args):
    
    # you should not have to edit these
    # home directory path (of the project folder, full path)
    exp_path = f'{current_dir}/data' # 
    # path and name of the JSON files (exlude the .setup.json and .mmwave.json)
    json_filename = f'{current_dir}/scripts'
    # path to config used to capture debug data
    config_lua_script = f'{current_dir}/{args.config}.lua'

    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    # num_rx, num_tx, adc_samples, periodicity, num_frames, chirp_loops
    chirp_dict = utility.read_radar_params(config_lua_script)

    processor = TI_PROCESSOR()
    # temp file
    mmwave_dict, setup_dict, mmwave_filename, setup_filename = sd.process_json_files(json_filename, chirp_dict, exp_path, args.exp_name)

    adc_data = processor.rawDataReader(setup_dict, mmwave_dict, os.path.join(exp_path, args.exp_name), 'tmp_rdc.mat')
    adc_data = np.stack(adc_data, axis=-1)
    adc_data = np.reshape(adc_data, (adc_data.shape[0], adc_data.shape[1], adc_data.shape[2], adc_data.shape[3]))

    num_frames = adc_data.shape[0]
    print("You captured %d frames, for %d TX, %d Rx, and %d adc samples" % adc_data.shape)

    # Parameters for the range-azimuth beamforming
    r_idxs = np.arange(0, chirp_dict['samples_per_chirp'], 1)
    phi = np.deg2rad(np.arange(0, 180, 1))
    width = 100 # azimuth width in degrees

    # Radar  parameters
    cfg_radar = {
        "range_idx": r_idxs,
        "phi": phi,
        "width": width,
        "n_radar": 1,
        "num_tx": chirp_dict['num_tx'],
        "num_rx": chirp_dict['num_rx'],
        "num_doppler": chirp_dict['chirp_loops'],
        "samples_per_chirp": chirp_dict['samples_per_chirp'],
        "sample_rate": chirp_dict['sample_rate'],
        "c": 3e8,
        "lm": 3e8 / 77e9,
        "slope": chirp_dict['sample_rate']
    }

    # Parameters for CFAR

    cfg_cfar = {
        "cfar_on": False, 
        "bg_sub": False,
        "num_train_r": 10,
        "num_train_d": 10,
        "num_guard_r": 4,
        "num_guard_d": 2,
        "threshold_scale": 1e-3
    }

    x_locs, _, _ = get_ant_pos_2d(chirp_dict['num_tx']*chirp_dict['num_rx'], chirp_dict['samples_per_chirp'], chirp_dict['num_rx'])

    # --- Setup polar plot ---
    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(111, projection="polar")

    PHI, R = np.meshgrid(phi, r_idxs, indexing="ij")

    # initial dummy image
    bf_img = np.zeros_like(PHI)
    im = ax.pcolormesh(PHI, R, bf_img, shading="auto")

    ax.set_ylim(r_idxs[0], r_idxs[-1])
    plt.tight_layout()
    plt.ion()
    plt.show()

    ############################### process data! ################################
    rfft = scipy.fft.fft(np.squeeze(adc_data[:,:,:,:]), axis=-1)
    rfft = rfft.transpose(1, 2, 0, 3) # tx, rx, frames, adc samples
    rfft = rfft.reshape(chirp_dict['num_tx']*chirp_dict['num_rx'], num_frames, chirp_dict['samples_per_chirp'])
    rfft = rfft.transpose(1,0,2) # frames, trx, adc samples
    last_frames = np.zeros((5, chirp_dict['num_tx']*chirp_dict['num_rx'], chirp_dict['samples_per_chirp']), dtype=np.complex64)

    for frame in range(0, rfft.shape[0]):
        # Apply FFT along the range dimension
        range_fft = rfft[frame]

        last_frames[:-1] = last_frames[1:]
        last_frames[-1] = range_fft

        # Set the static range indices to zero
        range_fft[:, 0:5] = 0
        range_fft = np.reshape(range_fft,(range_fft.shape[0],1,range_fft.shape[-1]))

        bf_input = np.mean(last_frames,axis=0)

        bf_output = beamform_2d(bf_input.squeeze(), cfg_radar, x_locs[:,0])
        dets = process_frame_2d(abs(bf_output)**2, cfg_cfar)
        bf_output = dets 
        if bf_output.shape != (len(phi), len(r_idxs)):
            print("ERROR: bf_output shape =", bf_output.shape,
                "expected =", (len(phi), len(r_idxs)))
            continue
        Z = np.abs(bf_output)

        im.set_array(Z.ravel())                # efficient
        im.set_clim(0, Z.max() + 1e-9)         # normalize color scale

        fig.canvas.draw_idle()
        fig.canvas.flush_events()
        


if __name__ == "__main__":
    args = parse_args()
    main(args)