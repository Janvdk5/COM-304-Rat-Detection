import os
import numpy as np
import matplotlib.pyplot as plt
import os
import scipy
import scipy.io as sio
import utils.save_adc_data as sd
import utils.utility as utility
from utils.singlechip_raw_data_reader_example import TI_PROCESSOR
# from task4_vital_signs_TODO_old import get_br_hr, get_freq 
from task2_ranging_TODO import rangefft
import argparse
'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself)
    Technically, you do not have to change anything this this file other that those paths (so that we can extract chirp parameters correctly and so on).
    This file is for DEBUGGING your function: get_br_hr, get_freq.
    Goal of this task: debug your vital signs monitoring code.
'''

current_dir = os.path.dirname(os.getcwd()) # one level up for this repo

# ----------------------------------------------------------------------------------------- #
#                             Processing function to complete                               #
# ----------------------------------------------------------------------------------------- #
# TODO: implement this function to extract the breathing/heart rate from the accumulated time domain data
def get_br_hr(summed_range_data, all_range_data, second_p):
    """
    Extracts the phase data for heart rate and breathing monitoring.

    Parameters
    ----------
    summed_range_data : np.array 
        The current range data calculated (a single frame). Use this to extract the location of the reflector.
    current_range_data : np.ndarray
        The range FFT data over time (multiple frames). Size is number of frames x number of samples per chirp. 
    second_p : float 
        A reference value to save each time to faciliate real time plotting. (No need to touch this). 

    Returns
    -------
    unwrapped_phase : np.ndarray
        The unwrapped phase over time (corresponds to distance over time). 
    second_p : float 
        A updated reference value to save each time to faciliate real time plotting.  
    max_idx : int 
        The maximum index (returend for plotting).
    """ 
    # find max index between 0.2 and 1 meter, you can adjust as needed
    max_lim = int(1 // 0.1)
    min_lim = int(0.1 // 0.1)

    max_idx = np.argmax(summed_range_data[min_lim:max_lim]) + min_lim
    
    # TODO: implement the phase extraction of current_range_data at max_idx 
    # (do not forget to unwrap the phase and convert to distance)
    #unwrapped_phase = np.zeros(all_range_data.shape[0])
    for i in range(all_range_data.shape[0]):
        unwrapped_phase[i] = np.angle(all_range_data[i, max_idx])
    
    unwrapped_phase = np.unwrap(unwrapped_phase)

    # to dist
    unwrapped_phase = unwrapped_phase * (3/785) / (2 * np.pi)

    # just brings the average down to 0 of the phase signal
    unwrapped_phase = unwrapped_phase - np.mean(unwrapped_phase)

    return unwrapped_phase, second_p, max_idx
 
# Cacluate the frequency domain information from the time domain phase data.
def get_freq(time_data, periodicity):
    """
    Performs frequency analysis to extract heart rate in BPM. Remember, time_data is a real signal,
    meaning half of the fft output will be symmetric. You only need to look at the first half.

    Parameters
    ----------
    time_data : np.ndarray 
        The time domain phase data, of size number of frames.
    periodicity: float
        Periodicity of the frames (how often a frame is captured).

    Returns
    -------
    fft_phase : np.ndarray
        The frequency data. Size must be the same as freqs.
    freqs : np.ndarray
        The frequency bins associated with each value in fft_phase. 
        This is basically the frequency associated with each value from the output of the FFT.
        It is related to the sampling frequency (aka how often we are capturing frames (periodicity in the Lua file)) and the size of the output of the FFT.
    second_p : float 
        A updated reference value to save each time to faciliate real time plotting.  
    """  
    N = len(time_data)

    # calculate frequency information and the corresponding frequency bins
    N = len(time_data)
    fft_phase = abs(np.fft.fft(time_data))
    freqs = np.fft.fftfreq(N, periodicity * 0.001)
    freq_spacing = np.diff(freqs)[0]

    # lets filter out values that are less than the most likely heart rate (15 bpm) and greater than 250 bpm
    # Note you can adjust this if you would like
    min_freq = int((15 / 60) / freq_spacing)
    max_freq = int((250 / 60) / freq_spacing)
    # here we will crop out half the spectrum since our signal is real
    fft_phase = fft_phase[min_freq:max_freq]
    freqs = freqs[min_freq:max_freq]

    # extract the max frequency (note, there will be noise, so this may or may not work very well
    # you might want to extract a set of max frequencies) 
    max_freq_ind = np.argpartition(fft_phase, -2)[-2:] # this prints out the last 2
    max_freq_ind = max_freq_ind[np.argsort(fft_phase[max_freq_ind])[::-1]]

    # convert from frequency to BPM
    bpm = freqs[max_freq_ind] * 60
    return fft_phase, freqs, bpm

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Configure and capture radar data from mmWave Studio.")
    parser.add_argument("--config",type=str, default='scripts/1843_config_debug_task4',help="Run the radar configuration Lua script before capturing.",)
    parser.add_argument("--exp_name",type=str, default='task4_gt',help="Run the radar configuration Lua script before capturing.",)

    return parser.parse_args()

# ----------------------------------------------------------------------------------------- #
#                                        Main function                                      #
# ----------------------------------------------------------------------------------------- #
def main(args):
    
    # you should not have to edit this
    
    exp_path = f'{current_dir}/data' 
    # the path (relative to home_dir) and name of the JSON files (exlude the .setup.json and .mmwave.json), 
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

    print("You captured %d frames, for %d TX, %d Rx, and %d adc samples" % adc_data.shape)

    ############################### process data! ################################
    rfft = scipy.fft.fft(np.squeeze(adc_data[:,0,-1,:]), axis=-1)
    range_fft_all = np.abs(np.fft.fft(np.sum(adc_data[:10,:], axis=(0,1,2)), axis=-1))

    plt.plot(abs(np.sum(rfft,axis=0)))
    plt.show(block=True)

    # You should have implemented this function in task4_vital_signs.py
    unwrapped_phase, _, max_idx = get_br_hr(range_fft_all, rfft, 0)  
    # unwrapped_phase = unwrapped_phase[3880:15410] #TODO: uncomment this if you want to zoom in on the heart rate, or change the array slicing to match your experiment

    plt.plot(unwrapped_phase)
    plt.show(block=True)

    # You should have implemented this function in task4_vital_signs.py
    fft_phase, freqs, bpm  = get_freq(unwrapped_phase, chirp_dict['periodicity'])
    
    print("BPM:", bpm)
    plt.plot(freqs[:100], fft_phase[:100]) # just look at the first 100 since the latter will most definitely be noise
    plt.show(block=True)

if __name__ == "__main__":
    args = parse_args()
    main(args)