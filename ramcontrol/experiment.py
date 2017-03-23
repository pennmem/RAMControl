from __future__ import print_function

from abc import ABCMeta, abstractmethod
import os
import os.path as osp
import sys
import time
import json
import pickle
import codecs
from multiprocessing import Process
from contextlib import contextmanager
import functools
import logging
import atexit

import six
import psutil

from wordpool import WordList
import wordpool.data

import logserver
from logserver import create_logger
from logserver.handlers import SQLiteHandler

from ramcontrol import listgen
from ramcontrol.control import RAMControl
from ramcontrol.util import absjoin
from ramcontrol.exc import LanguageError, ExperimentError, MicTestAbort
from ramcontrol.messages import StateMessage, TrialMessage, ExitMessage
from ramcontrol.extendedPyepl import (
    CustomAudioTrack, customMathDistract, customMicTest
)
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
        if not self.kwargs.get(skip_key, False) and self.debug:
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
    :param bool debug: Enables debug mode.
    :param dict kwargs: Additional keyword arguments used primarily for debug
         settings.

    """
    def __init__(self, epl_exp, debug=False, **kwargs):
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

        # print("config1:\n%s",
        #       json.dumps(self.config.config1.config, indent=2, sort_keys=True))
        # print("config2:\n%s",
        #       json.dumps(self.config.config2.config, indent=2, sort_keys=True))

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

    @staticmethod
    def copy_word_pool(data_root, language="en", include_lures=False):
        """Copy word pools to the subject's data root directory. This method
        only needs to be called the first time an experiment is run with a
        given subject.

        This is only a static method because PyEPL makes it nearly impossible
        to test otherwise.

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

        # Copy wordpool used in experiment...
        with codecs.open(osp.join(data_root, "RAM_wordpool.txt"),
                         "w", encoding="utf-8") as wordfile:
            filename = "ram_wordpool_{:s}.txt".format(lang)
            wordfile.write("\n".join(wordpool.data.read_list(filename)))

        # ... and lures if required
        if include_lures:
            with codecs.open(osp.join(data_root, "RAM_lurepool.txt"),
                             "w", encoding="utf-8") as lurefile:
                filename = "REC1_lures_{:s}.txt".format(lang)
                lurefile.write("\n".join(wordpool.data.read_list(filename)))

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

            self.run()

        # Closes stuff and sends EXIT message
        self.controller.send(ExitMessage())

        # Add some buffer time to ensure queued messages get sent
        self.clock.delay(100)
        self.clock.wait()
        self.controller.shutdown()


