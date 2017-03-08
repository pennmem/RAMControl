"""Commonly used PyEPL routines.

This module will be removed when migrating away from PyEPL is complete.

"""

from pyepl.locals import (
    VideoTrack, AudioTrack, LogTrack, KeyTrack, Key, Text, ButtonChooser,
    PresentationClock, SOUTH, waitForAnyKey, Movie
)


# From RAM_FR, but seemingly not used
def skip_session(exp):
    state = exp.restoreState()
    exp.setSession(state.sessionNum)

    video = VideoTrack("video")
    keyboard = KeyTrack("keyboard")
    log = LogTrack("session")
    mathlog = LogTrack("math")

    continueKey = Key('SPACE') & Key('RETURN')
    breakKey = Key('ESCAPE')

    message = Text(
        "Press SPACE and RETURN \n" +
        "to skip session %d.\n" % state.sessionNum +
        "Press esc to exit without skipping." % state.sessionNum)
    bc = ButtonChooser(continueKey, breakKey)

    video.showCentered(message)
    video.updateScreen()
    b = bc.wait()

    if b == continueKey:
        print('skipping session...')
        state.sessionNum += 1
        state.trialNum = 0
        exp.saveState(state)
        log.logMessage('SESSION_SKIPPED', PresentationClock().get())


def play_whole_movie(video, audio, movieFile, clock, bc=None):
    """Plays any movie file and audio file synchronously.

    Imported from RAM_FR but seemingly not used
    (FR.py defines its own version...).

    FIXME: move functionality here from FR.py

    """
    movieObject = Movie(movieFile)
    movieObject.load()
    video.showCentered(movieObject)
    video.playMovie(movieObject)

    # Stop on button press if BC passed in, otherwise wait until the movie
    # is finished.
    if bc is None:
        clock.delay(movieObject.getTotalTime())
        clock.wait()
    else:
        clock.wait()
        bc.wait()
    video.stopMovie(movieObject)
    movieObject.unload()


def play_intro_movie(exp, video, keyboard, allowSkip, language):
    """Uses the experimental configuration to load a movie and sound
    clip and plays them synchonously with the movie centered on the
    screen

    (NOTE: video and sound had to be split to allow for playing of files
    that were exported from keynote, which are not compatible with MPEG1
    format

    Imported from RAM_FR.

    """
    config = exp.getConfig()
    clock = PresentationClock()
    audio = AudioTrack.lastInstance()

    video.clear('black')

    introMovie = config.introMovie.format(language=language)
    print(introMovie)

    # if the first list has been completed, allow them to skip playing the movie
    if not allowSkip:
        waitForAnyKey(clock, Text('Press any key to play movie'))
        continueText = Text('Hit SPACE at any time to continue')
        shown = video.showAnchored(continueText, SOUTH, video.propToPixel(.5, 1))
        stopBc = ButtonChooser(Key('SPACE'))
        play_whole_movie(video, audio, introMovie, clock, stopBc)
        video.unshow(shown)
        seenOnce = True
    else:
        bc = ButtonChooser(Key('Y'), Key('N'))
        _, button, _ = Text(
            "Press Y to play instructional video \n"
            "Press N continue to practice list"
        ).present(bc=bc)
        if button == Key('N'):
            return
        seenOnce = False

    bc = ButtonChooser(Key('Y'), Key('N'))

    # Allowed to skip the movie the second time that it has been watched
    while True:
        if seenOnce:
            _, button, _ = Text(
                "Press Y to continue to practice list, \n"
                "Press N to replay instructional video"
            ).present(bc=bc)
            if button == Key('Y'):
                break

        continueText = Text('Hit SPACE at any time to continue')
        shown = video.showAnchored(continueText, SOUTH, video.propToPixel(.5, 1))

        stopBc = ButtonChooser(Key('SPACE'))
        play_whole_movie(video, audio, introMovie,  clock, stopBc)
        seenOnce = True
        video.unshow(shown)
