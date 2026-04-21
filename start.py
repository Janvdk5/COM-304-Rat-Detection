import subprocess
import sys
import ctypes
import os
import time

###### USAGE INSTRUCTIONS ######
# NB: Can comment out mmWave Studio lauching anfd others for ease
# 1) change envirnonment name to match
# 2) select process (review old data) or realtime (stream live data)
# 3) select config file 



# PARAMS ----------------------------------------

scripts = {"task3": "scripts/1843_config_debug_task3", 
           "task3_realtime": "scripts/1843_config_streaming_task3",
           "task4": "scripts/1843_config_debug_task4",
           "task4_realtime": "scripts/1843_config_streaming_task4",
           "config": "scripts/1843_config_debug_task3",
           "highres": "scripts/1843_config_highres",
           "lowres": "scripts/1843_config_lowres",
           "highrange": "scripts/1843_config_highrange",
           "lowrange": "scripts/1843_config_lowrange"}


ENV_NAME = "comm-proj"  
TASK_NAME = "realtime"           # process (review old data), realtime (stream live data)
CONFIG_FILE = scripts["task3_realtime"]  # use dict above to select config
TEST_NAME = "task3_gt"          # output data file
EXTRA_FLAGS = ""  


# FUNCTIONS -------------------------------------
def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

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
    studio_path = r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\RunTime\mmWaveStudio.exe"
    studio_dir = r"C:\ti\mmwave_studio_02_01_01_00\mmWaveStudio\RunTime"

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
    #if not is_admin():
    #    print("ERROR: This script MUST be run as Administrator.")
    #    sys.exit(1)

    run_command(f"conda activate {ENV_NAME}", "Activating Conda Environment")

    if TASK_NAME == "realtime":
        #run_mmwave_studio()
        print("mmWave Studio now live")
    run_command("python configure.py", "Running config")


    if TASK_NAME == "process":
        run_command(f"python {TASK_NAME}.py --config {CONFIG_FILE} --exp_name {TEST_NAME} {EXTRA_FLAGS}", 
                    f"Starting Capture Task with command: ``python {TASK_NAME}.py --config {CONFIG_FILE} --exp_name {TEST_NAME} {EXTRA_FLAGS}``")
    elif TASK_NAME == "realtime":
        run_command(f"python {TASK_NAME}.py --config {EXTRA_FLAGS}", 
                    f"Starting Real-time Task with command: ``python {TASK_NAME}.py --config {EXTRA_FLAGS}``")
    else:
        print(f"Error: {TASK_NAME} not recognised")

if __name__ == "__main__":
    main()