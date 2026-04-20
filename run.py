import os
import numpy as np
import matplotlib.pyplot as plt
import sys
import scipy
import argparse

import utils.save_adc_data as sd
import utils.utility as utility
from utils.singlechip_raw_data_reader_example import TI_PROCESSOR

from streaming_base.processing.processing import process_frame_2d
from streaming_base.utils.utils import get_ant_pos_2d
from streaming_base.processing.processing import rangefft, beamform_2d, cfar_ca_2d

'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself)
    Technically, you do not have to change anything this this file other thatn those paths (so that we can extract chirp parameters correctly and so on).
    This file is for DEBUGGING your function: beamform_2d.
    Goal of this task: debug your beamforming code.
'''

current_dir = (os.getcwd())


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

    print("Reading raw data from: ", mmwave_filename)
    print("Using setup file: ", setup_filename)
    
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