class WordTask(Experiment):
    """Class for "word"-based tasks (e.g., free recall)."""
    def define_state_variables(self):
        """Defines the following state variables:

        * ``all_lists`` - generated lists for as many sessions as allowed by
          the config file. Type: list
        * ``list_index`` - current list number. Type: int
        * ``all_rec_blocks`` - generated REC blocks for as many sessions as
          allowed by the config file. Type: list

        All variables are initially set to ``None`` until initialized and are
        accessible as properties.

        """
        kwargs = dict()
        if not hasattr(self.state, "all_lists"):
            kwargs["all_lists"] = None
        if not hasattr(self.state, "list_index"):
            kwargs["list_index"] = None
        if not hasattr(self.state, "rec_blocks"):
            kwargs["all_rec_blocks"] = None
        self.update_state(**kwargs)

    @property
    def all_lists(self):
        return self.state.all_lists

    @all_lists.setter
    def all_lists(self, lists):
        assert isinstance(lists, list)
        self.update_state(all_lists=lists)

    @property
    def list_index(self):
        return self.state.list_index

    @list_index.setter
    def list_index(self, new_index):
        assert isinstance(new_index, int)
        self.update_state(list_index=new_index)

    @property
    def all_rec_blocks(self):
        return self.state.all_rec_blocks

    @all_rec_blocks.setter
    def all_rec_blocks(self, new_blocks):
        assert isinstance(new_blocks, list)
        self.update_state(all_rec_blocks=new_blocks)

    def reset_state(self):
        self.list_index = 0

    def display_word(self, word, listno, serialpos, phase, wait=False,
                     keys=["SPACE"]):
        """Displays a single word in the list.

        :param str word: Word to display.
        :param int listno: List number.
        :param int serialpos: Serial position in the list of the word.
        :param str phase: Experiment "phase": PS, STIM, NON-STIM, BASELINE, or
            PRACTICE.
        :param bool wait: When False, display the word for an amount of time
            set by the experimental configuration; when True, wait until a key
            is pressed.
        :param list keys: List of keys to accept when ``wait`` is True.
        :returns: None if not waiting, otherwise the key pressed and the
            timestamp.

        """
        text = Text(word, size=self.config.wordHeight)

        with self.state_context("WORD", word=word, listno=listno, serialpos=serialpos,
                                phase_type=phase):
            if not wait:
                text.present(self.clock, self.timings.word_duration)
            else:
                key, timestamp = self.epl_helpers.show_text_and_wait_for_keyboard_input(
                    word, self.config.wordHeight, keys)
                return key, timestamp

    @skippable
    def run_instructions(self):
        """Instruction period to explain the task to the subject."""
        with self.state_context("INSTRUCT"):
            filename = absjoin(osp.expanduser(self.kwargs["video_path"]),
                               self.config.introMovie.format(language=self.config.LANGUAGE))
            self.epl_helpers.play_intro_movie(filename)

    @skippable
    def run_confirm(self, text):
        """Display text and wait for confirmation.

        :param str text: Text to display.
        :returns: True if yes, False if no.

        """
        return self.epl_helpers.confirm(text)

    @skippable
    def run_countdown(self):
        """Display the countdown movie."""
        self.video.clear('black')
        with self.state_context("COUNTDOWN"):
            filename = absjoin(osp.expanduser(self.kwargs["video_path"]),
                               self.config.countdownMovie)
            self.epl_helpers.play_movie_sync(filename)

    @skippable
    def run_wait_for_keypress(self, text):
        """Display text and wait for a keypress before continuing.

        :param str text: Text to display.

        """
        with self.state_context("WAITING"):
            waitForAnyKey(self.clock, Text(text))

    @skippable
    def run_mic_test(self):
        with self.state_context("MIC TEST"):
            if not customMicTest(2000, 1.0):
                raise MicTestAbort

    @skippable
    def run_distraction(self, phase_type):
        """Distraction phase."""
        with self.state_context("DISTRACT", phase_type=phase_type):
            problems = self.config.MATH_maxProbs if not self.debug else 1
            customMathDistract(clk=self.clock,
                               mathlog=self.mathlog,
                               numVars=self.config.MATH_numVars,
                               maxProbs=problems,
                               plusAndMinus=self.config.MATH_plusAndMinus,
                               minDuration=self.config.MATH_minDuration,
                               textSize=self.config.MATH_textSize,
                               callback=self.controller.send_math_message)

    @skippable
    def run_encoding(self, words, phase_type):
        """Run an encoding phase.

        :param pd.DataFrame words:
        :param str phase_type: Phase type (BASELINE, ...)

        """
        with self.state_context("ENCODING", phase_type=phase_type):
            for n, row in words.iterrows():
                self.clock.delay(self.timings.isi, self.timings.jitter)
                self.clock.wait()
                self.display_word(row.word, row.listno, n, row.type)

    @skippable
    def run_orient(self, phase_type, orient_text):
        """Run an orient phase.

        :param str phase_type:
        :param str orient_text: The text to display.

        """
        with self.state_context("ORIENT", phase_type=phase_type):
            text = Text(orient_text)

            # FIXME: should I be using encoding timings here?
            text.present(self.clock, self.timings.encoding_delay,
                         jitter=self.timings.encoding_jitter)

            if self.kwargs.get("play_beeps", True):
                self.epl_helpers.play_start_beep()

            self.video.unshow(text)

    @skippable
    def run_retrieval(self, phase_type):
        """Run a retrieval (a.k.a. recall) phase."""
        with self.state_context("RETRIEVAL", phase_type=phase_type):
            label = str(self.list_index)

            # Record responses
            self.audio.record(self.timings.recall_duration, label, t=self.clock)

            # Ending beep
            if self.kwargs.get("play_beeps", True):
                self.epl_helpers.play_stop_beep()

    @skippable
    def run_recognition(self):
        """Run a recognition phase."""
        if not self.config.recognition_enabled:
            raise ExperimentError("Recognition subtask not enabled!")
        rec_list = self.all_rec_blocks[self.session]

        with self.state_context("RECOGNITION"):
            keys = [self.config.recognition_yes_key,
                    self.config.recognition_no_key]
            for n, item in rec_list.iterrows():
                key, timestamp = self.display_word(
                    item.word, item.listno, n, item.type,
                    wait=True, keys=keys)

                yes = key.name == self.config.recognition_yes_key
                no = key.name == self.config.recognition_no_key
                self.log_event("KEYPRESS", key=key.name, yes=yes, no=no)

                if self.debug and n > self.kwargs.get("rec_limit", len(rec_list) - 1):
                    return


