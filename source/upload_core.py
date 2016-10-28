#!/opt/local/bin/python
##### The purpose of this script is to provide an interface to copy files over rsync
##### both from the control PC to the task laptop (for system2.0) and from the task
##### laptop to ramtransfer

import config
import sys, tty, os, termios, subprocess, time, urllib2, datetime, shutil


def chooseFromListbox(contents, prompt = '', multiSelect = True):
    """
    Makes an applescript listbox
    """
    if len(prompt) != 0:
        prompt = 'with prompt \\"%s\\"'%prompt

    if multiSelect:
        multiSelect = 'with multiple selections allowed'
    else:
        multiSelect = ''

    formattedContents = ['\\"%s\\"'%x for x in contents]
    appleCmd = 'set myList to {%s}\nchoose from list myList %s %s'%\
            (', '.join(formattedContents), prompt, multiSelect)
    
    output = execCmd('osascript -e "%s"'%appleCmd).strip()
    if output == 'false':
        return False
    elif ',' in output:
        return output.split(', ')
    else:
        return [output]


def enterNameInDialog(prompt = '', defaultAnswer = ''):
    """
    Makes an applescript dialog and returns the value entered in it
    """
    appleCmd = 'set output to the text returned of (display dialog \\"%s\\" default answer \\"%s\\")'%\
            (prompt, defaultAnswer)

    output = execCmd('osascript -e "%s"'%appleCmd).strip()

    if output == '':
        return None
    else:
        return output

def selectFile(prompt = '', fileOnly = True):
    """
    Makes an applescript file selection box to select files or folders
    Selects only files if fileOnly==True, otherwise only folders
    """
    
    appleCmd = 'tell application \\"Finder\\" \n'+\
               'set frontmost to true \n'+\
               'set output to choose %s with prompt '%('file' if fileOnly else 'folder')+\
               '\\"%s\\" invisibles false multiple selections allowed true \n'%prompt+\
               'set output to POSIX path of output \n'+\
               'end tell'

    output = execCmd('osascript -e "%s"'%appleCmd).strip()

    if output == 'false':
        return False
    else:
        return output

def keyToFn(key):
    """
    Maps a character to a function
    """

    # Each of these functions must return true/false 
    # for whether to return to the main menu
    fnMap = {\
        'u' : uploadFiles_option,
        'e' : transferEEG_option,
        'c' : addClinical_option,
        'v' : viewFilesToUpload_option,
        's' : showStatus_option,
        'i' : uploadImaging_option,
        'q' : quitProgram_option,
        }
    
    if key in fnMap:
        return fnMap[key]
    else:
        return None

def clear():
    """
    Clears the terminal window
    """
    sys.stderr.write('\x1b[2J\x1b[H')

def getCh():
    """
    Gets a single character from stdin
    (taken from: http://stackoverflow.com/questions/510357/python-read-a-single-character-from-the-user)
    """
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch

def execCmd(cmdToExec, returnOutput = True, returnCode = False, suppressErr = False, suppressOutput = False):
    """
    Executes a command and returns the output as a variable
    accepts:
        returnOuptut - Suppresses output and returns it to the calling function
        returnCode   - Returns the "return code" of the call instead of output
                       (overridden by returnOutput
        suppressErr - if False (default) shows stdErr, otherwise pipes it to /dev/null
        suppressOutput - if False (default) shows stdOut (cannot be used with returnOutput)
    """
    opts = {'shell': True, 'universal_newlines':True};
    if suppressErr:
        if not os.path.exists(os.path.dirname(config.errLog)):
            os.makedirs(os.path.dirname(config.errLog))
        errRedirect = open(config.errLog, 'w')
        opts['stderr'] = errRedirect
    if returnOutput:
        opts['stdout'] = subprocess.PIPE
    elif suppressOutput:
        if not os.path.exists(os.path.dirname(config.outLog)):
            os.makedirs(os.path.dirname(config.outLog))
        outRedirect = open(config.outLog, 'w')
        opts['stdout'] = outRedirect

    
    if returnOutput:
        proc = subprocess.Popen(cmdToExec, **opts)
        return proc.communicate()[0]
    if returnCode and not suppressOutput:
        retCode = subprocess.call(cmdToExec, **opts)
        return retCode
    if returnCode:
        proc = subprocess.Popen(cmdToExec, **opts)
        return proc.returncode
    subprocess.Popen(cmdToExec, **opts)

