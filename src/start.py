import subprocess
import sys
import ctypes
import os
import time
import argparse



###### USAGE INSTRUCTIONS ######
# NB: Can comment out mmWave Studio lauching anfd others for ease
# 1) change envirnonment name to match
# 2) Opne MMwave Studio
# 3) python start.py 



# PARAMS ----------------------------------------
ENV_NAME =      r"C:/Users/janva/anaconda3/envs/comm-proj/python.exe" 
CONFIG_FILE =   "scripts/config_doppler"  # use dict above to select config
EXTRA_FLAGS =   ["--config", "--doppler", "--cfar"]
SRC_DIR = (os.path.dirname(os.getcwd()))


# FUNCTIONS -------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def launch(command, description):
    print(f"Starting: {description}")
    return subprocess.Popen(command, shell=True)

def run_command(command, description):
    print(f"{description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error: {e.stderr}")
        return None
    
def run_mmwave_studio():
    process_name = "mmWaveStudio.exe"
    studio_path  = r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\RunTime\mmWaveStudio.exe"
    studio_dir   = r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\RunTime"

    # Kill any existing instances
    print(f" Checking for existing {process_name}...")
   
    subprocess.run(f'taskkill /F /IM {process_name} /T >nul 2>&1', shell=True) # taken from online
    time.sleep(2)
    print("Cleaned up existing processes.")

    # Launch fresh instance
    if os.path.exists(studio_path):
        print("Launching a fresh instance of mmWave Studio...")
        subprocess.Popen([studio_path], cwd=studio_dir, shell=True)

        print("Waiting 5 seconds for initialization...")
        time.sleep(5)
    else:
        print(f"Error: Path not found: {studio_path}")

def main():
    if not is_admin():
        print("ERROR: This script MUST be run as Administrator.")
        sys.exit(1)

    radar_cmd = [
        ENV_NAME,
        os.path.join(SRC_DIR, "src/realtime.py"),
        *EXTRA_FLAGS  
    ]

    gui_cmd = [
        ENV_NAME,
        os.path.join(SRC_DIR, "jerry_gui", "jerry_gui.py"),
    ]

    #run_mmwave_studio()
    gui_proc = launch(gui_cmd, "Jerry GUI")
    radar_proc = launch(radar_cmd, "Radar pipeline")
    time.sleep(2) # let radar init 
    print("\nBoth processes running/initalising. Close this terminal or Ctrl+C to stop both.\n")

    try:
        radar_proc.wait() #wait for radar
    except KeyboardInterrupt:
        pass
    finally:
        print("Shutting down...")
        radar_proc.terminate()
        gui_proc.terminate()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    args = parser.parse_args()
    main()