class FRExperiment(WordTask):
    """Base for FR tasks."""
    def prepare_experiment(self):
        """Pre-generate all word lists and copy files to the proper locations.

        """
        # Copy word pool to the data directory
        # TODO: only copy lures for tasks using REC1
        self.logger.info("Copying word pool(s) to data directory")
        self.copy_word_pool(osp.join(self.data_root, self.subject),
                            self.config.LANGUAGE, True)

        # Generate all session lists and REC blocks
        self.logger.info("Pre-generating all word lists for %d sessions",
                         self.config.numSessions)
        all_lists = []
        all_rec_blocks = []
        for session in range(self.config.numSessions):
            self.logger.info("Pre-generating word lists for session %d",
                             session)
            pool = listgen.generate_session_pool(language=self.config.LANGUAGE)
            n_baseline = self.config.n_baseline
            n_nonstim = self.config.n_nonstim
            n_stim = self.config.n_stim
            n_ps = self.config.n_ps
            assigned = listgen.assign_list_types(pool, n_baseline, n_nonstim,
                                                 n_stim, n_ps)

            # Create session directory if it doesn't yet exist
            session_dir = osp.join(self.data_root, self.subject,
                                   "session_{:d}".format(session))
            try:
                os.makedirs(session_dir)
            except OSError:
                self.logger.warning("Session %d already created", session)

            # Write assigned list to session folders
            assigned.to_json(osp.join(session_dir, "pool.json"))

            all_lists.append(assigned)

            # Generate recognition phase lists if this experiment supports it
            # and save to session folder
            if self.config.recognition_enabled:
                self.logger.info("Pre-generating REC1 blocks for session %d",
                                 session)

                # Load lures
                # TODO: update when Spanish allowed
                lures = WordList(wordpool.data.read_list("REC1_lures_en.txt"))
                rec_blocks = listgen.generate_rec1_blocks(pool, lures)

                # Save to session folder
                rec_blocks.to_json(osp.join(session_dir, "rec_blocks.json"),
                                   orient="records")

                all_rec_blocks.append(rec_blocks)

        # Store lists and REC blocks in the state
        self.all_lists = all_lists
        self.all_rec_blocks = all_rec_blocks

    def prepare_session(self):
        pass

    def run(self):
        self.video.clear("black")

        # Send session info to the host
        self.controller.send_experiment_info(self.name, self.config.version,
                                             self.subject, self.session)

        self.run_instructions()
        self.run_mic_test()

        # Get the current list
        try:
            idx = self.list_index
        except AttributeError:  # first time
            idx = 0
            self.list_index = idx

        if self.list_index > len(self.all_lists):  # reset required
            self.list_index = 0
        wordlist = self.all_lists[self.list_index].to_dataframe()

        for listno in range(self.list_index, len(wordlist.listno.unique())):
            words = wordlist[wordlist.listno == listno]
            phase_type = words.type.iloc[0]
            assert all(words.type == phase_type)

            # Confirm that we should proceed
            if not self.run_confirm(
                "Running {:s} in session {:d} of {:s}\n({:s}).\n".format(
                    self.subject, self.session, self.name, self.config.LANGUAGE) + \
                            "Press Y to continue, N to quit"):
                self.logger.info("Quitting because reasons")
                return

            with self.state_context("TRIAL", listno=listno, phase_type=phase_type):
                self.log_event("TRIAL", listno=listno, phase_type=phase_type)  # FIXME: host should get this with state message
                self.controller.send(TrialMessage(listno))

                # Countdown to encoding
                self.run_countdown()

                # Encoding
                num = "practice trial" if listno is 0 else "trial {:d}".format(listno)
                self.run_wait_for_keypress("Press any key for {:s}".format(num))
                self.run_encoding(words, phase_type)

                # Distract
                self.run_distraction(phase_type)
                self.run_orient(phase_type, self.config.orientText)

                # Delay before retrieval
                self.clock.delay(self.timings.recall_delay,
                                 jitter=self.timings.recall_jitter)
                self.clock.wait()

                # Retrieval
                self.run_orient(phase_type, self.config.recallStartText)
                if self.config.vad_during_retrieval:
                    with self.controller.voice_detector():
                        self.run_retrieval(phase_type)
                else:
                    self.run_retrieval(phase_type)

            # Update list index stored in state
            self.list_index += 1

        if self.config.recognition_enabled:
            self.run_recognition()

        self.run_wait_for_keypress("Thank you!\nYou have completed the session.")

        # Update session number stored in state and reset list index
        self.session += 1


