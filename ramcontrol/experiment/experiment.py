from __future__ import print_function

from abc import ABCMeta, abstractmethod
import os
import os.path as osp
import sys
import json
from contextlib import contextmanager
import functools
import logging

import six

from logserver import create_logger

from ramcontrol import listgen, __version__
from ramcontrol.control import RAMControl
from ramcontrol.exc import LanguageError, RAMException
from ramcontrol.messages import StateMessage, ExitMessage
from ramcontrol.extendedPyepl import CustomAudioTrack
from ramcontrol.epl import PyEPLHelpers

from pyepl import exputils, timing
from pyepl.display import VideoTrack, Text
from pyepl.keyboard import KeyTrack, Key
from pyepl.mechinput import ButtonChooser
from pyepl.textlog import LogTrack
from pyepl.convenience import waitForAnyKey, flashStimulus


def skippable(func):
    """Decorator to skip a run_x method. Just add ``skip_x`` to the ``kwargs``
    given to the :class:`Experiment` instance. This also requires the debug
    flag is set.

    """
    if not func.__name__.startswith("run_"):
        raise RuntimeError("You can only use this decorator with run_xyz methods!")

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        skip_key = "skip_" + '_'.join(func.__name__.split("_")[1:])
        if self.debug:
            if self.kwargs.get(skip_key, False):
                print(skip_key)
                return True
        return func(self, *args, **kwargs)
    return wrapper


class Timings(object):
    """Convenience class to store all timing settings."""
    def __init__(self, word_duration, recall_duration, encoding_delay,
                 recall_delay, isi, jitter, encoding_jitter, recall_jitter):
        """
        :param int word_duration:
        :param int recall_duration:
        :param int encoding_delay:
        :param int recall_delay:
        :param int isi:
        :param int jitter:
        :param int encoding_jitter:
        :param int recall_jitter:

        """
        self.word_duration = word_duration
        self.recall_duration = recall_duration
        self.encoding_delay = encoding_delay
        self.recall_delay = recall_delay
        self.isi = isi
        self.jitter = jitter
        self.encoding_jitter = encoding_jitter
        self.recall_jitter = recall_jitter

    @classmethod
    def make_from_config(cls, config):
        """Create a new :class:`Timings` instance from the settings in the
        experimental configuration.

        :param config:

        """
        # TODO: rename config file variable names to be PEP8-compliant
        return Timings(config.wordDuration, config.recallDuration,
                       config.PauseBeforeWords, config.PauseBeforeRecall,
                       config.ISI, config.JitterBeforeWords, config.Jitter,
                       config.JitterBeforeRecall)

    @classmethod
    def make_debug(cls):
        """Create a new :class:`Timings` instance with shorter intervals for
        aiding development.

        """
        return Timings(20, 20, 10, 10, 10, 0, 0, 0)