def line(lineChar = '-', numChars = 40):
    """
    Prints out a line of characters ('-') a bunch of times (25)
    """
    print(lineChar*numChars)

def showMenu(options):
    """
    Shows an arbitrary menu of options
        Key1   :   What key1 does
        Key2   :   What key2 does
        ...
    """

    # Hah. Double meaning, get it? The "key" is a "key"? I'm hillarious. 
    for key in options:
        print('%s -- %s'%(key, options[key]))

def mainMenu(options = None):
    """
    The main menu for the program. Gives options for what the user can do.
    Accepts:
        options  ---  Dictionary of keys and labels
                      [optional: defailts to config.expMenuOptions]
    Returns:
        key pressed (must be in options)
    """

    if not options:
        options = config.expMenuOptions
        
    # Make the menu:
    line()
    print('Press one of the following keys to continue...')
    showMenu(options)
    line()

    key = None
    while not key in options.keys():
        key = getCh()

    return key

def hasInternetConnection(url = 'http://www.google.com'):
    """
    Checks to see if internet connection is active by pinging a website
    (google, by default)

    returns: 
        True if has connection, False otherwise
    """
    try:
        _ = urllib2.urlopen(url, timeout = 5)
        return True
    except :
        pass
    return False


def checkInternetConnection(url = 'http://www.google.com'):
    """
    Wrapper to provide interface for hasInternetConnection
    """
    print('Checking internet connection...')
    while not hasInternetConnection(url):
        line('*')
        print('    NO INTERNET CONNECTION !    ')
        print('     HIT ANY KEY TO RETRY')
        line('*')
        getCh()
        print('Checking internet connection...')
    print('Internet connection verified.')

def splitPath(path):
    """
    Splits a path into a list of its directories
    """
    pathParts = []
    while len(path)>1:
        [path, tail] = os.path.split(path)
        pathParts.append(tail)

    # Reverse at the end to return in the correct order
    return pathParts[::-1]

def getDataIndex(pathParts, rootDir = 'data'):
    """
    If path is in list split by /, returns the index of the 
    core RAM data directory
    """
    
    if rootDir[-1] == '/':
        rootBase = os.path.basename(rootDir[:-1])
    else:
        rootBase = os.path.basename(rootDir)

    for i, pathPart in enumerate(pathParts):
        if pathPart == rootBase:
            return i
    return None

def getSess(dataPath, rootDir = 'data'):
    """
    Returns the session number from a full data path
    """
    pathParts = splitPath(dataPath)
    dataIndex = getDataIndex(pathParts, rootDir)
    
    # Session is three folders down from the base path
    sessIndex = dataIndex + 3

    if sessIndex >=len(pathParts):
        return None
    else:
        return pathParts[sessIndex]

def getSubj(dataPath, rootDir = 'data'):
    """
    Returns the subject code from ta full data path
    """
    pathParts = splitPath(dataPath)
    dataIndex = getDataIndex(pathParts, rootDir)

    # Experiment is one folder down from base path
    subjIndex = dataIndex + 2

    if subjIndex >= len(pathParts):
        return None
    else:
        return pathParts[subjIndex]



def getExp(dataPath, rootDir = 'data'):
    """
    Returns the experiment name from a full data path
    """
    pathParts = splitPath(dataPath)
    dataIndex = getDataIndex(pathParts, rootDir)

    # Experiment is one folder down from base path
    expIndex = dataIndex + 1

    if expIndex >= len(pathParts):
        return None
    else:
        return pathParts[expIndex]


def moveEEGToTransferred():
    """
    Moves all EEG files in the data directory to the transferred folder
    """
    EEGSessFolders = getSessionsWithEEG()
    for EEGSessFolder in EEGSessFolders:
        sess = getSess(EEGSessFolder)
        subj = getSubj(EEGSessFolder)
        exp  = getExp(EEGSessFolder)
        if not os.path.exists(os.path.join(config.transferredDir, exp, subj, sess)):
            os.makedirs(os.path.join(config.transferredDir, exp, subj, sess))
        EEGFolder = os.path.join(EEGSessFolder, 'eeg')
        os.rename(EEGFolder, os.path.join(config.transferredDir, exp, subj, sess, 'eeg', ''))
   
def moveToTransferred(inProgDir, subject):
    """
    Moves a subject's clinical files into the transferred directory
    """
    origin = os.path.join(inProgDir, subject, '')
    subjFolder = os.path.join(config.transferredDir, subject)
    try:
        os.makedirs(subjFolder)
    except:
        pass
    destination = os.path.join(subjFolder, str(datetime.date.today()), '')

    # Rsync origin to destination
    rsyncCmd = 'rsync -a %s %s'%(origin, destination)
    execCmd(rsyncCmd, suppressOutput = True)

    # Remove origin
    shutil.rmtree(origin, True)

