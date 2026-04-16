import os
import numpy as np
import os
import sys

sys.path.append(os.path.dirname(os.getcwd())) # one level up for this repo

import utils.save_adc_data as sd
import utils.utility as utility
from utils.singlechip_raw_data_reader_example import TI_PROCESSOR
import matplotlib.pyplot as plt
import scipy
import argparse

'''
    Again, the primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself)
    Goal of this task: Get familiar with basic processing of the captured data, edit the Lua script.
'''

current_dir = os.path.dirname(os.getcwd()) # one level up for this repo

# ----------------------------------------------------------------------------------------- #
#                                     Processing functions                                  #
# ----------------------------------------------------------------------------------------- #
# TODO: Complete the function to perform ranging and plot the resulting figure here
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

    fft_data = np.fft.fft(fft_data)

    return fft_data # must be of size frames x tx x rx x samples per chirp (adc_samples)


# Plots your result 
def plot_rangefft(fft_data,range_res):
    """
    Plots a range FFT.

    Parameters
    ----------
    fft_data : np.ndarray
        The range fft data. (Size: frames x tx x rx x samples per chirp (adc_samples))
        Note that for plotting you can plot a single frame and tx/rx pair or sum them all up.
 
    """

    # Plot the Range FFT
    plt.plot(np.arange(fft_data.shape[-1]) * range_res, abs(np.squeeze(np.sum(fft_data,axis=(0,2,1))))**2)
    plt.xlabel('Distance in meters')
    plt.ylabel('Power')
    plt.show(block=True)
    
    return 

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Configure and capture radar data from mmWave Studio.")
    parser.add_argument("--config",type=str, default='scripts/1843_config_lowres',help="Run the radar configuration Lua script before capturing.",)
    parser.add_argument("--exp_name",type=str, default='test',help="Run the radar configuration Lua script before capturing.",)
    return parser.parse_args()

# ----------------------------------------------------------------------------------------- #
#                                        Main function                                      #
# ----------------------------------------------------------------------------------------- #
def main(args):
    #o folder name that you want to save data, default is data
    exp_path = f'{current_dir}/data' # path to data folder 

    # no need to change
    json_filename = f'{current_dir}/scripts'

    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    # num_rx, num_tx, adc_samples, periodicity, num_frames, chirp_loops
    chirp_dict = utility.read_radar_params(args.config + '.lua')
    print(chirp_dict['range_res'])
    # Put the path (relative to home_dir) and name of the JSON files (exlude the .setup.json and .mmwave.json), you should not have to edit this
    processor = TI_PROCESSOR()

    # temp file that has your chirp parameters 
    mmwave_dict, setup_dict, mmwave_filename, setup_filename = sd.process_json_files(json_filename, chirp_dict, exp_path, args.exp_name)

    # this reads the data from the binary file and puts it into a nice array for you
    adc_data = processor.rawDataReader(setup_dict, mmwave_dict, os.path.join(exp_path, args.exp_name), 'tmp_rdc.mat')
    adc_data = np.stack(adc_data, axis=-1)
    # in the end the data will be of shape (number of frames x number of transmitters x number of receivers x number of samples per chirp aka adc samples)
    adc_data = np.reshape(adc_data, (adc_data.shape[0], adc_data.shape[1], adc_data.shape[2], adc_data.shape[3]))

    print("You captured %d frames, for %d TX, %d Rx, and %d adc samples" % adc_data.shape)

    ############################### process data! ################################
    fft_data = rangefft(adc_data)
    plot_rangefft(fft_data, chirp_dict['range_res'])

if __name__ == "__main__":
    args = parse_args()
    main(args)