import time

import os
import clr
from utils import utility

# helper functions
def replace_filename(lua_file, exp_name, exp_path):
    with open(lua_file, 'r') as file:
        data = file.readlines()
    for i,line in enumerate(data):
        if("capture_file=" in line.replace(' ', '')):
            data[i] = 'capture_file               =   "%s"\n' % exp_name
        if("SAVE_DATA_PATH=" in line.replace(' ', '')):
            data[i] = 'SAVE_DATA_PATH = "%s" .. capture_file .. ".bin"\n' % exp_path

    with open(lua_file, 'w') as file:
        file.writelines(data)

# radar class:
# initiates connection with mmWave Studio
# measures data
# can do processing if required later on
class radar():
    def __init__(self):
        # self.captured = False
        # self.chirp_loops = 1
        # self.num_rx = 4
        # self.num_tx = 3
        # self.samples_per_chirp = 128 
        # self.periodicity = 20
        # self.num_frames = 10
        # chirp_dict = utility.read_radar_params(lua_script)
        # self.num_rx = chirp_dict['num_rx']
        # self.num_tx = chirp_dict['num_tx']
        # self.samples_per_chirp = chirp_dict['samples_per_chirp']
        # self.periodicity = chirp_dict['periodicity']
        # self.num_frames = chirp_dict['num_frames']
        # self.chirp_loops = chirp_dict['chirp_loops']
        # self.data_rate = chirp_dict['data_rate']
        # self.freq_plot_len = chirp_dict['freq_plot_len']
        # self.range_plot_len = chirp_dict['range_plot_len']

        self.power_dict = dict()
        self.rtt_path = r'C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\Clients\RtttNetClientController\RtttNetClientAPI.dll' 
        self.RtttNetClientAPI = self.Init_RSTD_Connection(self.rtt_path)
    
    
    def Init_RSTD_Connection(self, RSTD_DLL_Path):
        RSTD_Assembly = clr.AddReference(RSTD_DLL_Path)
        import RtttNetClientAPI
        try:
            RtttNetClientAPI.RtttNetClient.IsConnected()
            Init_RSTD_Connection = 0
        except:
            Init_RSTD_Connection = 1
        if Init_RSTD_Connection:
            print('Initializing RSTD client')
            ErrStatus = RtttNetClientAPI.RtttNetClient.Init()
            if not ErrStatus == 0:
                print('Unable to initialize NetClient DLL')
                return
            print('Connecting to RSTD client')
            ErrStatus = RtttNetClientAPI.RtttNetClient.Connect('127.0.0.1',2777)
            if not ErrStatus == 0:
                print('Unable to connect to mmWaveStudio')
                print('Reopen port in mmWaveStudio. Type RSTD.NetClose() followed by RSTD.NetStart()')
                return
            time.sleep(1)

        print('Sending test message to RSTD')
        Lua_String = r'WriteToLog("Running script from Python\\n", "green")'
        ErrStatus = RtttNetClientAPI.RtttNetClient.SendCommand(Lua_String)
        if not ErrStatus == (0, None):
            print ('mmWaveStudio Connection Failed')
        else:
            print('Test message success')
        return RtttNetClientAPI

    def mmwave_config(self, script_name):
        file1 = script_name
        file2 = file1.replace("\\", "\\\\\\\\") 
        Lua_String = 'dofile("'+ file2 + '")'
        # update the lua file with new location to save the data
        ErrStatus = self.RtttNetClientAPI.RtttNetClient.SendCommand(Lua_String)
        if not ErrStatus == (0, None):
            print ('The config did not update :(')
        else:
            print('Radar configurated!')

    def mmwave_capture(self, exp_name, exp_path, script_name):
        exp_path = exp_path.replace(r"/", r"\\")
        exp_path = exp_path.replace("\\", "\\\\\\\\") + "\\\\\\\\"
        print(exp_path)
        script_name = script_name.replace("\\", "\\") 
        file1 = script_name
        file2 = file1.replace("\\", "\\\\\\\\") 
        Lua_String = 'dofile("'+ file2 + '")'
        # update the lua file with new location to save the data
        replace_filename(file1, exp_name, exp_path)
        ErrStatus = self.RtttNetClientAPI.RtttNetClient.SendCommand(Lua_String)
        if not ErrStatus == (0, None):
            print ('The frame did not get collected :(')
        else:
            print('Frame collected!')
            
