      
import os
import numpy as np

def read_radar_params(lua_script):
    """
    Helper function that reads the radar paramters from a input lua script.
    It assumes that the lua script has the following parameters input to variables 
        (chirp loops, number rx, number tx, adc samples, periodicity, number of frames).
    Variables should be named as listed below.
    Paramters:
    - lua_script: lua configuration file
    """
    file1 = open(os.path.join(lua_script), 'r')
    Lines = file1.readlines()
    for line in Lines:
        line_ = line.replace(' ', '')
        if("CHIRP_LOOPS=" in line_):
            chirp_loops = int(line_[12:line_.find('-')].strip())
        elif("NUM_RX=" in line_):
            num_rx = int(line_[7:line_.find('-')].strip())
        elif("NUM_TX=" in line_):
            num_tx = int(line_[7:line_.find('-')].strip())
        elif("ADC_SAMPLES=" in line_):
            samples_per_chirp = int(line_[12:line_.find('-')].strip())
        elif("SAMPLE_RATE=" in line_):
            sample_rate = int(line_[12:line_.find('-')].strip()) * 1e3
        elif("FREQ_SLOPE=" in line_):
            slope = float(line_[11:line_.find('-')].strip()) * 1e12
        elif("PERIODICITY=" in line_):
            periodicity = float(line_[12:line_.find('-')].strip())
        elif("NUM_FRAMES=" in line_):
            num_frames= float(line_[11:line_.find('-')].strip())

    data_rate = int(1 / (periodicity * 0.001) / 2)
    freq_plot_len = data_rate  // 2
    range_plot_len = samples_per_chirp
    range_res = (3e8 * sample_rate) / (2 * slope * samples_per_chirp)
    chirp_dict = {}
    chirp_dict['num_rx'] = num_rx
    chirp_dict['num_tx'] = num_tx
    chirp_dict['samples_per_chirp'] = samples_per_chirp 
    chirp_dict['periodicity'] = periodicity 
    chirp_dict['num_frames'] = num_frames 
    chirp_dict['chirp_loops'] = chirp_loops 
    chirp_dict['data_rate'] = data_rate 
    chirp_dict['freq_plot_len'] = freq_plot_len 
    chirp_dict['range_plot_len'] = range_plot_len 
    chirp_dict['sample_rate'] = sample_rate
    chirp_dict['slope'] = slope
    chirp_dict['range_res'] = range_res
    return chirp_dict 


def grid_num(max_val: float, min_val: float, res: float) -> int:
    """
    Calculates the number of grid points based on the specified resolution.

    This function determines how many points fit between `min_val` and `max_val` 
    using a given resolution `res`. The result is the number of grid points that 
    can be created from `min_val` to `max_val` inclusively.

    Parameters:
    ----------
    max_val : float
        The upper bound of the grid.
    min_val : float
        The lower bound of the grid.
    res : float
        The resolution or step size between grid points.

    Returns:
    -------
    int
        The total number of grid points, including both endpoints.
    """
    if res <= 0:
        raise ValueError("Resolution 'res' must be greater than zero.")
    
    return int(round((max_val - min_val) / res)) + 1

