# COM-304-RADARS-RAT-DETECTION

## USAGE
- follow instructions within old/docs/radar-setup-README.md to set up radar and for reference
- navigate to src/ and run `python configure.py` to set up the radar and COM port for streaming. Follow instruction in that file to configure properly.
NB: process requires data to exist already.
- if using start script, run `python start.py` (note this file is not error free as of now)
- if not, run `python realtime.py --config` and you should get an output
- if it fails:
    - make sure mmWaveStudio is open. 
    - If mmWaveStudio was already open, kill it, go to task manager and check for any process starting with "DCA" and kill 
    - open mmWave studio again
    - follow 
 

## ISSUES
- Some of the streaming_base files refer to old diles from tutorials, eed to update this (kerim has updated version locally)
- 