# THIS FILE SETS THE CONFIGURATIONS
# FOR FR IN SYSTEM 2.0

version = "4.0.0"

# ALL SYSTEM2.0 CONFIGURATION OPTIONS
sys2 = {
    'EXPERIMENT_NAME': 'FR4',
    'STIM_TYPE': 'CLOSED_STIM',
    'VERSION_NUM': '2.04',
    'control_pc': 1,  # Will be incremented later for other control pc versions.  Set to 0 to turn off control pc processing
    'heartbeat': 1000,  # milliseconds
    'syncMeasure': False,  # If True, sync pulses are sent to the syncbox at the same time as a 'SYNC' messages to the Control PC
    'syncCount': 5,  # number of sync messages before control PC is 'synced'
    'syncInterval': 500,  # milliseconds
    'is_hardwire': True, # Should be set to 'True' in production code
    'state_list': [
        'PRACTICE',
        'STIM ENCODING',
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
}

require_labjack = False

numSessions = 10

nStimTrials = 14
nBaselineTrials = 3
nControlTrials = 8

# %s will be replaced by config.LANGUAGE
wordList_dir = 'pools_%s/stim_lists'

# Control PC options
sessionType = 'CLOSED_STIM'
