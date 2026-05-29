# COM-304-RADARS-Rat-detection
This repository contains the code for the COM-304 project on using mmWave radar for through-wall rat detection. The project focuses on developing a real-time pipeline for detecting rats in a pipe using radar data, without relying on machine learning models. Find a full explanation of the project in the final report pdf available on the repo.

## Info
### Repo structure
- `jerry_gui/` : contains the code for the GUI used to visualise the radar data and detections in real time, as well as some helper functions for the GUI.
- `scripts/` : contains the lua files to setup the radar for doppler tracking and regular streaming
- `src/` : contains the code for running the pipeline
    - `logs/` : contains the logs from the tests, including the recorded radar data and the corresponding labels
    - `configure.py` : script to update the lua config files with the correct COM port and RTT path for the current system, should be run before running the pipeline
    - `realtime.py` : script to run the real-time pipeline with the GUI, should be run after running `configure.py`
    - `start.py` : script to start everything
- `streaming_base/` : contains the base code for streaming and processing the radar data
    - `mmWave/` : contains the code fSor communicating with mmWave studio
    - `processing/` : contains the code for processing the radar data, including the detection method and the doppler tracking method
    - `streaming/` : contains the code for streaming the radar data and running the real-time pipeline
        - `realtime_streaming.py` : main code for running the real-time pipeline, including the visualisation and the detection method
        - `prod_dca.py` : This file contains the producer function for real-time data acquisition from the DCA1000 connected to the AWR1843 radar.
        - these two files involve most of the added code for this project
    - `utils/` : contains some helper functions for processing the radar data
    - `visualisation/` : contains some helper functions for visualising the radar data
- `utils` : contains various helper functions for data processing, visualisation and other tasks, used across the different branches of the repo.    


### Branches
- `main` : the main branch, with the final version used for the projec presentation, demos and all references to code in the final report. *NB: this branch is the most up to date and has the latest code, we cannot garuntee all code to be working in other branches*
- `ml/main` : branch with the ml-based approach, which was ultimately not used in the final pipeline but is still available for reference in the `data_exploration` folder. There are models for image classification as well as logistic regression, CNNs and NNs for rat classification and detection. Refer to the readme on that branch for more details.
- `deployments/no_gui` : branch with the final version of the code used for the deployment without the GUI in order to minimise latency and resource usage. Used for testing and debugging
- `deployments/v1-same-ml` : branch with the final pipeline but with a logistic regresion classifier used instead of the noise detection method.
- `Kasper` : branch used by a teammeber for testing doppler-related methods on the pipeline.

## Usage
### Prereqs
- mmWave studio and associated packages, as per the COM-304 radars tutorial for windows
- A machine running windows

### Running the code
- Clone the repo
- install the required packages from `environment.yml`
- activate the conda environment with `conda activate comm-proj`
- Then do 1 of 2 things:
    1. (recommended) 
        - Open up a terminal and mmWave studio in admin mode, let both load up.
        - Run `python configure.py` to update the lua config files with the correct COM port and RTT path for the current system.
        - run `python realtime.py --config` to start the real-time pipeline with the GUI.
        - verify the streaming is working
    2. 
        - Open up a terminal admin mode
        - Run `python start.py` to start everything
        - NB: we have had issues with this file
- *NB: use the `--doppler` flag with `realtime.py` to enable doppler motion tracking and ue the `--cfar` flag to enable the CFAR-based detection method/ Note aslo that both require the `--config` flag. So too, you an use `--exp_name "exp-name"` to record data from the test*
- now, do ` cd jerry_gui` and `python jerry_gui.py` to start the GUI, which should connect to the streaming pipeline and display the radar data and detections in real time.

Ensure to stop the streaming pipeline by closing the bf visualisation plots and use ctrl+c in the terminal, to avoid having to hard kill the process.

### Known Problems
- The streaming will timeout after about ~20s, this is expected
- Running `realtime.py` without the `--config` breaks mmWave studio for an unkown reason.