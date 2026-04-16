import json
from scipy.signal.windows import hann, blackman, boxcar
import numpy as np
import os
import scipy.io as sio
import math

# Global parameters
class TI_PROCESSOR():
    def __init__(self):
        # Start MATLAB engine

        self.dataSet = {}
        self.Params = {}

    def rawDataReader(self, setupJSON, mmwaveJSON, rawDataFileName, radarCubeDataFileName):

        # print(f"mmwave Device: {setupJSON['mmWaveDevice']}")

        # Read bin file names
        binFilePath = setupJSON['capturedFiles']['fileBasePath']
        binFiles = setupJSON['capturedFiles']['files']
        numBinFiles = len(binFiles)
        if numBinFiles < 1:
            raise ValueError("Bin File is not available")

        self.Params['numBinFiles'] = numBinFiles
        binFileNames = [
            os.path.join(binFilePath, file['processedFileName']) for file in binFiles
        ]

        # Generate ADC data parameters
        adcDataParams = self.dp_generateADCDataParams(mmwaveJSON)

        # Generate radar cube parameters
        radarCubeParams = self.dp_generateRadarCubeParams(mmwaveJSON)

        # Generate RF parameters
        self.Params['RFParams'] = self.dp_generateRFParams(mmwaveJSON, radarCubeParams, adcDataParams)
        self.Params['NSample'] = adcDataParams['numAdcSamples']
        self.Params['NChirp'] = adcDataParams['numChirpsPerFrame']
        self.Params['NChan'] = adcDataParams['numRxChan']
        self.Params['NTxAnt'] = radarCubeParams['numTxChan']
        self.Params['numRangeBins'] = radarCubeParams['numRangeBins']
        self.Params['numDopplerBins'] = radarCubeParams['numDopplerChirps']
        self.Params['rangeWinType'] = 0

        # Validate configuration
        validConf = self.dp_validateDataCaptureConf(setupJSON, mmwaveJSON)
        if not validConf:
            raise ValueError("Configuration from JSON file is not valid")

        # Open raw data from file
        self.Params['NFrame'] = 0
        self.Params['fid_rawData'] = []
        self.Params['NFramePerFile'] = []

        for idx, fileName in enumerate(binFileNames):
            try:
                fid = open(fileName, 'rb')
                self.Params['fid_rawData'].append(fid)
            except IOError as e:
                print(f"Cannot open Bin file {fileName}, - {e}")
                raise RuntimeError("Quit with error")

            try:
                frameCount = self.dp_getNumberOfFrameFromBinFile(fileName)
                if frameCount == 0:
                    raise ValueError("Not enough data in binary file")
                self.Params['NFramePerFile'].append(frameCount)
                self.Params['NFrame'] += frameCount
            except Exception as e:
                raise RuntimeError(f"Failed to read frames from {fileName}: {e}")

        # Export data
        return self.dp_exportData(rawDataFileName, radarCubeDataFileName)

        # # Close file handles
        # for fid in self.Params['fid_rawData']:
        #     fid.close()


    def dp_exportData(self, rawDataFileName, radarCubeDataFileName):
        # global dataSet, Params

        # rawADCData = []
        # radarCubeData = []
        rawData = []

        # Prepare data for all frames
        if rawDataFileName or radarCubeDataFileName:
            for frameIdx in range(1, self.Params['NFrame'] + 1):
                self.dp_updateFrameData(frameIdx)  # This must populate `dataSet`

                # Store per-frame data
                # rawADCData.append(self.dataSet['rawDataUint16'])              # Should be np.uint16
                # radarCubeData.append(self.dataSet['radarCubeData'].astype(np.complex64))
                rawData.append(self.dataSet['rawFrameData'].astype(np.complex64))

        # Export raw ADC data
        # if rawDataFileName:
        #     adcRawData = {
        #         'rfParams': self.Params['RFParams'],
        #         'data': rawADCData,
        #         'dim': {
        #             'numFrames': self.Params['NFrame'],
        #             'numChirpsPerFrame': self.Params['adcDataParams']['numChirpsPerFrame'],
        #             'numRxChan': self.Params['NChan'],
        #             'numSamples': self.Params['NSample'],
        #         }
        #     }
            # sio.savemat(rawDataFileName, {'adcRawData': adcRawData}, do_compression=True)

        # Export radar cube data
        # if radarCubeDataFileName:
        radarCubeParams = self.Params['radarCubeParams']
        radarCube = {
            'rfParams': self.Params['RFParams'],
            'data_raw': rawData,
            'dim': {
                'numFrames': self.Params['NFrame'],
                'numChirps': radarCubeParams['numTxChan'] * radarCubeParams['numDopplerChirps'],
                'numRxChan': radarCubeParams['numRxChan'],
                'numRangeBins': radarCubeParams['numRangeBins'],
                'iqSwap': radarCubeParams['iqSwap']
            }
        }
        return rawData, 
            # sio.savemat(radarCubeDataFileName, {'radarCube': radarCube}, do_compression=True)

    def dp_updateFrameData(self, frameIdx):
        # global Params, dataSet

        # Find correct bin file index for the given frame
        currFrameIdx = 0
        fidIdx = -1
        for idx in range(self.Params['numBinFiles']):
            if frameIdx <= (self.Params['NFramePerFile'][idx] + currFrameIdx):
                fidIdx = idx
                break
            else:
                currFrameIdx += self.Params['NFramePerFile'][idx]

        if fidIdx < self.Params['numBinFiles']:
            # Load one frame of complex raw data
            rawDataComplex = self.dp_loadOneFrameData(
                self.Params['fid_rawData'][fidIdx],
                self.Params['dataSizeOneFrame'],
                frameIdx - currFrameIdx
            )

            # Store rawDataUint16 as uint16 view of raw data
            self.dataSet['rawDataUint16'] = rawDataComplex.astype(np.uint16)

            # Adjust time domain data to signed int16
            timeDomainData = rawDataComplex.copy()
            timeDomainData[rawDataComplex >= 2**15] -= 2**16

            # Pass time-domain frame to generator (reshaping, etc.)
            self.dp_generateFrameData(timeDomainData)

            # Run range FFT processing chain
            # self.dataSet['radarCubeData'] = self.processingChain_rangeFFT(self.Params['rangeWinType'])


    def dp_getNumberOfFrameFromBinFile(self, binFileName):
        # global Params

        try:
            fileSize = os.path.getsize(binFileName)
        except Exception as e:
            raise RuntimeError(f"Reading bin file failed: {e}")

        NFrame = math.floor(fileSize / self.Params['dataSizeOneFrame'])
        return NFrame

    def dp_loadOneFrameData(self, fid_rawData, dataSizeOneFrame, frameIdx):
        """
        Load one frame of raw ADC data from binary file.
        
        Args:
            fid_rawData: File object opened in 'rb' mode.
            dataSizeOneFrame: Size of one frame in bytes.
            frameIdx: Frame index (1-based).
        
        Returns:
            rawData (np.ndarray): One frame of raw ADC data as float32.
        """
        # Seek to the correct position (0-based index)
        offset = (frameIdx - 1) * dataSizeOneFrame
        fid_rawData.seek(offset)

        try:
            # Read data as uint16 and convert to float32
            rawData = np.frombuffer(fid_rawData.read(dataSizeOneFrame), dtype=np.uint16).astype(np.float32)
        except Exception as e:
            raise RuntimeError(f"Error reading binary file: {e}")

        if len(rawData) * 2 != dataSizeOneFrame:
            raise ValueError(f"dp_loadOneFrameData: read {len(rawData)} uint16s, expected {dataSizeOneFrame // 2}")

        return rawData

    def dp_numberOfEnabledChan(self, laneEn):
        """Returns the number of enabled LVDS lanes from laneEn bitmask (e.g., 0xF -> 4 lanes)."""
        return bin(laneEn).count('1')

    def dp_validateDataCaptureConf(self, setupJson, mmwaveJSON):
        """
        Validates the radar capture configuration.

        Args:
            setupJson (dict): Parsed setup JSON config.
            mmwaveJSON (dict): Parsed mmWave JSON config.
            Params (dict): Global parameters dict (mutable).
        
        Returns:
            confValid (bool): True if configuration is valid.
        """
        mmWaveDevice = setupJson['mmWaveDevice']
        confValid = True

        # Check capture hardware
        if setupJson['captureHardware'] != 'DCA1000':
            print(f"Capture hardware is not supported: {setupJson['captureHardware']}")
            confValid = False

        # Check raw data format
        transferFmtPkt0 = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevDataPathCfg_t']['transferFmtPkt0']
        if transferFmtPkt0 != '0x1':
            print(f"Capture data format is not supported: {transferFmtPkt0}")
            confValid = False

        # Check logging mode
        if setupJson['DCA1000Config']['dataLoggingMode'] != 'raw':
            print(f"Capture data logging mode is not supported: {setupJson['DCA1000Config']['dataLoggingMode']}")
            confValid = False

        # Check LVDS lane and interleave mode
        laneEnHex = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevLaneEnable_t']['laneEn']
        laneEn = int(laneEnHex, 16)
        self.Params['numLane'] = self.dp_numberOfEnabledChan(laneEn)
        self.Params['chInterleave'] = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevDataFmtCfg_t']['chInterleave']

        if mmWaveDevice in ['awr1443', 'iwr1443', 'awr1243', 'iwr1243']:
            if self.Params['numLane'] != 4:
                print(f"{self.Params['numLane']} LVDS Lane is not supported for device: {mmWaveDevice}")
                confValid = False
            if self.Params['chInterleave'] != 0:
                print(f"Interleave mode {self.Params['chInterleave']} is not supported for device: {mmWaveDevice}")
                confValid = False
        else:
            if self.Params['numLane'] != 2:
                print(f"{self.Params['numLane']} LVDS Lane is not supported for device: {mmWaveDevice}")
                confValid = False
            if self.Params['chInterleave'] != 1:
                print(f"Interleave mode {self.Params['chInterleave']} is not supported for device: {mmWaveDevice}")
                confValid = False

        return confValid


    def dp_generateFrameData(self, rawData):
        """
        Reshape raw ADC data based on capture configuration.

        Args:
            rawData (np.ndarray): Raw ADC data as float32.
            Params (dict): Parameters including numLane, interleave, etc.
            dataSet (dict): Global structure to store frame output.

        Returns:
            frameData (np.ndarray): Reshaped raw data.
        """
        # Step 1: Reshape based on LVDS lanes
        if self.Params['numLane'] == 2:
            frameData = self.dp_reshape2LaneLVDS(rawData)
        # elif self.Params['numLane'] == 4:
        #     frameData = self.dp_reshape4LaneLVDS(rawData)
        else:
            raise ValueError(f"{self.Params['numLane']} LVDS lane is not supported.")

        # Step 2: IQ Swap if required (Re-Im → Im-Re)
        # if self.Params['adcDataParams']['iqSwap'] == 1:
        #     frameData[:, [0, 1]] = frameData[:, [1, 0]]

        # Step 3: Convert to complex (column 0 = Imag, column 1 = Real)
        frameCplx = frameData[:, 0] + 1j * frameData[:, 1]

        NChirp = self.Params['NChirp']
        NChan = self.Params['NChan']
        NSample = self.Params['NSample']

        # Step 4: Initialize final 3D cube
        frameComplex = np.zeros((NChirp, NChan, NSample, ), dtype=np.complex64)

        # Step 5: Deinterleave based on channel format
        temp = frameCplx.reshape((NSample * NChan,NChirp), order='F').T

        if self.Params['chInterleave'] == 1:
            # Channel-major (non-interleaved)
            for chirp in range(NChirp):
                reshaped = temp[chirp].reshape((NSample,NChan), order='F').T
                frameComplex[chirp, :, :] = reshaped
        else:
            # Sample-major (interleaved)
            for chirp in range(NChirp):
                reshaped = temp[chirp].reshape((NSample, NChan), order='F').T
                frameComplex[chirp, :, :] = reshaped

        # Save result to global dataSet
        self.dataSet['rawFrameData'] = frameComplex

        return frameData

    def dp_numberOfEnabledChan(self, chanMask):
        """
        Counts the number of enabled channels from a bitmask.

        Args:
            chanMask (int): Bitmask representing enabled channels (e.g., 0b1111 for 4 channels).

        Returns:
            int: Number of enabled channels.
        """
        MAX_RXCHAN = 4
        count = 0

        for chan in range(MAX_RXCHAN):
            bitVal = 1 << chan
            if (chanMask & bitVal) == bitVal:
                count += 1
                chanMask -= bitVal
                if chanMask == 0:
                    break

        return count

    def dp_generateADCDataParams(self, mmwaveJSON):
        # global Params

        frameCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']

        adcDataParams = {}
        adcDataParams['dataFmt'] = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlAdcOutCfg_t']['fmt']['b2AdcOutFmt']
        adcDataParams['iqSwap'] = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevDataFmtCfg_t']['iqSwapSel']
        adcDataParams['chanInterleave'] = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevDataFmtCfg_t']['chInterleave']
        adcDataParams['numChirpsPerFrame'] = frameCfg['numLoops'] * (frameCfg['chirpEndIdx'] - frameCfg['chirpStartIdx'] + 1)
        adcDataParams['adcBits'] = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlAdcOutCfg_t']['fmt']['b2AdcBits']

        rxChanMaskStr = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']['rxChannelEn']
        rxChanMask = int(rxChanMaskStr, 16)  # Convert '0x' string to integer
        adcDataParams['numRxChan'] = self.dp_numberOfEnabledChan(rxChanMask)

        adcDataParams['numAdcSamples'] = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlProfiles'][0]['rlProfileCfg_t']['numAdcSamples']

        # dp_printADCDataParams(adcDataParams)

        # Determine ADC sample size
        if adcDataParams['adcBits'] == 2:
            if adcDataParams['dataFmt'] == 0:
                # Real data: 16 bits (2 bytes)
                gAdcOneSampleSize = 2
            elif adcDataParams['dataFmt'] in [1, 2]:
                # Complex data: 32 bits (4 bytes)
                gAdcOneSampleSize = 4
            else:
                raise ValueError('Unsupported ADC dataFmt: {}'.format(adcDataParams['dataFmt']))
        else:
            raise ValueError('Unsupported ADC bits: {}'.format(adcDataParams['adcBits']))

        dataSizeOneChirp = gAdcOneSampleSize * adcDataParams['numAdcSamples'] * adcDataParams['numRxChan']

        self.Params['dataSizeOneChirp'] = dataSizeOneChirp
        self.Params['dataSizeOneFrame'] = dataSizeOneChirp * adcDataParams['numChirpsPerFrame']
        self.Params['adcDataParams'] = adcDataParams

        return adcDataParams

    def dp_generateRadarCubeParams(self, mmwaveJSON):
        # global Params

        frameCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']
        profileCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlProfiles'][0]['rlProfileCfg_t']
        chanCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlChanCfg_t']
        dataFmtCfg = mmwaveJSON['mmWaveDevices'][0]['rawDataCaptureConfig']['rlDevDataFmtCfg_t']

        radarCubeParams = {}

        radarCubeParams['iqSwap'] = dataFmtCfg['iqSwapSel']

        rxChanMaskStr = chanCfg['rxChannelEn']
        rxChanMask = int(rxChanMaskStr, 16)
        radarCubeParams['numRxChan'] = self.dp_numberOfEnabledChan(rxChanMask)

        radarCubeParams['numTxChan'] = frameCfg['chirpEndIdx'] - frameCfg['chirpStartIdx'] + 1

        numAdcSamples = profileCfg['numAdcSamples']
        radarCubeParams['numRangeBins'] = int(2 ** np.ceil(np.log2(numAdcSamples)))

        radarCubeParams['numDopplerChirps'] = frameCfg['numLoops']

        # Radar Cube Format: 1 means [chirps][rx][range]
        radarCubeParams['radarCubeFmt'] = 1  # Equivalent to RADAR_CUBE_FORMAT_1

        # dp_printRadarCubeParams(radarCubeParams)

        self.Params['radarCubeParams'] = radarCubeParams
        return radarCubeParams

    def dp_generateRFParams(self, mmwaveJSON, radarCubeParams, adcDataParams):
        C = 3e8  # Speed of light in m/s
        profileCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlProfiles'][0]['rlProfileCfg_t']
        frameCfg = mmwaveJSON['mmWaveDevices'][0]['rfConfig']['rlFrameCfg_t']

        RFParams = {}

        # Start frequency in GHz
        RFParams['startFreq'] = profileCfg['startFreqConst_GHz']

        # Frequency slope in MHz/us
        RFParams['freqSlope'] = profileCfg['freqSlopeConst_MHz_usec']

        # ADC sampling rate in Msps
        RFParams['sampleRate'] = profileCfg['digOutSampleRate'] / 1e3

        # Derived parameters
        RFParams['numRangeBins'] = int(2 ** np.ceil(np.log2(adcDataParams['numAdcSamples'])))
        RFParams['numDopplerBins'] = radarCubeParams['numDopplerChirps']

        # Bandwidth in GHz
        RFParams['bandwidth'] = abs(RFParams['freqSlope'] * profileCfg['numAdcSamples'] / profileCfg['digOutSampleRate'])

        # Range resolution in meters
        RFParams['rangeResolutionsInMeters'] = (
            C * RFParams['sampleRate'] /
            (2 * RFParams['freqSlope'] * RFParams['numRangeBins'] * 1e6)
        )

        # Doppler resolution in m/s
        idleTime_sec = profileCfg['idleTimeConst_usec'] * 1e-6
        rampEndTime_sec = profileCfg['rampEndTime_usec'] * 1e-6
        RFParams['dopplerResolutionMps'] = (
            C /
            (2 * RFParams['startFreq'] * 1e9 *
            (idleTime_sec + rampEndTime_sec) *
            radarCubeParams['numDopplerChirps'] * radarCubeParams['numTxChan'])
        )

        # Frame periodicity in milliseconds
        RFParams['framePeriodicity'] = frameCfg['framePeriodicity_msec']

        return RFParams

    def dp_reshape2LaneLVDS(self, rawData):
        """
        Reshape raw ADC data from 2-lane LVDS capture into I/Q frame format.

        Args:
            rawData (np.ndarray): 1D numpy array of raw ADC samples (uint16 or int16)

        Returns:
            frameData (np.ndarray): 2D array of shape (N, 2) where column 0 is I, column 1 is Q
        """
        rawData = np.asarray(rawData)

        # Reshape into 4 rows: each column corresponds to one IQ sample pair in 2-lane format

        rawData4 = rawData.reshape((4, -1), order='F')  # MATLAB-style column-major reshape

        rawDataI = rawData4[0:2, :].reshape(-1, order='F')
        rawDataQ = rawData4[2:4, :].reshape(-1, order='F')

        # Combine into two-column IQ frame
        frameData = np.stack((rawDataI, rawDataQ), axis=1)

        return frameData

    # def dp_reshape4LaneLVDS(self, rawData):
    #     """
    #     Reshape raw ADC data from 4-lane LVDS capture into I/Q frame format.

    #     Args:
    #         rawData (np.ndarray): 1D numpy array of raw ADC samples (uint16 or int16)

    #     Returns:
    #         frameData (np.ndarray): 2D array with shape (N, 2), column 0 is I, column 1 is Q
    #     """
    #     rawData = np.asarray(rawData)
    #     rawData8 = rawData.reshape(8, -1)  # Shape: (8, N)

    #     # I samples from first 4 rows, Q samples from last 4 rows
    #     rawDataI = rawData8[0:4, :].reshape(-1, order='F')  # column-wise flattening
    #     rawDataQ = rawData8[4:8, :].reshape(-1, order='F')

    #     frameData = np.stack((rawDataI, rawDataQ), axis=1)
    #     return frameData

