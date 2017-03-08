# RAM_FR configuration for NONSTIM SESSIONS ONLY.
# Other configuration in the main config file

# ALL SYSTEM2.0 CONFIGURATION OPTIONS

experiment = 'FR1'
stim_type = 'NO_STIM'
version = '1.0.0'
control_pc = True
heartbeat_interval = 1000

state_list = [
    'PRACTICE',
    'NON-STIM ENCODING',
    'RETRIEVAL',
    'DISTRACT',
    'INSTRUCT',
    'COUNTDOWN',
    'WAITING',
    'WORD',
    'ORIENT',
    'MIC TEST',
 ]

require_labjack = False

numSessions = 18

nBaselineTrials = 0
nStimTrials = 0
nControlTrials = 25

# %s WILL BE REPLACED BY config.LANGUAGE
wordList_dir = 'pools_%s/nonstim_lists'