def run():
    """Entry point for running experiments. This must be run with
    subprocess.Popen because PyEPL is total garbage and hijacks things like
    command line parsing.

    """
    config = pickle.loads(os.environ["RAM_CONFIG"])

    subject = config["subject"]
    experiment = config["experiment"]
    family = config["experiment_family"]
    debug = config["debug"]
    fullscreen = not debug

    here = config["ramcontrol_path"]
    archive_dir = absjoin(config["data_path"], experiment)
    config_file = absjoin(here, "configs", family, "config.py")
    sconfig_file = absjoin(here, "configs", family, experiment + "_config.py")

    # This is only here because PyEPL screws up the voice server if we don't
    # instantiate this *before* the PyEPL experiment.
    RAMControl.instance(voiceserver=config["voiceserver"])

    pid = os.getpid()
    proc = psutil.Process(pid)

    epl_exp = exputils.Experiment(subject=subject,
                                  fullscreen=fullscreen, resolution="1440x900",
                                  use_eeg=False,
                                  archive=archive_dir,
                                  config=config_file,
                                  sconfig=sconfig_file)

    kwargs = {
        "video_path": config["video_path"]
    }
    if debug:
        kwargs.update(config["debug_options"])

    # epl_exp.setup()
    epl_exp.setBreak()  # quit with Esc-F1

    if debug:
        print(json.dumps(epl_exp.getConfig().config1.config, indent=2, sort_keys=True))
        print(json.dumps(epl_exp.getConfig().config2.config, indent=2, sort_keys=True))

    ExperimentClass = getattr(sys.modules[__name__], config["experiment_class"])
    exp = ExperimentClass(epl_exp, debug=debug, **kwargs)

    log_path = osp.join(exp.session_data_dir, "session.sqlite")
    log_args = ([SQLiteHandler(log_path)],)
    log_process = Process(target=logserver.run_server, args=log_args,
                          name="log_process")

    # Some funny business seems to be happening with PyEPL... Shocking, I know.
    @atexit.register
    def cleanup():
        time.sleep(0.25)
        for p in proc.children():
            p.kill()

    log_process.start()
    exp.start()


if __name__ == "__main__":
    run()
