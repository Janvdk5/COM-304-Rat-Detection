from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
import numpy as np
import utils.utility as utility
from streaming_base.streaming import realtime_streaming_task4
import argparse
from utils.read_com import find_com_port, update_com_port_in_file
import os

'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself) at the bototm of this file.
    Technically, you do not have to change anything this this file other thatn those paths (so that we can extract chirp parameters correctly and so on).
    This file is for runing REALTIME code to display 3 plots of vital sign monitoring using your function: get_br_hr, get_freq.
    Goal of this task: debug run your code in real time!
'''

def main():
    """
    Main function to start the real-time radar streaming and processing.
    """

    # Parameters for the range-azimuth beamforming
    r_idxs = np.arange(0, chirp_dict['samples_per_chirp'], 1) 
 
    # Radar  parameters
    cfg_radar = {
        "range_idx": r_idxs, 
        "n_radar": 1,
        "num_tx": chirp_dict['num_tx'],
        "num_rx": chirp_dict['num_rx'],
        "num_doppler": chirp_dict['chirp_loops'],
        "samples_per_chirp": chirp_dict['samples_per_chirp'],
        "sample_rate": chirp_dict['sample_rate'],
        "c": 3e8,
        "lm": 3e8 / 77e9,
        "slope": chirp_dict['sample_rate'],
        "num_frames": 250,
        "periodicity": chirp_dict['periodicity']
    } 
    # Parameters for CFAR
    cfg_cfar = {
        "num_train_r": 10,
        "num_train_d": 8,
        "num_guard_r": 2,
        "num_guard_d": 2,
        "threshold_scale": 1e-2
    }

    print("Starting streaming...")

    # Start the streaming process
    realtime_streaming_task4.main(cfg_radar, cfg_cfar)

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(description="Command line arguments.")
    # Add arguments
    parser.add_argument("--config",  action="store_true", help="True if you want to configure the radar from python.")
    args = parser.parse_args()

    current_dir = os.getcwd()
    # the path of your configuration script
    config_lua_script = f'{current_dir}/scripts/1843_config_streaming_task4.lua'

    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    chirp_dict = utility.read_radar_params(config_lua_script)
    print(chirp_dict)

    if args.config:
        radar1 = radar()
        radar1.mmwave_config(config_lua_script)
    main()