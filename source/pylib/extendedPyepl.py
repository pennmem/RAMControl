from pyepl.locals import *
from pyepl import exputils
from pyepl import display
import os
import codecs

TEXT_EXTS = ["txt"]

class CustomText(Text):

    def presentWithCallback(self, clk = None, duration = None, jitter = None, bc = None, minDuration = None,
                            updateCallback = None):
        """
        Present an text on the screen.  If a ButtonChooser is
        provided, present ignores the jitter and clears the stimulus
        once a button is pressed or the duration is exceeded.

        INPUT ARGS:
          clk- Optional PresentationClock to update.
          duration/jitter- Duration to display the stimulus.
          bc- Optional ButtonChooser object
          minDuration
          onscreenCallback
          offscreenCallback


        OUTPUT ARGS:
          timestamp- time and latency of when the text came on the screen.
          button- Button pressed if we passed in bc.
          bc_time- Time and latency of when the button was pressed (if provided)

        """

        v = VideoTrack.lastInstance()

        # get the clock if needed
        if clk is None:
            clk = exputils.PresentationClock()

        # show the image
        t = v.showCentered(self)
        if updateCallback:
            v.addUpdateCallback(updateCallback)
            cbref = v.update_callbacks[-1]
        timestamp_on = v.updateScreen(clk)

        if bc:
            # wait for button press
            button,bc_time = bc.waitWithTime(minDuration,duration,clk)
        else:
            clk.delay(duration,jitter)

        v.unshow(t)
        timestamp_off = v.updateScreen(clk)
        if updateCallback:
            v.removeUpdateCallback(cbref)

        if bc:
            return timestamp_on, button,bc_time
        else:
            return timestamp_on, timestamp_off


class CustomTextPool(TextPool):
    """
    Overrides the TextPool allowing for accents to appear in words
    """
    def loadFromSourcePath(self, sourcepath, size, color, font):
        """
        """
        if os.path.isdir(sourcepath):
            for stimfile in os.listdir(sourcepath):
                name, ext = os.path.splitext(stimfile)
                ext = ext.lower()
                if not name or not ext:
                    continue
                try:
                    stimobj = self.findBy(name=name)
                except LookupError:
                    stimobj = self.append(name=name)
                if ext == ".dummy":
                    pass
                elif ext[1:] in TEXT_EXTS:
                    # load text file as TextPool
                    stimobj.content = TextPool(os.path.abspath(os.path.join(sourcepath, stimfile)))
                    # stimobj.content = display.Text(open(os.path.abspath(os.path.join(sourcepath, stimfile))).read(),
                    #                                 size=size, color=color, font=font)
                else:
                    raise Exception('Bad File Extension creating CustomTextPool')
        else:
            for line in codecs.open(sourcepath, "r", "utf-8"):
                textval = line.strip()
                self.append(name=textval,
                            content=display.Text(textval, size=size, color=color, font=font))


def waitForAnyKeyWithCallback(clk = None, showable = None, x = 0.5, y = 0.5, excludeKeys=None,
                  onscreenCallback=None, offscreenCallback=None):
    """
    Wait for any key to be pressed.  Optionally you can pass in a
    showable to be displayed at the coordinants x,y.

    (Where is the Any key???)

    INPUT ARGS:
      clk- Optional PresentationClock for timing.
      showable- Text/Image object to display.
      x,y- Proportional coordinants of where to display the showable.
      excludeKeys- Optional keys to ignore, such as ['T','Q']
    """
    if excludeKeys: # decide which keys to wait for
        knames = []
        for kname in hardware.keyNames():
            if kname not in excludeKeys:
                knames.append(kname)

    # if a showable is given...
    if showable:
        # get the VideoTrack
        v = display.VideoTrack.lastInstance()

        # show the showable
        shown = v.showProportional(showable, x, y)

        # update the screen (using the clock object)
        if onscreenCallback:
            onscreenCallback()
        v.updateScreen(clk)

    # get the keytrack
    k = KeyTrack.lastInstance()

    # wait for a key press
    if excludeKeys:
        bc = k.keyChooser(*knames)
    else:
        bc = k.keyChooser()
    but,timestamp = bc.waitWithTime(clock=clk)

    # if we displayed a showable...
    if showable:
        # ...unshow it
        v.unshow(shown)
        # and update the screen again
        if offscreenCallback:
            offscreenCallback()
        v.updateScreen(clk)


