#!/opt/local/bin/python
#### This file contains configurations that are to be used across run scripts
#### and upload scripts. 
#### To access: import config; localIsDev = config.isDev; ...

import os

isDev    = False # Whether or not this is a development version
isSys2   = True  # Whether or not this is system 2.0 

# For right now, if it's not system2.0, we don't support it via these python scripts
if not isSys2:
    raise Exception('config.py only works with System 2.0')




############
# General settings
############

homeDir      = os.getenv('HOME')            # Home folder
localUser    = os.getenv('USER')            # Local user
remoteUser   = os.getenv('RHINO_USER')      # Rhino username (NOTE: reading from ~/.bashrc, enviornment variable )
remoteServer = 'ramtransfer.sas.upenn.edu'  # server to transfer files 
remotePort = 443
thisDir      = os.path.dirname(__file__)

# Location of the main RAM directory
RAMdir = os.path.join(thisDir, '..')
logDir = os.path.join(thisDir, '..', 'logs')

# Where the ssh key is located
sshKeyLoc = os.path.join(RAMdir, 'source', 'RAMTransfer-Keys', '%s.key'%remoteUser)
RAMrsync = 'rsync -av -e "ssh -i %(keyloc)s -p %(port)d " '%\
        {'keyloc': sshKeyLoc, 'port': remotePort}

SVNROOT='svn+ssh://RAM_exp@rhino.psych.upenn.edu/home/svn'

# Where other files get uploaded from
inProgressDir = os.path.join(homeDir, 'inProgress')

# Where transferred files go
transferredDir        = os.path.join(homeDir, 'transferred')



############
# Experiment transfer settings
############

# Path stuff
localExperimentDir    = os.path.join(RAMdir, 'data/')
#remoteExperimentDir   = '/TEST_FOLDER/'
remoteExperimentDir   = '/experiments/'
remoteExperimentPath  = '%s@%s:%s'%(remoteUser,remoteServer, remoteExperimentDir)

PCMountPoint          = os.path.join(homeDir, 'Control_PC')
PCIPAddress           = '192.168.137.1'
PCUsername            = 'OdinUser'
PCPassword            = 'MemoryExperiment'
PCSharedDir           = 'Users/OdinUser/Desktop/'#System3/SYS3_output/'

# UI stuff
expMenuOptions = {\
        'u': 'Upload experiment files',
        'e': 'Transfer EEG from Control PC',
        'c': 'Upload clinical EEG files',
        'i': 'Upload imaging',
        #'s': 'Show status of EEG data',
        'q': 'Quit'
        };

errLog = os.path.join(logDir, 'experimentError.log')
outLog = os.path.join(logDir, 'experimentOut.log')



###########
# Clinical EEG transfer settings
###########

# Path stuff
localClinicalDir = os.path.join(inProgressDir, 'clinical_eeg')
remoteClinicalDir = '/clinical_eeg/'
remoteClinicalPath = '%s@%s:%s'%(remoteUser, remoteServer, remoteClinicalDir)




##########
# Imaging transfer settings
##########

localImagingDir = os.path.join(inProgressDir, 'imaging')
remoteImagingDir = '/imaging/'
remoteImagingPath = '%s@%s:%s'%(remoteUser, remoteServer, remoteImagingDir)
