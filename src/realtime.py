# Info:
# This file contains the main function to start the real-time radar streaming and processing.
# It reads the radar parameters from a lua config file, sets up the radar and CFAR configurations,
# then calls the main function of the realtime_streaming module to start the streaming and processing.
# NB: we recommend to run this file directly after configuring radar using configure.py
# -------------------------------------

import os
import sys
import argparse
import numpy as np

sys.path.append(os.path.dirname(os.getcwd())) # one level up for this repo

from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
import utils.utility as utility

from streaming_base.streaming import realtime_streaming

current_dir = (os.path.dirname(os.getcwd())) # one level up for this repo

def main(cfar_on, exp_name="test", save_raw_dt=False, doppler=False):
    """
    Main function to start the real-time radar streaming and processing.

    Args:
        cfar_on (bool): Whether to apply CFAR detection.
        exp_name (str): Base filename for saved raw data.
        save_raw_dt (bool): Whether to save the real-time captured raw data.
        doppler (bool): Whether to include Doppler processing.
    """

    # Parameters for the range-azimuth beamforming.
    max_bin = max(8, int(1.5 / chirp_dict['range_res']))
    r_idxs = np.arange(0, min(max_bin, chirp_dict['samples_per_chirp']), 1)  # Range-gate to ~1.5 m

    phi = np.deg2rad(np.arange(0, 180, 1))
    width =  len(r_idxs) # azimuth width in degrees

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
        "slope": chirp_dict['slope'],
        "range_res": chirp_dict['range_res'],          
        "save_raw_dt": save_raw_dt,
        "exp_name": exp_name,
        "exp_path": os.path.join(current_dir, "data"),   # NOTE : Data Directory Path (for specified experiment file)
        "doppler" : doppler
    }

    # Parameters for CFAR
    cfg_cfar = {
        "cfar_on": cfar_on,
        "bg_sub": not doppler,  # subtract previous-frame range FFT to kill static clutter (pipe walls, floor, etc.)
        "num_train_r": 10,
        "num_train_d": 10,
        "num_guard_r": 4,
        "num_guard_d": 2,
        "threshold_scale": 1e-3, # CFAR rate_fa. Lower = stricter (fewer detections), higher = looser.
        "doppler_notch_bins": 1,
    }
    cfg_cfar["doppler_notch_bins"] = max(cfg_cfar.get("doppler_notch_bins", 2), 2)

    print("Starting streaming...")
    realtime_streaming.main(cfg_radar, cfg_cfar)

if __name__ == "__main__":
    #   PARSER --------------------------------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Example script with command line arguments.")

    # Add arguments
    parser.add_argument("--config",  action="store_true", help="True if you want to configure the radar from python.")
    parser.add_argument("--cfar", action="store_true", help="True if you want cfar.")
    parser.add_argument("--doppler", action="store_true", help="True if you want doppler.")
    parser.add_argument("--save_raw_dt", action="store_true", help="True if you want to save the real-time captured raw data to 'data/<exp_name>_Raw_0.bin'.")
    parser.add_argument("--exp_name", type=str, default="test", help="Base filename for saved raw data")

    args = parser.parse_args()
    #   ---------------------------------------------------------------------------------------------------------------
    if args.doppler:
        config_lua_script = f'{current_dir}/scripts/config_doppler.lua'
    else:
        config_lua_script = f'{current_dir}/scripts/config_streaming.lua'
    
    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    # num_rx, num_tx, samples_per_chirp, periodicity, num_frames, chirp_loops, _, _, _
    chirp_dict = utility.read_radar_params(config_lua_script)

    if args.config:
        radar1 = radar()
        radar1.mmwave_config(config_lua_script)
    main(args.cfar, args.exp_name, args.save_raw_dt, args.doppler)