def flashStimulusWithOffscreenTimestamp(showable, duration = 1000, x = 0.5, y = 0.5, jitter = None, clk = None,
                                        onUpdateCallback = None):
    """
    Flash a showable on the screen for a specified duration.

    INPUT ARGS:
      showable- Object to display.
      duration- Duration to display the image.
      x,y- Location of the showable.
      jitter- Amount to jitter the presentation duration.
      clk- PresentationClock for timing.

    OUTPUT ARGS:
      timestamp- Time/latency when stimulus was presented on the screen.
    """
    if clk is None:
        # if no PresentationClock is given, create one
        clk = exputils.PresentationClock()

    # get the VideoTrack
    v = VideoTrack.lastInstance()

    # show the stimulus
    shown = v.showProportional(showable, x, y)

    # update the screen
    timestamp_on = v.updateScreen(clk)

    # delay
    clk.delay(duration, jitter)

    # unshow the stimulus
    v.unshow(shown)

    # update the screen
    timestamp_off = v.updateScreen(clk)


    # return ontime
    return timestamp_on, timestamp_off


class CustomAudioTrack(AudioTrack):

    def __init__(self, *args):
        AudioTrack.__init__(self, *args)

    def record(self, duration, basename = None, t = None,
               startCallback=None, stopCallback=None, **sfargs):

        """
        Perform a blocked recording for a specified duration (in milliseconds).

        INPUT ARGS:
          duration- length of time (in ms.) to record for.
          basename- filename to save recorded data to.
          t- optional PresentationClock for timing.
          sfargs- keyword arguments passed to FileAudioClip constructor

        OUTPUT ARGS:
          recClip- The AudioClip object that contains the recorded data.
          timestamp- time and latency when sound recording began.
        """
        if not t:
            t = timing.now()
        elif isinstance(t, exputils.PresentationClock):
            clk = t
            t = clk.get()
            clk.delay(duration)

        if startCallback:
            startCallback()
        (r,starttime) = self.startRecording(basename, t = t, **sfargs)
        if stopCallback:
            stopCallback()
        (r,stoptime) = self.stopRecording(t = t + duration)
        return (r,starttime)


class CustomAudioClip(AudioClip):

        def present(self, clk = None, duration = None, jitter = None, bc = None, minDuration = None, doDelay = True,
                    onCallback=None):
            """
            Present an AudioClip.  If provided, the clock will be advanced
            by the duration/jitter passed in, otherwise it will advance
            the duration of the audio clip.  If a ButtonChooser is
            provided, then present waits until the button is pressed
            before returning, advancing the clock to the point when the
            button was pressed.

            INPUT ARGS:
              clk- Optional PresentationClock for timing.
              duration/jitter- Duration to keep the stimulus on.
              bc - Optional ButtonChooser object.

            OUTPUT ARGS:
              timestamp- time and latency of when the sound was played.
              button- Button pressed if we passed in bc.
              bc_time- Time and latency of when the button was pressed (if provided)
            """

            a = CustomAudioTrack.lastInstance()

            # get the clock if needed
            if clk is None:
                clk = exputils.PresentationClock()

            # play the sound
            if onCallback:
                onCallback()
            timestamp = a.play(self, t=clk, doDelay=doDelay)

            if bc:
                # wait for button press
                button,bc_time = bc.waitWithTime(minDuration, duration, clk)
                return timestamp, button, bc_time
            elif duration:
                # reset to before play and just advance the duration+jitter
                clk.delay(duration, jitter)
                return timestamp
            else:
                # keep the clock advanced the duration of the sound
                return timestamp


