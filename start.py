# Init script to set up project
import subprocess
import sys
import ctypes
import os
import time

# PARAMS ----------------------------------------
ENV_NAME = "comm-proj"  
TASK_NAME = "run"
CONFIG_FILE = "scripts/1843_config"
CONFIG_FILE = "-- config"
TEST_NAME = "test1"  # output data fil
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
    if not is_admin():
        print("ERROR: This script MUST be run as Administrator.")
        sys.exit(1)

    run_command(f"conda activate {ENV_NAME}", "Activating Conda Environment")
    run_mmwave_studio()
    run_command("python configure.py", "Running config")
    run_command(f"python {TASK_NAME}.py --config {CONFIG_FILE} --exp_name {TEST_NAME} {EXTRA_FLAGS}", "Starting Capture Task")

if __name__ == "__main__":
    main()