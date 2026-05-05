capture_file               =   "test17-labradar"

--TODO: edit this path!!
SAVE_DATA_PATH = "D:\\\\GitHub\\\\com-405-radar-tutorial\\\\data\\\\" .. capture_file .. ".bin"

ar1.CaptureCardConfig_StartRecord(SAVE_DATA_PATH, 1)
ar1.StartFrame()