class CustomBeep(CustomAudioClip, Beep):

    def __init__(self, freq, duration, risefalltime = 0, scalePercent = 0.8):
        """
        Generate a beep of desired frequency, duration, and rise/fall
        time.  Format of beep is in 16bit int samples.

            INPUT ARGS:
              freq- frequency of beep
              duration- length of time (in ms.) to play beep for.
              risefalltime- length of time (in ms.) for beep to rise from
                silence to full volume at beginning, and fall to no volume
                at end.
              scalePercent- Percent of the max audio range for the beep (defaults to .8).

          """
        CustomAudioClip.__init__(self)
        a = CustomAudioTrack.lastInstance()

            # set the scale
        scale = a.eplsound.SCALE * scalePercent

        # Do some rate and ms conversions
        sampCycle = int(self.RESAMPLEDRATE/freq)
        sampDur = int(duration*self.RESAMPLEDRATE/1000)
        sampRise = int(risefalltime*self.RESAMPLEDRATE/1000)

        # Create the array at correct frequency
        buff = numpy.arange(0, sampDur*(2*math.pi)/sampCycle, (2*math.pi)/sampCycle)
        buff = scale * numpy.sin(buff)

        # Apply envelope
        if risefalltime > 0:
            env = numpy.arange(0, 1, float(1/float(sampRise)))
            buff[0:len(env)] = buff[0:len(env)]*env
            buff[-1:-(len(env)+1):-1] = buff[-1:-(len(env)+1):-1]*env

        # convert to int16
        buff = buff.astype(numpy.int16)

        # convert duplicate to a 2nd channel
        self.snd = self.duplicateChannel(buff)


def customMicTest(recDuration = 2000, ampFactor = 1.0, clk = None, excludeKeys=None):
    """
    Microphone test function.  Requires VideoTrack, AudioTrack,
    KeyTrack to already exist.

    INPUT ARGS:
      recDuration- Duration to record during the test.
      ampFactor- Amplification factor for playback of the sound.
      clk- Optional PresentationClock for timing.

    OUTPUT ARGS:
      status- True if you should continue the experiment.
              False if the sound was not good and you should
              quit the program.
    """

    v = display.VideoTrack.lastInstance()
    a = CustomAudioTrack.lastInstance()
    k = KeyTrack.lastInstance()

    if clk is None:
        clk = exputils.PresentationClock()

    done = False
    while not done:
        v.clear()
        v.showProportional(display.Text("Microphone Test",size = .1), .5, .1)
        waitForAnyKey(clk,showable=display.Text("Press any key to\nrecord a sound after the beep."), excludeKeys=excludeKeys)

            # clear screen and say recording
        beep1 = CustomBeep(400, 500, 100)
        beep1.present(clk)

        t = v.showCentered(display.Text("Recording...",color=(1,0,0)))
        v.updateScreen(clk)
        (testsnd,x) = a.record(recDuration, t=clk)
        v.unshow(t)
        v.updateScreen(clk)

        # play sound
        t = v.showCentered(display.Text("Playing..."))
        v.updateScreen(clk)
        a.play(testsnd,t=clk, ampFactor=ampFactor)
        v.unshow(t)
        v.updateScreen(clk)

        # ask if they were happy with the sound
        t = v.showCentered(display.Text("Did you hear the recording?"))
        v.showRelative(display.Text("(Y=Continue / N=Try Again / C=Cancel)"),display.BELOW,t)
        v.updateScreen(clk)

        response = buttonChoice(clk,
                                yes = (Key('Y') | Key('RETURN')),
                                no = Key('N'),
                                cancel = Key('C'))
        status = True
        if response == "cancel":
            status = False
        elif response == "no":
            # do it again
            continue
        done = True

    # clear before returning
    v.clear()

    return status