@six.add_metaclass(ABCMeta)
class Experiment(object):
    """Base class to run a RAM experiment. General usage::

        epl_exp = Experiment(use_eeg=False)
        epl_exp.parseArgs()
        epl_exp.setup()
        epl_exp.setBreak()  # quit with Esc-F1

        experiment = Experiment(epl_exp)
        experiment.connect_to_control_pc()
        experiment.run()

    The general flow is as follows:

    1. Load state.
    2. If state not found, initialize experiment.
    3. Load/initialize session.
    4. Run session.

    :param exputils.Experiment epl_exp: PyEPL experiment instance.
    :param str family: Experiment family (e.g., FR, catFR, ...)
    :param bool debug: Enables debug mode.
    :param dict kwargs: Additional keyword arguments used primarily for debug
         settings.

    """
    def __init__(self, epl_exp, family, debug=False, **kwargs):
        self.family = family
        self.debug = debug
        self.kwargs = kwargs

        assert isinstance(epl_exp, exputils.Experiment)
        self.epl_exp = epl_exp
        self.controller = RAMControl.instance()

        self.clock = exputils.PresentationClock()
        self.config = self.epl_exp.getConfig()
        self.logger = create_logger(
            "experiment", level=(logging.DEBUG if debug else logging.INFO))
        self.event_logger = create_logger("events")

        if self.debug and self.kwargs.get("fast_timing", False):
            self.timings = Timings.make_debug()
        else:
            self.timings = Timings.make_from_config(self.config)

        # Experiment name
        self.name = self.config.experiment

        # Session must be set before creating tracks, apparently
        self.epl_exp.setSession(self.session)

        # Create all tracks
        self.log = LogTrack("session")
        self.mathlog = LogTrack("math")
        self.keyboard = KeyTrack("keyboard")

        # Prepare the experiment if not already done
        if not self.experiment_started:
            self.prepare_experiment()

        # Set up the RAMControl instance
        # TODO: get rid of this monstrosity
        self.controller.configure(self.config.experiment, self.config.version,
                                  self.session, self.subject)

        # Set network log path
        self.controller.socket.log_path = self.session_data_dir

        # Initialize video and audi
        self.video = VideoTrack("video")
        self.audio = CustomAudioTrack("audio")

        # Helpers for common PyEPL routines
        self.epl_helpers = PyEPLHelpers(self.epl_exp, self.video, self.audio,
                                        self.clock)

        # If the session should be skipped, we're done here
        self._ok_to_run = not self._skip_session_dialog()
        if not self._ok_to_run:
            self.log_event('SESSION_SKIPPED')
            self.update_state(session_number=(self.session + 1),
                              session_started=False)
            self.reset_state()
            return

        # Finalize preparation for the session
        self.prepare_session()

    @property
    def subject(self):
        """Subject ID."""
        return self.epl_exp.getOptions().get("subject")

    @property
    def session(self):
        """The session number."""
        try:
            session = self.state.session_number
        except AttributeError:
            session = 0
        return session

    @session.setter
    def session(self, session):
        self.epl_exp.setSession(session)
        self.update_state(session_number=session)

    @property
    def data_root(self):
        """Root directory for data files. Session-specific data will go in
        session files below this directory. Directory structure::

            <root>
            `---- <experiment> <-- what this function should return
                  `---- <subject>
                        `---- <common files>
                        `---- session_<number>
                              `---- <session-specific files>

        See also :meth:`session_data_dir` for accessing the current session
        data directory.

        """
        dirs = self.epl_exp.options["archive"]
        try:
            os.makedirs(dirs)
        except OSError:
            if not osp.exists(dirs):
                raise OSError("Can't make directories: " + dirs)
        return dirs

    @property
    def session_data_dir(self):
        """Return the data directory for the current session."""
        return osp.join(self.data_root, self.subject,
                        "session_{:d}".format(self.session))

    @property
    def experiment_started(self):
        """Has the experiment been started previously?"""
        return True if self.epl_exp.restoreState() is not None else False

    @property
    def session_started(self):
        """Has the session been started previously?"""
        state = self.state
        if state is None:
            return False
        else:
            try:
                return state.session_started
            except AttributeError:  # the session_started state hasn't been set yet
                return False

    def _skip_session_dialog(self):
        """Check if session should be skipped

        :return: True if session is skipped, False otherwise

        """
        try:
            session_number = self.state.session_number
        except AttributeError:
            self.update_state(session_number=0)
            return False

        if self.session_started:
            bc = ButtonChooser(Key('SPACE') & Key('RETURN'), Key('ESCAPE'))
            self.video.clear('black')
            _, button, timestamp = Text(
                'Session %d was previously started\n' % session_number +
                'Press SPACE + RETURN to skip session\n' +
                'Press ESCAPE to continue'
            ).present(self.clock, bc=bc)
            if 'AND' in button.name:
                waitForAnyKey(self.clock, Text('Session skipped\nRestart to run next session'))
                return True
        return False

    @property
    def state(self):
        """Returns the experimental state (implmented via PyEPL). Use the
        :meth:`update_state` method to make persisting changes to the state.

        """
        return self.epl_exp.restoreState()

    def update_state(self, **kwargs):
        """Update the experiment's state with keyword arguments."""
        state = self.epl_exp.restoreState()
        self.epl_exp.saveState(state, **kwargs)

    def reset_state(self):
        """Override this method to reset state appropriately for beginning a
        new session. This is called automatically when skipping a session that
        has already been started *after first incrementing the session number
        and the ``session_started`` flag*.

        """

    def log_event(self, event, **kwargs):
        """Log an event. Logs are currently stored both by PyEPL and in a more
        pandas-friendly JSONized format. The JSON format has one entry per line
        and can be read into a pandas DataFrame like::

            with open("sessionlog.log") as log:
                entries = [json.loads(entry) for entry in log.readlines()]
                df = pd.DataFrame.from_records(entries, index="index")

        :param str event: Event description.
        :param dict kwargs: Additional details to log with event.

        """
        self.log.logMessage(event + " " + json.dumps(kwargs), self.clock)
        kwargs.update({
            "event": event, "timestamp": timing.now()
        })
        msg = json.dumps(kwargs)
        self.event_logger.info(msg)

    @contextmanager
    def state_context(self, state, **kwargs):
        """Context manager to log and send state messages. Usage example::

            with self.state_context("COUNTDOWN"):
                self.do_thing()

        :param str state: Name of state.
        :param dict kwargs: Additional keyword arguments to append to the STATE
            message sent to the host PC.

        """
        self.log_event(state + "_START", **kwargs)
        self.controller.send(StateMessage(state, True, timestamp=timing.now(),
                                          **kwargs))
        yield
        self.controller.send(StateMessage(state, False, timestamp=timing.now(),
                                          **kwargs))
        self.log_event(state + "_END", **kwargs)

    def copy_word_pool(self, data_root, language="en", include_lures=False):
        """Copy word pools to the subject's data root directory. This method
        only needs to be called the first time an experiment is run with a
        given subject.

        FIXME: this should probably be a member of WordTask

        :param str data_root: Path to data root directory.
        :param str language: Language to use for the pools (English or Spanish).
        :param bool include_lures: Include lure word pool.
        :raises LanguageError: when a passed language is unavailable

        """
        logger = create_logger(__name__)
        logger.info("Copying word pool(s)...")

        # Validate language selection
        lang = language[:2].lower()
        if lang not in ["en", "sp"]:
            raise LanguageError("Invalid language: " + lang)
        if include_lures:
            if lang == "sp":
                raise LanguageError("Spanish lures are not yet available.")

        if self.family == "FR":
            cat = False
        elif self.family == "catFR":
            cat = True
        else:
            raise RAMException("Invalid family: ", self.family)
        listgen.write_wordpool_txt(data_root, include_lure_words=include_lures,
                                   categorized=cat)

    def connect_to_control_pc(self):
        """Wait for a connection with the host PC."""
        if self.debug and self.kwargs.get("no_host", False):
            self.logger.warning("***** PROCEEDING WITHOUT CONNECTING TO HOST PC! *****")
        else:
            video = VideoTrack.lastInstance()
            video.clear('black')

            if not self.controller.initiate_connection():
                waitForAnyKey(self.clock,
                              Text(
                                  "CANNOT SYNC TO CONTROL PC\n"
                                  "Check connections and restart the experiment",
                                  size=.05))
                sys.exit(1)  # FIXME

            self.controller.wait_for_start_message(
                poll_callback=lambda: flashStimulus(Text("Waiting for start from control PC...")))

    @abstractmethod
    def define_state_variables(self):
        """Define required experiment-specific state variables here. Overridden
        docstrings should explain what variables are being defined.

        Example for PyEPL::

            self.update_state(is_ughful=True, ughful_index=99)

        """

    @abstractmethod
    def prepare_experiment(self):
        """Code for preparing an entire experiment across all sessions should
        go here.

        This is a byproduct of the weird architecture of PyEPL. Ideally, only
        each session would be prepared rather than pre-initializing everything
        on the first run.

        """

    @abstractmethod
    def prepare_session(self):
        """Code for preparing a specific session of an experiment should go
        here.

        """

    @abstractmethod
    def run(self):
        """Experiment logic should go here."""

    def start(self):
        """Start the experiment."""
        if self._ok_to_run:
            if not self.session_started:
                self.update_state(session_started=True)

            if not self.kwargs.get("no_host", False):
                self.connect_to_control_pc()

            self.logger.info(json.dumps(dict(version=__version__)))

            self.run()

        # Closes stuff and sends EXIT message
        self.controller.send(ExitMessage())

        # Add some buffer time to ensure queued messages get sent
        self.clock.delay(100)
        self.clock.wait()
        self.controller.shutdown()
