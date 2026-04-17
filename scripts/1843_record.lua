capture_file               =   "lowres2"

--TODO: edit this path!!
SAVE_DATA_PATH = "D:\\\\GitHub\\\\COM-304-Rat-Detection\\\\\\\\data\\\\" .. capture_file .. ".bin"

ar1.CaptureCardConfig_StartRecord(SAVE_DATA_PATH, 1)
ar1.StartFrame()