def gshredSingleFile(fileToShred):
    """
    Shreds a single file
    """
    print('Deleting file: %s'%fileToShred)
    if not os.path.isfile(fileToShred):
        os.system('find \'%s\' -type f  -exec gshred -vu \'{}\' \;'%\
                (fileToShred))
        os.system('rm -r \'%s\'' % fileToShred)
    else:
        execCmd('gshred -u \'%s\''%fileToShred)

    line()

def getSubfolders(directory):
    """
    for a directory x@y:a/b/c/d,
    will yield x@y:a, then x@y:a/b, then x@y:a/b/c, then x@y:a/b/c/d
    """
    subDir = os.path.dirname(directory)
    if subDir[-1] != ':':
        for x in getSubfolders(subDir):
            yield x
    yield directory

def makeRemoteFolders(remotePath):
    """
    Uploads a .tmp file to all of the directories in a remote path, 
    ensuring that each of the directories in turn exist
    """
    
    # Make a .tmp file
    open('./.tmp','w').close()
    
    genericRsyncCmd = '%(rsync)s "./.tmp" "%(remoteDir)s/"'
    
    # Loop over the sub directories
    for subFolder in getSubfolders(remotePath):
        rsyncCmd = genericRsyncCmd%\
                {'rsync':config.RAMrsync, 'remoteDir':subFolder}
        execCmd(rsyncCmd, suppressOutput = True)

def rsyncToRamtransfer(showProgress = True, getReturn = False, 
        localDir = None, remoteDir = config.remoteExperimentPath):
    """
    Does the rsync from the task PC to ramtransfer
    if getReturn == True, returns the return code from the sync
    """

    if not localDir:
        localDir = os.path.join(config.localExperimentDir, '')
    
    if showProgress:
        progress = '--progress'
    else:
        progress = ''
    
    # Build the command to be executed
    rsyncCmd = '%(rsync)s %(prog)s "%(locDir)s" "%(remoteDir)s"'%\
        {'rsync': config.RAMrsync, 
         'prog' : progress, 
         'locDir' : localDir,
         'remoteDir' : remoteDir}

    # We have to make the directories into which we will upload
    makeRemoteFolders(remoteDir)

    if not getReturn:
        # Execute the command (rsync) and show the output
        execCmd(rsyncCmd, returnOutput = False, returnCode = True, suppressErr = False)
    else:
        return execCmd(rsyncCmd,\
                returnOutput = False,\
                returnCode = True,\
                suppressErr = True,\
                suppressOutput = False)

def uploadFiles_option(showProgress = True):
    """
    A core menu function. rsyncs the entire RAM data directory to ramtransfer
    """
    checkInternetConnection()
    
    # Do the rsync work:
    rsyncToRamtransfer()

    # Do it again, and capture the return code. Don't show output
    rtnCode = rsyncToRamtransfer(False, True)

    if rtnCode == 0:
        print('Upload complete! Moving files to transferred folder')
        moveEEGToTransferred()
        print('Files moved. Hit any key to continue')
    else:
        line('*')
        print('ERROR UPLOADING!!!')
        print('Check internet connection, then contact:')
        print('iped@sas.upenn.edu AND drizzuto@psych.upenn.edu')
        line('*')
    print('Hit any key to continue...')
    getCh()
    clear()
    return True

def getSessionsWithEEG(rootDir = None):
    """
    Gets the sessions within 'rootDir' that have EEG data
    """
    if not rootDir:
        rootDir = config.localExperimentDir
    sessWithEEG = []
    # Walk over the contents of the data directory
    for (root, subdirs, files) in os.walk(rootDir):
        dirName = os.path.basename(root)
        if 'session_' in dirName and 'eeg' in subdirs:
            sessWithEEG.append(root)

    return sessWithEEG

def getSessionList(rootDir):
    """
    Returns a list of strings of all sessions in rootDir
    Subject, experiment: session_#
    """
    sessList = []
    for (root, subdirs, files) in os.walk(rootDir):
        dirName = os.path.basename(root)
        if 'session_' in dirName:
            sessList.append(root)

    return sessList

