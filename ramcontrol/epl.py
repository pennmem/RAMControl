"""Commonly used PyEPL routines.

This module will be removed when migrating away from PyEPL is complete.

"""

from pyepl.locals import (
    VideoTrack, AudioTrack, LogTrack, KeyTrack, Key, Text, ButtonChooser,
    PresentationClock, SOUTH, waitForAnyKey, Movie
)
from ramcontrol.extendedPyepl import CustomBeep


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


class PyEPLHelpers(object):
    """Helpers for PyEPL-based experiments.

    :param epl_exp: PyEPL :class:`Experiment` instance.
    :param video: PyEPL :class:`Video` instance.
    :param audio: PyEPL :class:`audio` instance.
    :param clock: PyEPL :class:`clock` instance.

    """
    def __init__(self, epl_exp, video, audio, clock):
        self.exp = epl_exp
        self.video = video
        self.audio = audio
        self.clock = clock

        config = self.exp.getConfig()

        self._start_beep = CustomBeep(
            config.startBeepFreq,
            config.startBeepDur,
            config.startBeepRiseFall)

        self._stop_beep = CustomBeep(
            config.stopBeepFreq,
            config.stopBeepDur,
            config.stopBeepRiseFall)

    def play_start_beep(self):
        self._start_beep.present(self.clock)

    def play_stop_beep(self):
        self._stop_beep.present(self.clock)
        
    def play_movie_sync(self, filename, bc=None):
        """Plays a whole movie synchronously.

        :param str filename: Path to movie file.
        :param ButtonChooser bc: When given, allows for cancelling the movie.

        """
        movie = Movie(filename)
        movie_shown = self.video.showCentered(movie)
        self.video.playMovie(movie)

        # Stop on button press if BC passed in, otherwise wait until the movie
        # is finished.
        if bc is None:
            self.clock.delay(movie.getTotalTime())
            self.clock.wait()
        else:
            self.clock.wait()
            bc.wait()
        self.video.stopMovie(movie)
        movie.unload()
        #self.video.unshow(movie_shown)

    def play_intro_movie(self, filename, allow_skip=True):
        """Play an intro movie, allowing cancellation.

        :param str filename: Path to movie file.
        :param bool allow_skip: Allow skipping the intro video.

        """
        self.video.clear('black')

        # if the first list has been completed, allow them to skip playing the movie
        if not allow_skip:
            waitForAnyKey(self.clock, Text('Press any key to play movie'))
            shown = self.video.showAnchored(
                Text('Hit SPACE at any time to continue'), SOUTH,
                self.video.propToPixel(.5, 1))
            self.play_movie_sync(filename, ButtonChooser(Key('SPACE')))
            self.video.unshow(shown)
            seen_once = True
        else:
            bc = ButtonChooser(Key('Y'), Key('N'))
            _, button, _ = Text(
                'Press Y to play instructional video \n Press N to continue to practice list') \
                .present(bc=bc)
            if button == Key('N'):
                return
            seen_once = False

        bc = ButtonChooser(Key('Y'), Key('N'))

        # Allowed to skip the movie the second time that it has been watched
        while True:
            if seen_once:
                _, button, _ = Text(
                    'Press Y to continue to practice list, \n Press N to replay instructional video') \
                    .present(bc=bc)
                if button == Key('Y'):
                    break
            shown = self.video.showAnchored(
                Text('Hit SPACE at any time to continue'), SOUTH,
                self.video.propToPixel(.5, 1))

            stop_bc = ButtonChooser(Key('SPACE'))
            self.play_movie_sync(filename, stop_bc)
            seen_once = True
            self.video.unshow(shown)

    def show_text_and_wait_for_keyboard_input(self, text, keys=["SPACE"]):
        """Display text and wait for the user to hit a key.
        
        :param str text: Text to display.
        :param list keys: List of keys to accept.
        :returns: Tuple of key pressed, timestamp of key press.

        """
        if len(keys) > 1:
            raise NotImplementedError("TODO: allow more than just SPACE key")
        bc = ButtonChooser(Key('SPACE'))
        self.video.clear('black')
        _, key, timestamp = Text(text).present(self.clock, bc=bc)
        return key, timestamp