def customMathDistract(clk = None,
                       mathlog = None,
                       problemTimeLimit = None,
                       numVars = 2,
                       maxNum = 9,
                       minNum = 1,
                       maxProbs = 50,
                       plusAndMinus = False,
                       minDuration = 20000,
                       textSize = None,
                       correctBeepDur = 500,
                       correctBeepFreq = 400,
                       correctBeepRF = 50,
                       correctSndFile = None,
                       incorrectBeepDur = 500,
                       incorrectBeepFreq = 200,
                       incorrectBeepRF = 50,
                       incorrectSndFile = None,
                       tfKeys = None,
                       ansMod = [0,1,-1,10,-10],
                       ansProb = [.5,.125,.125,.125,.125],
                       visualFeedback = False):
    """
    Math distractor for specified period of time.  Logs to a math_distract.log
    if no log is passed in.

    INPUT ARGS:
      clk - Optional PresentationClock for timing.
      mathlog - Optional Logtrack for logging.
      problemTimeLimit - set this param for non-self-paced distractor;
                         buzzer sounds when time's up; you get at least
                         minDuration/problemTimeLimit problems.
      numVars - Number of variables in the problem.
      maxNum - Max possible number for each variable.
      minNum - Min possible number for each varialbe.
      maxProbs - Max number of problems.
      plusAndMinus - True will have both plus and minus.
      minDuration - Minimum duration of distractor.
      textSize - Vertical height of the text.
      correctBeepDur - Duration of correct beep.
      correctBeepFreq - Frequency of correct beep.
      correctBeepRF - Rise/Fall of correct beep.
      correctSndFile - Optional Audio clip to use for correct notification.
      incorrectBeepDur - Duration of incorrect beep.
      incorrectBeepFreq - Frequency of incorrect beep.
      incorrectBeepRF - Rise/Fall of incorrect beep
      incorrectSndFile - Optional AudioClip used for incorrect notification.
      tfKeys - Tuple of keys for true/false problems. e.g., tfKeys = ('T','F')
      ansMod - For True/False problems, the possible values to add to correct answer.
      ansProb - The probability of each modifer on ansMod (must add to 1).
      visualFeedback - Whether to provide visual feedback to indicate correctness.
    """

    # start the timing
    start_time = timing.now()

    # get the tracks
    v = display.VideoTrack.lastInstance()
    a = CustomAudioTrack.lastInstance()
    k = KeyTrack.lastInstance()

    # see if need logtrack
    if mathlog is None:
        mathlog = LogTrack('math_distract')

    # log the start
    mathlog.logMessage('START')

    # start timing
    if clk is None:
        clk = exputils.PresentationClock()

    # set the stop time
    if not minDuration is None:
        stop_time = start_time + minDuration
    else:
        stop_time = None

    # generate the beeps
    correctBeep = CustomBeep(correctBeepFreq,correctBeepDur,correctBeepRF)
    incorrectBeep = CustomBeep(incorrectBeepFreq,incorrectBeepDur,incorrectBeepRF)

    # clear the screen (now left up to caller of function)
    #v.clear("black")

    # generate a bunch of math problems
    vars = numpy.random.randint(minNum,maxNum+1,[maxProbs, numVars])
    if plusAndMinus:
        pm = numpy.sign(numpy.random.uniform(-1,1,[maxProbs, numVars-1]))
    else:
        pm = numpy.ones([maxProbs, numVars-1])

    # see if T/F or numeric answers
    if isinstance(tfKeys,tuple):
        # do true/false problems
        tfProblems = True

        # check the ansMod and ansProb
        if len(ansMod) != len(ansProb):
            # raise error
            pass
        if sum(ansProb) != 1.0:
            # raise error
            pass
        ansProb = numpy.cumsum(ansProb)
    else:
        # not t/f problems
        tfProblems = False

    # set up the answer button
    if tfProblems:
        # set up t/f keys
        ans_but = k.keyChooser(*tfKeys)
    else:
        # set up numeric entry
        ans_but = k.keyChooser('0','1','2','3','4','5','6','7','8','9','-','RETURN',
                               '[0]','[1]','[2]','[3]','[4]','[5]','[6]',
                               '[7]','[8]','[9]','[-]','ENTER','BACKSPACE')

    # do equations till the time is up
    curProb = 0
    while not (not stop_time is None and timing.now() >= stop_time) and curProb < maxProbs:
        # generate the string and result

        # loop over each variable to generate the problem
        probtxt = ''
        for i,x in enumerate(vars[curProb,:]):
            if i > 0:
                # add the sign
                if pm[curProb,i-1] > 0:
                    probtxt += ' + '
                else:
                    probtxt += ' - '

            # add the number
            probtxt += str(x)

        # calc the correct answer
        cor_ans = eval(probtxt)

        # add the equal sign
        probtxt += ' = '

        # do tf or numeric problem
        if tfProblems:
            # determine the displayed answer
            # see which answermod
            ansInd = numpy.nonzero(ansProb >= numpy.random.uniform(0,1))
            if isinstance(ansInd,tuple):
                ansInd = ansInd[0]
            ansInd = min(ansInd)
            disp_ans = cor_ans + ansMod[ansInd]

            # see if is True or False
            if disp_ans == cor_ans:
                # correct response is true
                corRsp = tfKeys[0]
            else:
                # correct response is false
                corRsp = tfKeys[1]

            # set response str
            rstr = str(disp_ans)
        else:
            rstr = ''

        # display it on the screen
        pt = v.showProportional(display.Text(probtxt,size = textSize),.4,.5)
        rt = v.showRelative(display.Text(rstr, size = textSize),display.RIGHT,pt)
        probstart = v.updateScreen(clk)

        # wait for input
        answer = .12345  # not an int
        hasMinus = False
        if problemTimeLimit:
            probStart = timing.now()
            probEnd = probStart + problemTimeLimit
            curProbTimeLimit = probEnd - probStart
        else:
            curProbTimeLimit = None

        # wait for keypress
        kret,timestamp = ans_but.waitWithTime(maxDuration = curProbTimeLimit, clock=clk)

        # process as T/F or as numeric answer
        if tfProblems:
            # check the answer
            if not kret is None and kret.name == corRsp:
                isCorrect = 1
            else:
                isCorrect = 0
        else:
            # is part of numeric answer
            while kret and \
                      ((kret.name != "RETURN" and kret.name != "ENTER") or \
                       (hasMinus is True and len(rstr)<=1) or (len(rstr)==0)):
                # process the response
                if kret.name == 'BACKSPACE':
                    # remove last char
                    if len(rstr) > 0:
                        rstr = rstr[:-1]
                        if len(rstr) == 0:
                            hasMinus = False
                elif kret.name == '-' or kret.name == '[-]':
                    if len(rstr) == 0 and plusAndMinus:
                        # append it
                        rstr = '-'
                        hasMinus = True
                elif kret.name == 'RETURN' or kret.name == 'ENTER':
                    # ignore cause have minus without number
                    pass
                elif len(rstr) == 0 and (kret.name == '0' or kret.name == '[0]'):
                    # Can't start a number with 0, so pass
                    pass
                else:
                    # if its a number, just append
                    numstr = kret.name.strip('[]')
                    rstr = rstr + numstr

                # update the text
                rt = v.replace(rt,display.Text(rstr,size = textSize))
                v.updateScreen(clk)

                # wait for another response
                if problemTimeLimit:
                    curProbTimeLimit = probEnd - timing.now()
                else:
                    curProbTimeLimit = None
                kret,timestamp = ans_but.waitWithTime(maxDuration = curProbTimeLimit,clock=clk)

            # check the answer
            if len(rstr)==0 or eval(rstr) != cor_ans:
                isCorrect = 0
            else:
                isCorrect = 1

        # give feedback
        if isCorrect == 1:
            # play the beep
            pTime = a.play(correctBeep,t=clk,doDelay=False)
            #clk.tare(pTime[0])
            #correctBeep.present(clk)

            # see if set color of text
            if visualFeedback:
                pt = v.replace(pt,display.Text(probtxt,size=textSize,color='green'))
                rt = v.replace(rt,display.Text(rstr, size=textSize, color='green'))
                v.updateScreen(clk)
                clk.delay(correctBeepDur)
        else:
            # play the beep
            pTime = a.play(incorrectBeep,t=clk,doDelay=False)
            #clk.tare(pTime[0])
            #incorrectBeep.present(clk)

            # see if set color of text
            if visualFeedback:
                pt = v.replace(pt,display.Text(probtxt,size=textSize,color='red'))
                rt = v.replace(rt,display.Text(rstr, size=textSize, color='red'))
                v.updateScreen(clk)
                clk.delay(incorrectBeepDur)

        # calc the RT as (RT, maxlatency)
        prob_rt = (timestamp[0]-probstart[0],timestamp[1]+probstart[1])

        # log it
        # probstart, PROB, prob_txt, ans_txt, Correct(1/0), RT
        # Sends:
        # - problem as text ("4 + 5 + 1 = ")
        # - response as text ("1")
        # - 1 if correct, 0 if incorrect
        # - always 0 apparently
        # - response time in ms
        # - how long it took to update the screen in ms (not necesssary)
        mathlog.logMessage('PROB\t%r\t%r\t%d\t%ld\t%d' %
                           (probtxt,rstr,isCorrect,prob_rt[0],prob_rt[1]),
                           probstart)

        # clear the problem
        v.unshow(pt,rt)
        v.updateScreen(clk)

        # increment the curprob
        curProb+=1

    # log the end
    mathlog.logMessage('STOP',timestamp)

    # tare the clock
    # PBS: Why set the time back to when the last button was pressed?
    #clk.tare(timestamp)