def sessionPathToString(paths, rootDir):
    """
    Changes the path to a session into a single string
    containing subject -- experiment: session_#

    Paths can be list or single string
    """ 
    if isinstance(paths, (list, tuple)):
        output = []
        for path in paths:
            subj = getSubj(path, rootDir)
            exp = getExp(path, rootDir)
            sess = getSess(path, rootDir)
            output.append('%s -- %s: %s'%(subj, exp, sess))
        return output
    else:
        path = paths
        subj = getSubj(path, rootDir)
        exp = getExp(path, rootDir)
        sess = getSess(path, rootDir)
        return '%s -- %s: %s'%(subj, exp, sess)

def stringToSessionPath(sessStrs, rootDir):
    """
    Takes a formatted session string and changes it back into
    the path that that came from, assuming 'rootDir' is the 
    root directory of the data

    sessStrs can be list or single string
    """
    if isinstance(sessStrs, (list, tuple)):
        output = []
        for sessStr in sessStrs:
            subj = sessStr.split(' -- ')[0]
            exp = sessStr.split(' -- ')[1].split(':')[0]
            sess = sessStr.split(': ')[1]
            output.append(os.path.join(rootDir, exp, subj, sess))
        return output
    else:
        subj = sessStrs.split(' -- ')[0]
        exp = sessStrs.split(' -- ')[1].split(':')[0]
        sess = sessStrs.split(': ')[1]
        output = os.path.join(rootDir, exp, subj, sess)
        return output

def getNonTransferredSessions():
    """
    Gets all of the sessions that exist on the control PC that are
    not in the data or transferred folder

    Note: Assumes the control PC is mounted
    """
    # Get the sessions in "data"
    inData = getSessionsWithEEG(config.localExperimentDir)
    inData = sessionPathToString(inData, config.localExperimentDir)

    # Get the sessions in "transeferred"
    inTransferred = getSessionsWithEEG(config.transferredDir)
    inTransferred = sessionPathToString(inTransferred, config.transferredDir)

    # Get the sessions on control PC
    inPC = getSessionsWithEEG(config.PCMountPoint)
    inPC = sessionPathToString(inPC, config.PCMountPoint)

    # Get what's on PC but not in data or transferred
    onlyInPC = [sess for sess in inPC if (sess not in inData and sess not in inTransferred)]

    return onlyInPC

def chooseSessionFromPC(showAll = False):
    """
    Chooses a session from the control PC
    
    showAll - if True, shows all sessions on control PC in listbox
              if False, only shows sessions that have not yet been transferred

    returns - sessions chosen, False if cancelled
    """
    
    if showAll:
        sessions = getSessionsWithEEG(config.PCMountPoint)
        print config.PCMountPoint
        sessions = sessionPathToString(sessions, config.PCMountPoint)
        sessions.sort()
    else:
        sessions = getNonTransferredSessions()
        sessions.sort()
        sessions.append('Show all')

    if len(sessions)==0:
        line('*')
        print('ERROR: Could not find any sessions!\n Press any key to return')
        line('*')
        getCh()
        return False

    chosen = chooseFromListbox(sessions, 'Choose sessions to transfer') 
    
    if not chosen:
        return False
    elif 'Show all' in chosen:
        return chooseSessionFromPC(True)
    else:
        return chosen

def confirm(message, yMessage = 'confirm', nMessage = 'return'):
    """
    Prompts with message, asking for Y to confirm, N to return
    """
    line()
    print(message)
    line()
    print('Press Y to %s\nPress N to %s'%\
            (yMessage, nMessage))
    ch = None
    while ch not in ('y','n'):
        ch = getCh()

    return ch == 'y'

def mountPC():
    """
    Mount the control PC

    returns True if completed sucessfully, False otherwise
    """

    # Make sure user wants to be here
    if not confirm('Must mount Control PC to continue.',
            'confirm Control PC is connected', 
            'return to main menu'):
        # Get outta here!
        return False
     
    # First, mount the PC at ~/Control_PC
    if not os.path.exists(config.PCMountPoint):
        clear()
        os.makedirs(config.PCMountPoint)

    line()
    print('Mounting Control PC...')
    
    # Try until success
    mounted = False
    while not mounted:
        #### DEBUGGING:
        #print("mount_smbfs  //%(user)s:%(pwd)s@%(ip)s/%(share)s %(mountPoint)s"%\
        #        {'user':config.PCUsername, 'pwd':config.PCPassword, 'ip':config.PCIPAddress,\
        #         'share':config.PCSharedDir, 'mountPoint': config.PCMountPoint})

        os.system("mount_smbfs  //%(user)s:%(pwd)s@%(ip)s/%(share)s %(mountPoint)s"%\
                {'user':config.PCUsername, 'pwd':config.PCPassword, 'ip':config.PCIPAddress,\
                 'share':config.PCSharedDir, 'mountPoint': config.PCMountPoint})
        clear()
        mounted = os.listdir(config.PCMountPoint) != []
        if not mounted:
            if not confirm('Control PC could not be mounted.',
                           'Try again', 
                           'Go back to main menu'):
                return False
    
    print('Control PC mounted')
    return True

