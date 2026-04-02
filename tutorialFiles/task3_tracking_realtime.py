from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
import numpy as np
import utils.utility as utility
from streaming_base.streaming import realtime_streaming_task3 
import argparse
from utils.read_com import find_com_port, update_com_port_in_file
import os 

'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself) at the bototm of this file.
    Technically, you do not have to change anything this this file other thatn those paths (so that we can extract chirp parameters correctly and so on).
    This file is for runing REALTIME code to display a 2D heatmap using your function: beamform_2d.
    Goal of this task: debug run your code in real time!
'''

def main(cfar_on):
    """
    Main function to start the real-time radar streaming and processing.
    """

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
        "cfar_on": cfar_on,
        "bg_sub": False,
        "num_train_r": 10,
        "num_train_d": 10,
        "num_guard_r": 4,
        "num_guard_d": 2,
        "threshold_scale": 1e-3
    }

    print("Starting streaming...")

    # Start the streaming process
    realtime_streaming_task3.main(cfg_radar, cfg_cfar)

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Example script with command line arguments.")
    # Add arguments
    parser.add_argument("--config",  action="store_true", help="True if you want to configure the radar from python.")
    parser.add_argument("--cfar", action="store_true", help="True if you want cfar.")
    args = parser.parse_args()

    current_dir = os.getcwd()
    config_lua_script = f'{current_dir}/scripts/1843_config_streaming_task3.lua'
    
    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    # num_rx, num_tx, samples_per_chirp, periodicity, num_frames, chirp_loops, _, _, _
    chirp_dict = utility.read_radar_params(config_lua_script)

    if args.config:
        radar1 = radar()
        radar1.mmwave_config(config_lua_script)
    main(args.cfar)