import os
import sys
import argparse
import numpy as np

sys.path.append(os.path.dirname(os.getcwd())) # one level up for this repo

from utils.radar import radar # this contains helper functions to interact with the radar from Python (after opening up mmWave studio)
from utils.read_com import find_com_port
import utils.utility as utility

from streaming_base.streaming import realtime_streaming_task3
from streaming_base.streaming import realtime_streaming_track

'''
    The primary things to change in this file are paths to various locations on your computer (mainly inside this repo itself) at the bototm of this file.
    Technically, you do not have to change anything this this file other thatn those paths (so that we can extract chirp parameters correctly and so on).
    This file is for runing REALTIME code to display a 2D heatmap using your function: beamform_2d.
    Goal of this task: debug run your code in real time!

    based on the code in old/task3_tracking_realtime.py
'''

current_dir = (os.path.dirname(os.getcwd())) # one level up for this repo

def main(cfar_on, exp_name="test", save_raw_dt=False, doppler=False, track=False):
    """
    Main function to start the real-time radar streaming and processing.
    """

    # Parameters for the range-azimuth beamforming.
    # Range-gate to ~1.5 m: the rat lives in the inner part of the FOV, so
    # there's no point beamforming over bins out to 5+ m and having the
    # per-frame normalization pull the rat's brightness down.
    _max_bin = max(8, int(1.5 / chirp_dict['range_res']))
    r_idxs = np.arange(0, min(_max_bin, chirp_dict['samples_per_chirp']), 1)

    # r_idxs = np.arange(0, 64, 1)

    phi = np.deg2rad(np.arange(0, 180, 1))
    width =  len(r_idxs) ## 100 # 100 # azimuth width in degrees

    # Radar  parameters
    # Frame period (s) for GTrack Kalman dt — must match PERIODICITY in the Lua file (ms).
    frame_dt_s = float(chirp_dict["periodicity"]) * 1e-3

    cfg_radar = {
        "range_idx": r_idxs,
        "phi": phi,
        "width": width,
        "n_radar": 1,
        "num_tx": chirp_dict['num_tx'],
        "num_rx": chirp_dict['num_rx'],
        "num_doppler": chirp_dict['chirp_loops'],
        "samples_per_chirp": chirp_dict['samples_per_chirp'],
        "sample_rate": chirp_dict['sample_rate'],
        "c": 3e8,
        "lm": 3e8 / 77e9,
        "slope": chirp_dict['slope'],
        "range_res": chirp_dict['range_res'],           # NOTE : I ADDED THIS -- 4/20/2026 - KERIM
        "dt": frame_dt_s,
        "save_raw_dt": save_raw_dt,
        "exp_name": exp_name,
        "exp_path": os.path.join(current_dir, "data"),   # NOTE : Data Directory Path (for specified experiment file)
        "doppler" : doppler
    }

    # Parameters for CFAR
    cfg_cfar = {
        "cfar_on": cfar_on,
        "bg_sub": not doppler,  # subtract previous-frame range FFT to kill static clutter (pipe walls, floor, etc.)
        "num_train_r": 10,
        "num_train_d": 10,
        "num_guard_r": 4,
        "num_guard_d": 2,
        # CFAR rate_fa. Lower = stricter (fewer detections), higher = looser.
        # Default 1e-3 is fine for humans; small / low-RCS targets need looser.
        "threshold_scale": 1e-2 if track else 1e-1,
        # 'legacy'  -> Kasper's Doppler+notch -> dense beamform -> optional post-beamform CFAR
        # 'tracking' -> motion-dense beamform + GTrack (see prod_dca tracking branch).
        "pipeline": "tracking" if track else "legacy",
        # Number of Doppler bins to suppress around DC in tracking mode (0 = off).
        # Small/slow targets get killed by a wide notch; +/- 1 bin is a safer default.
        "doppler_notch_bins": 1,
    }
    # In tracking mode: bg_sub, motion-style post-beamform CFAR, and Doppler notch like legacy --doppler.
    if track:
        cfg_cfar["bg_sub"] = True
        cfg_cfar["cfar_on"] = True
        n_dop = int(chirp_dict["chirp_loops"])
        if n_dop < 8:
            print(
                f"WARNING: CHIRP_LOOPS={n_dop} in Lua — increase to >=8 (e.g. 16) in mmWave for "
                "usable Doppler / tracking. See scripts/config_doppler.lua (used automatically with --track)."
            )
            cfg_cfar["doppler_notch_bins"] = 0
        else:
            cfg_cfar["doppler_notch_bins"] = max(cfg_cfar.get("doppler_notch_bins", 2), 2)

    print("Starting streaming...")

    if track:
        # GTrack-wired consumer with PresenceZone2D for "rat in pipe".
        realtime_streaming_track.main(cfg_radar, cfg_cfar)
    else:
        # Legacy pipe-ROI EMA consumer.
        realtime_streaming_task3.main(cfg_radar, cfg_cfar)

if __name__ == "__main__":


    #   PARSER --------------------------------------------------------------------------------------------------------
    parser = argparse.ArgumentParser(description="Example script with command line arguments.")

    # Add arguments
    parser.add_argument("--config",  action="store_true", help="True if you want to configure the radar from python.")
    parser.add_argument("--cfar", action="store_true", help="True if you want cfar.")
    parser.add_argument("--doppler", action="store_true", help="True if you want doppler.")
    parser.add_argument("--save_raw_dt", action="store_true", help="True if you want to save the real-time captured raw data to 'data/<exp_name>_Raw_0.bin'.")
    parser.add_argument("--exp_name", type=str, default="test", help="Base filename for saved raw data")
    parser.add_argument("--track", action="store_true", help="GTrack + motion-dense beamform (Doppler-style); uses config_doppler.lua when no --doppler. Implies bg_sub and post-CFAR defaults.")

    args = parser.parse_args()
    #   ---------------------------------------------------------------------------------------------------------------
    if args.doppler or args.track:
        config_lua_script = f'{current_dir}/scripts/config_doppler.lua'
    else:
        config_lua_script = f'{current_dir}/scripts/1843_config_streaming_task3.lua'
    
    # this function reads the parameters from your lua config file (look at this function to see how it expects your config file to be formatted)
    # num_rx, num_tx, samples_per_chirp, periodicity, num_frames, chirp_loops, _, _, _
    chirp_dict = utility.read_radar_params(config_lua_script)

    if args.config:
        radar1 = radar()
        radar1.mmwave_config(config_lua_script)
    main(args.cfar, args.exp_name, args.save_raw_dt, args.doppler, args.track)