def chooseSessionsAndConfirm():
    """
    Asks user to choose a session and confirm
    Returns False if exited, list of sessions to transfer otherwise
    """

    # Confirming they've chosen a session
    sessionsConfirmed = False
    while not sessionsConfirmed:
        # Choose the session to transfer
        sessToTransfer = chooseSessionFromPC()
        
        if not sessToTransfer:
            return False

        # Make sure it's correct
        sessLines = '\n'.join(sessToTransfer)
        message = 'Are you sure you want to transfer the following sessions:\n%s'%sessLines
        sessionsConfirmed = confirm(message, nMessage = 'choose again')
        
        if not sessionsConfirmed:
            clear()

    return sessToTransfer

def transferChosenSessions(sessToTransfer):
    """
    For all of the sessions that have been chosen, transfer them to the task laptop
    from the control PC
    """
    # Get the places to transfer from
    fromSessPaths = stringToSessionPath(sessToTransfer, config.PCMountPoint)

    # Get the places to transfer to
    toSessPaths = stringToSessionPath(sessToTransfer, config.localExperimentDir)

    # Loop over, rsyncing each one
    for (strSess, fromSessPath, toSessPath) in zip(sessToTransfer, fromSessPaths, toSessPaths):
        line()
        print('Transferring %s'%strSess)
        time.sleep(1)
        try:
            os.makedirs(os.path.dirname(toSessPath))
        except OSError as e:
            pass # Can safely igore - it means file already exists

        # Gotta 'dirname' toSessPath, or else it creates a new directory inside
        rsyncCmd = 'rsync -av --progress \'%(from)s\' \'%(to)s\''%\
                {'from': fromSessPath, 'to': os.path.dirname(toSessPath)}
        
        ##### DEBUGGING:
        #print(rsyncCmd)
        
        # Through os.system instead of execCmd so newlines MIGHT work correctly
        os.system(rsyncCmd)
   

def transferEEG_option():
    """
    A core menu function. Transfers EEG and log files from the PC to
    the task laptop
    """
    clear()
    
    # Mount the control PC
    if not mountPC():
        return True

    sessToTransfer = chooseSessionsAndConfirm()
    
    if not sessToTransfer: # They chose to quit
        return True
    
    # Get the sessions that had EEG to begin with
    oldSessWithEEG = getSessionsWithEEG()

    # Trasnfer the chosen sessions
    transferChosenSessions(sessToTransfer)

    # Unmount the Task PC so we can do it again later.
    os.system('umount %s'%config.PCMountPoint)

    # Now get sessions with EEG again, to check what was transferred
    sessWithEEGNew = getSessionsWithEEG()

    # Check for sessions that have been added
    transferredSessions = [sess for sess in sessWithEEGNew if sess not in oldSessWithEEG]
    
    clear()
    # If no sessions have been added, tell the user
    if len(transferredSessions) == 0:
        line('*')
        print('WARNING!!!'+\
                'It doesn\'t appear that any EEG files were transferred.\n'+\
                'Check your connection to the Control PC and try again.')
        line('*')
    else:
        line()
        print('The following EEG folders were transferred:')
        for session in transferredSessions:
            print('\t%s'%session)
        line()

    print('Press any key to return to the main menu')
    getCh()
    
    return True

def viewFilesToUpload_option():
    pass

def showStatus_option():
    pass

def quitProgram_option():
    """
    Exits out of the program, and deletes any old data in the transferred folder
    """
    clear()
    print("Please wait. Deleting old data...")
    os.system('find %s -mtime +30 -type f -exec echo {} \; -exec gshred -u {} \;'%\
            (config.transferredDir))
    print('Done. Press any key to exit.')
    getCh()
    return False    

