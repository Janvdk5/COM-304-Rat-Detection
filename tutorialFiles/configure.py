import os
import argparse
from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
from utils.read_com import list_files, find_com_port, update_com_port_in_file, find_rtt_dll, update_rtt_path_in_file

current_dir = os.getcwd()

# update COM port automatically in all lua files
lua_files = list_files(f'{current_dir}/scripts')
com_number = find_com_port("Application") 
for lua_script in lua_files:
    print(lua_script)
    update_com_port_in_file(lua_script, com_number)