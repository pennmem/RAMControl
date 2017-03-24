"""Commonly used PyEPL routines.

This module will be removed when migrating away from PyEPL is complete.

"""

from pyepl.locals import (
    Key, Text, ButtonChooser, PresentationClock, SOUTH, waitForAnyKey, Movie
)
from ramcontrol.extendedPyepl import CustomBeep


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
        clock = PresentationClock()
        movie = Movie(filename)
        movie_shown = self.video.showCentered(movie)
        self.video.playMovie(movie)

        # Stop on button press if BC passed in, otherwise wait until the movie
        # is finished.
        if bc is None:
            clock.delay(movie.getTotalTime())
            clock.wait()
        else:
            clock.wait()
            bc.wait()
        self.video.stopMovie(movie)
        movie.unload()
        self.video.unshow(movie_shown)

    def play_intro_movie(self, filename, allow_skip):
        """Play an intro movie, allowing cancellation.

        :param str filename: Path to movie file.
        :param bool allow_skip: Allow skipping the intro video.

        """
        self.video.clear('black')

        yes_or_no_chooser = ButtonChooser(Key('Y'), Key('N'))

        # if the first list has been completed, allow them to skip playing the movie
        if not allow_skip:
            waitForAnyKey(self.clock, Text('Press any key to play movie'))
            shown = self.video.showAnchored(
                Text('Hit SPACE at any time to continue'), SOUTH,
                self.video.propToPixel(.5, 1))
            self.play_movie_sync(filename, bc=ButtonChooser(Key("SPACE")))
            self.video.unshow(shown)
            seen_once = True
        else:
            _, button, _ = Text(
                'Press Y to play instructional video \n Press N to continue to practice list') \
                .present(bc=yes_or_no_chooser)
            if button == Key('N'):
                return
            seen_once = False

        # Allowed to skip the movie the second time that it has been watched
        while True:
            if seen_once:
                _, button, _ = Text(
                    'Press Y to continue to practice list, \n Press N to replay instructional video') \
                    .present(bc=yes_or_no_chooser)
                if button == Key('Y'):
                    break
            shown = self.video.showAnchored(
                Text('Hit SPACE at any time to continue'), SOUTH,
                self.video.propToPixel(.5, 1))

            self.play_movie_sync(filename, bc=ButtonChooser(Key("SPACE")))
            seen_once = True
            self.video.unshow(shown)

    def confirm(self, text):
        """Display text and wait for a keypress to indicate yes or no.

        :param str text: Text to display.
        :returns: True if yes, False if no.

        """
        bc = ButtonChooser(Key('Y'), Key('N'))
        _, button, _ = Text(text).present(bc=bc)
        print("PYEPL SUCKS")
        return button == Key('Y')

    def show_text_and_wait_for_keyboard_input(self, text, font_height,
                                              keys=["SPACE"]):
        """Display text and wait for the user to hit a key.
        
        :param str text: Text to display.
        :param font_height: Config variable defined height of font to use.
        :param list keys: List of keys to accept.
        :returns: Tuple of key pressed, timestamp of key press.

        """
        bc = ButtonChooser(*[Key(key) for key in keys])
        self.video.clear('black')
        _, key, timestamp = Text(text, size=font_height).present(self.clock, bc=bc)
        return key, timestamp
