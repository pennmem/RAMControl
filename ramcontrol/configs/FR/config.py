LANGUAGE = 'EN'

# Number of sessions per subject
numSessions = 10

# Default number of PS lists
n_ps = 0

# Include recognition subtask REC1
recognition_enabled = False

# Pause+Jitter after orienting stim before first word
PauseBeforeWords = 1000
JitterBeforeWords = 400

PauseBeforeRecall = 500
JitterBeforeRecall = 200

# Word Font size (percentage of vertical screen)
wordHeight = .1

# Duration word is on the screen
wordDuration = 1600

# ISI+Jitter after word is cleared from the screen
ISI = 750
Jitter = 250

# Duration of recall in ms
recallDuration = 30000

# Beep at start and end of recording (freq,dur,rise/fall)
startBeepFreq = 800
startBeepDur = 500
startBeepRiseFall = 100
stopBeepFreq = 400
stopBeepDur = 500
stopBeepRiseFall = 100

# Orienting Stimulus text
orientText = '+'
recallStartText = '*******'

# Videos
# FIXME: figure out where to really put movies
video_root = "/Users/depalati/src/RAMControl/experiments/RAM_FR/"
# FIXME: why are there two countdown movies?
countdownMovie = video_root + "video_{language:s}/countdown.mpg"
introMovie = video_root + "video_{language:s}/instructions.mpg"

# Math distractor options
MATH_numVars = 3
MATH_maxNum = 9
MATH_minNum = 1
MATH_maxProbs = 50
MATH_plusAndMinus = False
MATH_minDuration_Practice = 30000
MATH_minDuration = 20000
MATH_textSize = .1
MATH_correctBeepDur = 500
MATH_correctBeepFreq = 400
MATH_correctBeepRF = 50
MATH_correctSndFile = None
MATH_incorrectBeepDur = 500
MATH_incorrectBeepFreq = 200
MATH_incorrectBeepRF = 50
MATH_incorrectSndFile = None

# Instructions text file
pre_practiceList = 'text_%s/pre_practiceList.txt'  # LANGUAGE PLACED BY FR.PY
post_practiceList = 'text_%s/post_practiceList.txt'  # LANGUAGE PLACED BY FR.PY

# make stim form
makeStimForm = False
trialsPerPage = 7

# Default font
defaultFont = 'fonts/Verdana.ttf'

# Realtime configuration
# ONLY MODIFY IF YOU KNOW WHAT YOU ARE DOING!
# HOWEVER, IT SHOULD BE TWEAKED FOR EACH MACHINE
doRealtime = True
rtPeriod = 120
rtComputation = 9600
rtConstraint = 1200

# Used to find the file for constructing word lists with similar words
similarityFile = 'wordpool_generation/RAM_FR_LSA.csv'

# Set to True to speed things up for development
fastConfig = False

if fastConfig:
    ISI = 10
    Jitter = 0

    PauseBeforeWords = 10
    JitterBeforeWords = 10

    wordDuration = 20
    recallDuration = 10

    MATH_minDuration_Practice = 10
    MATH_minDuration = 10
