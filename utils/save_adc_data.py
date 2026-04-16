import os
import json
import utils.singlechip_raw_data_reader_example as TI

# Helper function to load and process JSON configurations
def process_json_files(root_path, chirp_dict, raw_data_dir, file_end):
    mmwave_filename = os.path.join(root_path, f'base.mmwave.json')
    setup_filename =  os.path.join(root_path, f'base.setup.json')
    
    # Load and modify MMWave JSON
    with open(mmwave_filename, 'r') as f:
        json_mmwave = json.load(f)
    json_mmwave['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']['numFrames'] = chirp_dict['num_frames']
    json_mmwave['mmWaveDevices'][0]['rfConfig']['rlProfiles'][0]['rlProfileCfg_t']['numAdcSamples'] = chirp_dict['samples_per_chirp']
    if chirp_dict['num_tx'] == 1:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['txChannelEn'] = "0x1"
    elif chirp_dict['num_tx'] == 2:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['txChannelEn'] = "0x3"
    elif chirp_dict['num_tx'] == 3:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['txChannelEn'] = "0x7"
    if chirp_dict['num_rx'] == 1:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn'] = "0x1"
    elif chirp_dict['num_rx'] == 2:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn'] = "0x3"
    elif chirp_dict['num_rx'] == 3:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn'] = "0x7"
    elif chirp_dict['num_rx'] == 4:
        json_mmwave['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn'] = "0xF"
    json_mmwave['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']['chirpEndIdx'] = chirp_dict['num_tx']-1 
    # Save changes back
    # with open(mmwave_filename, 'w') as f:
    #     json.dump(json_mmwave, f, indent=4)
    # Load and modify setup JSON
    with open(setup_filename, 'r') as f:
        json_setup = json.load(f)
    json_setup['capturedFiles']['fileBasePath'] = str(raw_data_dir)

    for i in range(1):
        json_setup['capturedFiles']['files'][i]['processedFileName'] = f"{file_end}_Raw_{i}.bin"
        json_setup['capturedFiles']['files'][i]['rawFileName'] = f"{file_end}_Raw_{i}.bin"
    # json_setup['mmWaveDeviceConfig']['radarSSFirmware'] = str(root_path / 'radar_config/rf_eval_firmware/radarss/xwr18xx_radarss.bin')
    # json_setup['mmWaveDeviceConfig']['masterSSFirmware'] = str(root_path / 'radar_config/rf_eval_firmware/masterss/xwr18xx_masterss.bin')
    # Save changes back
    # with open(setup_filename, 'w') as f:
    #     json.dump(json_setup, f, indent=4) 
    return json_mmwave, json_setup, mmwave_filename, setup_filename