def transferFileToLaptop(source, destination):
    """
    Transfers a file [from a zip drive] to the appropriate place on the laptop
    """
    copyCmd = 'rsync -av "%s" "%s"'%(source, destination)

    # Make the directory if necessary
    if not os.path.exists(os.path.dirname(destination)):
        os.makedirs(os.path.dirname(destination))

    line()
    print('Copying to hard drive...')
    execCmd(copyCmd)
    print('Done copying!')
    line()
    
    print('Verifying copy to hard drive...')

    if not ((source[-1]=='/') ^ (destination[-1]=='/')):
        # If they're both directories or files
        sourceToDiff = source
        destToDiff = destination
    elif not source[-1]=='/':
        # Source is file, destination is directory
        sourceToDiff = source
        destToDiff = os.path.join(destination, os.path.basename(source))
    else:
        raise Exception('How did you move a directory to a file???')

    diffCmd = ('diff -rq "%s" "%s"'%(sourceToDiff, destToDiff))
    
    diffOut = execCmd(diffCmd)

    if diffOut != '':
        line('*')
        print('ERROR: Copy unsuccessful! Check drive with images and try again')
        print('Press any key to return to menu')
        getCh()
        return False
    else:
        print('Copy to hard drive verified!')
        line()
        return True

def uploadSubjectFile(typeOfUpload, isFile, transferredLbl, tempDestination, remotePath):
    """
    Used by AddClinical and uploadImaging, uploads an arbitrary file to
    ramtransfer and moves it to the transferred folder under that date

    iputs: 
        typeOfUpload    -- "clinical EEG" or "imaging", used as a label
        isFile          -- True if uploading file, false if folder
        transferredLbl  -- Directory to move to within the transferred directory
        tempDestination -- Where to put it before upload (generally an inProgress directory)
    """
    fileOrFolder = 'file' if isFile else 'folder'

    line()
    print('Enter the subject code')
    line()
    
    # User enters the subject name
    subject = enterNameInDialog('Enter Subject Code')
    
    if subject == False or subject == None:
        return True

    clear()
    line()
    prompt = 'Select %s %s'%(typeOfUpload, fileOrFolder)
    print(prompt)
    line()

    # User selects the clinical file
    toUpload = selectFile(prompt, isFile)
    
    if toUpload == False or toUpload == '':
        return True

    if toUpload[-1]=='/':
        toUpload = toUpload[:-1]
 
    clear()
    line()
    message ='Are you sure you want to upload the %s:\n\t%s\nunder the subject name:\n\t%s\n'%\
            (fileOrFolder, toUpload, subject)+\
            '*'*65 + \
            '\n  WARNING: THIS WILL REMOVE THE %s %s FROM ITS SOURCE\n'%\
            (typeOfUpload.upper(), fileOrFolder.upper()) + \
            '*'*65
    confirmed = confirm(message)

    if not confirmed:
        return True
    clear()
    
    subjDestination = os.path.join(tempDestination, subject, '')

    # Copy the files to the laptop
    if not transferFileToLaptop(toUpload, subjDestination):
        return True

    # Rsync the clinical eeg folder to ramtransfer
    print('Uploading files to ramtransfer...')
    
    remoteSubjPath = os.path.join(remotePath, subject)
    rtnCode = rsyncToRamtransfer(True, True, subjDestination, remoteSubjPath)
    if not rtnCode == 0:
        line("*")
        print('RSYNC FAILED. ERROR CODE: %d'%rtnCode)
        print('CONTACT iped@sas.upenn.edu FOR ASSISTANCE')
        line('*')
        getCh()
        return True
    print('Files uploaded!')
    line()

    # Move the file to the transferred directory
    moveToTransferred(tempDestination, subject)

    # Remove the files from their source
    gshredSingleFile(toUpload)
    line()
    print('Done. Press any key to continue')
    getCh()
    
    return True

def addClinical_option():
    """
    Adds a clinical EEG file to be uploaded so we can strip the jacksheet from it
    """
    return uploadSubjectFile('clinical EEG', True, 'clinical_eeg', config.localClinicalDir, config.remoteClinicalPath)

def uploadImaging_option():
    """
    Upload a folder with imaging to ramtransfer
    and delete the imaging from the source, moving it to the
    "tranferred" folder
    """
    checkInternetConnection()
    return uploadSubjectFile('imaging', False, 'imaging', config.localImagingDir, config.remoteImagingPath)

def run():
    clear()
    
    showMenuAgain = True
    while showMenuAgain:
        clear()
        keyPressed = mainMenu()
        funcToRun = keyToFn(keyPressed)
        showMenuAgain = funcToRun()

if __name__ == '__main__':
    run()
