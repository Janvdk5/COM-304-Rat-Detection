import os
import argparse

import sys
sys.path.append(os.path.dirname(os.getcwd())) # one level up for this repo

from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
from utils.read_com import list_files, find_com_port, update_com_port_in_file, find_rtt_dll, update_rtt_path_in_file

'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself)
    Goal of this task: Get familiar with capturing data, go through the Lua script to see what is happening.
'''

current_dir = os.path.dirname(os.getcwd()) # one level up for this repo

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Configure and capture radar data from mmWave Studio.")
    parser.add_argument("--config",type=str, default='',help="Run the radar configuration Lua script before capturing.",)
    parser.add_argument("--exp_name",type=str, default='test',help="Run the radar configuration Lua script before capturing.",)
    return parser.parse_args()

# ----------------------------------------------------------------------------------------- #
#                                        Main function                                      #
# ----------------------------------------------------------------------------------------- #
# Main function
def main(args):
    # change this to the path to location to save data if you want it somewhere else
    exp_path = f'{current_dir}/data' # path to the data folder or wherever you want to save data 

    # path to the lua scripts for recording it in is the home dir(eg. scripts/1843_record.lua)
    # should be the same always
    record_lua_script = f'{current_dir}/scripts/1843_record.lua' 

    # initialize the radar class, this runs .lua scripts from mmWaveStudio
    # path to the lua scripts for configuration assuming it in is the home dir(eg. scripts/1843_config.lua)
    config_lua_script = f'{current_dir}/{args.config}.lua' 

    radar1 = radar()

    # now if you have --configure True in your call to this script it will run the config_lua_script to set chirp parameters
    # you can also run that --configure script in mmWave studio at the bottom of the screen and hit Run
    if not (args.config == ""):
        radar1.mmwave_config(config_lua_script)

    # check to see if you've already captured data with the same experiment name, if so, maybe you don't want to overwrite it
    if os.path.isfile((os.path.join(exp_path, r"%s_Raw_0.bin" % args.exp_name))):
        print("You have files created already so you will overwrite data!")
    else:
        # make experiemnt folder if it doesn't exist
        if not os.path.isdir(exp_path):
            os.mkdir(exp_path)
        # capture data and process it into an array
        radar1.mmwave_capture(args.exp_name, exp_path, record_lua_script)

    ## If this file executes, you should have data stored in a file called {exp_name}_Raw_0.bin


if __name__ == "__main__":
    args = parse_args()
    main(args)
