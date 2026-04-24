import numpy as np
import matplotlib.pyplot as plt
import os
import scipy
import scipy.io as sio
import sys

sys.path.append(os.path.dirname(os.getcwd()))

import utils.save_adc_data as sd
import utils.utility as utility


def create_file_path(home_dir, data_dir, filename):
    path = os.path.join(home_dir, data_dir, "rdc_" + filename + '.mat')
    return path


def save_adc_data(path, filename, home_dir, data_dir, json_filename, args):
    if not os.path.exists(path):
        sd.save_adc_data(filename, home_dir, data_dir, json_filename,args)

def load_adc_data(path):
    bin_data = sio.loadmat(path)
    raw_data = np.array(bin_data['data_raw'])
    return raw_data

def read_lua_config(home_dir = "D:/GitHub/COM-304-Rat-Detection", lua_file = "config.lua"):
    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    chirp_dict = utility.read_radar_params(os.path.join(home_dir, lua_file))

    tx_en = '0x7' # HEX enable (1 for on, 0 for off)
    rx_en = '0xF' # HEX enable (1 for on, 0 for off)

    args = [chirp_dict['num_tx'], chirp_dict['num_rx'], chirp_dict['samples_per_chirp'], chirp_dict['chirp_loops'], tx_en, rx_en]

    return args, chirp_dict

def load_radar_capture(filename, data_dir, home_dir, json_filename, args):
    """
    Loads radar capture and computes range FFT.

    Returns:
        raw_data  : raw ADC cube
        range_fft : FFT along ADC samples
    """

    path = create_file_path(home_dir, data_dir, filename)

    # Convert BIN → MAT if needed
    save_adc_data(path, filename, home_dir, data_dir, json_filename, args)

    # Load radar cube
    raw_data = load_adc_data(path)

    # Range FFT (ADC samples axis)
    range_fft = scipy.fft.fft(raw_data, axis=3)

    return raw_data, range_fft