from __future__ import print_function

from abc import ABCMeta, abstractmethod
import os
import os.path as osp
import sys
import json
import codecs
from contextlib import contextmanager
import itertools
import functools
import logging

import six
import psutil

from wordpool import WordList
import wordpool.data
from logserver import create_logger

from ramcontrol import listgen
from ramcontrol.control import RAMControl
from ramcontrol.util import make_env
from ramcontrol.exc import LanguageError, ExperimentError, MicTestAbort
from ramcontrol.messages import StateMessage, TrialMessage
from ramcontrol.extendedPyepl import (
    CustomAudioTrack, waitForAnyKeyWithCallback, customMathDistract,
    customMicTest
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
    given to the :class:`Experiment` instance.

    """
    if not func.__name__.startswith("run_"):
        raise RuntimeError("You can only use this decorator with run_xyz methods!")

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        skip_key = "skip_" + '_'.join(func.__name__.split("_")[1:])
        if not self.kwargs.get(skip_key, False):
            func(self, *args, **kwargs)
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
        self._debug = debug
        self.kwargs = kwargs

        # Read environment variable config
        try:
            self.ram_config_env = json.loads(os.environ["RAM_CONFIG"])
        except KeyError:
            self.ram_config_env = make_env()

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

        self.name = self.config.experiment
        self.subject = self.epl_exp.getOptions().get("subject")

        # Session must be set before creating tracks, apparently
        self.epl_exp.setSession(self.session)

        # Create all tracks
        self.log = LogTrack("session")
        self.mathlog = LogTrack("math")
        self.keyboard = KeyTrack("keyboard")

        # Prepare the experiment if not already done
        if not self.experiment_started:
            self.prepare_experiment()

        # If the session should be skipped, do a hard exit
        if self._should_skip_session():
            sys.exit(0)

        # Finalize preparation for the session
        self.prepare_session()

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

    @property
    def debug(self):
        """Internal flag for enabling debug/development mode."""
        return self._debug

    @debug.setter
    def debug(self, debug):
        self._debug = debug

    @property
    def session(self):
        """The session number."""
        try:
            session = self.state.sessionNum
        except AttributeError:
            session = 0
        return session

    @session.setter
    def session(self, session):
        self.epl_exp.setSession(session)
        self.update_state(sessionNum=session)

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
    def log_filename(self):
        """Return the JSON (for now) log filename.

        This appends a new JSON object on each line, so newlines are not
        supported within the log.

        """
        return osp.join(self.session_data_dir, "sessionlog.log")

    @property
    def experiment_started(self):
        """Has the experiment been started previously?"""
        return True if self.epl_exp.restoreState() is not None else False

    @property
    def session_started(self):
        """Has the session been started previously?"""
        state = self.epl_exp.restoreState()
        if state is None:
            return False
        else:
            try:
                return state.session_started
            except AttributeError:  # a crash most likely happened last time
                return False

    def _should_skip_session(self):
        """Check if session should be skipped

        :return: True if session is skipped, False otherwise

        """
        if self.session_started:
            bc = ButtonChooser(Key('SPACE') & Key('RETURN'), Key('ESCAPE'))
            self.video.clear('black')
            _, button, timestamp = Text(
                'Session %d was previously started\n' % (self.state.sessionNum + 1) +
                'Press SPACE + RETURN to skip session\n' +
                'Press ESCAPE to continue'
            ).present(self.clock, bc=bc)
            if 'AND' in button.name:
                self.log_event('SESSION_SKIPPED')
                self.state.sessionNum += 1
                self.state.trialNum = 0
                self.state.practiceDone = False
                self.state.session_started = False
                self.epl_exp.saveState(self.state)
                waitForAnyKey(self.clock, Text('Session skipped\nRestart RAM_%s to run next session' %
                                               self.config.experiment))
                return True
        return False

    # TODO: this would be good to add, probably
    # @abstractmethod
    # def validate_config(self, config):
    #     """Implement this method to validate passed configuration before
    #     running an experiment. This is to avoid crashes during run time due to
    #     misconfiguration.
    #
    #     This should raise :class:`AssertionError`s when something is
    #     misconfigured.
    #
    #     """

    @property
    def state(self):
        """Returns the experimental state (implmented via PyEPL)."""
        return self.epl_exp.restoreState()

    # TODO: figure out how to do this properly with PyEPL
    # @state.setter
    # def state(self, new_state):
    #     self.update_state()

    def update_state(self, **kwargs):
        """Update the experiment's state with keyword arguments."""
        state = self.epl_exp.restoreState()
        self.epl_exp.saveState(state, **kwargs)

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
        with open(self.log_filename, "a") as logfile:
            kwargs.update({
                "event": event, "timestamp": timing.now()
            })
            msg = json.dumps(kwargs)
            logfile.write("{:s}\n".format(msg))
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
        if not self.ram_config_env["no_host"]:
            if not self.config.control_pc:
                return
            video = VideoTrack.lastInstance()
            video.clear('black')

            if not self.controller.initiate_connection():
                waitForAnyKey(self.clock,
                              Text(
                                  "CANNOT SYNC TO CONTROL PC\n"
                                  "Check connections and restart the experiment",
                                  size=.05))
                sys.exit(1)

            self.controller.wait_for_start_message(
                poll_callback=lambda: flashStimulus(Text("Waiting for start from control PC...")))
        else:
            self.logger.warning("***** PROCEEDING WITHOUT CONNECTING TO HOST PC! *****")

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
        self.run()

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

        """
        text = Text(word, size=self.config.wordHeight)

        with self.state_context("WORD", word=word, listno=listno, serialpos=serialpos,
                                phase_type=phase):
            if not wait:
                text.present(self.clock, self.timings.word_duration)
            else:
                key, timestamp = self.epl_helpers.show_text_and_wait_for_keyboard_input(
                    word, self.config.wordHeight, keys)
                # TODO: send key log to host PC (PyEPL already logs it)

    @skippable
    def run_instructions(self):
        """Instruction period to explain the task to the subject."""
        with self.state_context("INSTRUCT"):
            self.epl_helpers.play_intro_movie(
                self.config.introMovie.format(language=self.config.LANGUAGE))

    @skippable
    def run_countdown(self):
        """Display the countdown movie."""
        self.video.clear('black')
        with self.state_context("COUNTDOWN"):
            self.epl_helpers.play_movie_sync(self.config.countdownMovie)

    @skippable
    def run_mic_test(self):
        with self.state_context("MIC TEST"):
            if not customMicTest(2000, 1.0):
                raise MicTestAbort

    @skippable
    def run_distraction(self, phase_type):
        """Distraction phase."""
        with self.state_context("DISTRACT", phase_type=phase_type):
            problems = self.config.MATH_maxProbs if not self._debug else 1
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
    def run_orient(self, phase_type):
        """Run an orient phase."""
        with self.state_context("ORIENT", phase_type=phase_type):
            text = Text(self.config.recallStartText)

            # FIXME: should I be using encoding timings here?
            text.present(self.clock, self.timings.encoding_delay,
                         jitter=self.timings.encoding_jitter)

            if self.kwargs.get("play_beeps", True):
                self.epl_helpers.play_start_beep()

            #self.clock.delay(self.timings.encoding_delay,
            #                 jitter=self.timings.encoding_jitter)
            #self.clock.wait()

            self.video.unshow(text)

    @skippable
    def run_retrieval(self, phase_type):
        """Run a retrieval (a.k.a. recall) phase."""
        with self.state_context("RETRIEVAL", phase_type=phase_type):
            label = str(self.list_index)

            # Record responses
            rec, timestamp = self.audio.record(
                self.timings.recall_duration, label, t=self.clock)

            # Ending beep
            if self.kwargs.get("play_beeps", True):
                end_timestamp = self.epl_helpers.play_stop_beep()

    @skippable
    def run_recognition(self):
        """Run a recognition phase."""
        if not self.config.recognition_enabled:
            raise ExperimentError("Recognition subtask not enabled!")
        rec_list = self.all_rec_blocks[self.session]

        with self.state_context("RECOGNITION"):
            for n, item in rec_list.iterrows():
                self.display_word(item.word, item.listno, n, item.type, wait=True)
                if self.debug and n > 0:
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

            if phase_type == "PRACTICE" and self.kwargs["skip_practice"]:
                self.controller.send(TrialMessage(listno))
                self.log_event("TRIAL", listno=listno, phase_type=phase_type)

                # Countdown to encoding
                self.run_countdown()

                # Encoding
                self.run_encoding(words, phase_type)

                # Distract
                self.run_distraction(phase_type)
                self.run_orient(phase_type)

                # Delay before retrieval
                self.clock.delay(self.timings.recall_delay,
                                 jitter=self.timings.recall_jitter)
                self.clock.wait()

                # Retrieval
                self.run_orient(phase_type)
                self.run_retrieval(phase_type)

            # Update list index stored in state
            self.list_index += 1

        if self.config.recognition_enabled:
            self.run_recognition()

        # Update session number stored in state and reset list index
        self.session += 1

# class CatFRExperiment(FRExperiment):
#     """Base for CatFR tasks."""
#
#
# class PALExperiment(WordTask):
#     """Base for PAL tasks."""


if __name__ == "__main__":
    import os
    import os.path as osp
    import time
    from multiprocessing import Process
    import atexit

    import logserver
    from logserver.handlers import SQLiteHandler
    from ramcontrol.util import fake_subject

    os.environ["RAM_CONFIG"] = json.dumps(make_env(no_host=True, voiceserver=True))

    # This is only here because PyEPL screws up the voice server if we don't
    # instantiate this *before* the PyEPL experiment.
    RAMControl.instance()

    pid = os.getpid()
    proc = psutil.Process(pid)

    here = osp.realpath(osp.dirname(__file__))

    subject = "R0000P"  # fake_subject()
    exp_name = "FR5"
    archive_dir = osp.abspath(osp.join(here, "..", "data", exp_name))
    config_str = osp.abspath(osp.join(here, "configs", "FR", "config.py"))
    sconfig_str = osp.abspath(osp.join(here, "configs", "FR", exp_name + "_config.py"))

    epl_exp = exputils.Experiment(subject=subject, fullscreen=False,
                                  archive=archive_dir,
                                  use_eeg=False, config=config_str,
                                  sconfig=sconfig_str,
                                  resolution="1440x900")

    # epl_exp.parseArgs()
    epl_exp.setup()
    epl_exp.setBreak()  # quit with Esc-F1

    kwargs = {
        # Uncomment things to skip stuff for development
        "skip_countdown": True,
        "skip_distraction": True,
        "skip_encoding": True,
        "skip_instructions": True,
        "skip_mic_test": True,
        "skip_orient": True,
        "skip_practice": True,
        "skip_retrieval": True,
        # "skip_recognition": True,

        "fast_timing": True,
        "play_beeps": False
    }

    exp = FRExperiment(epl_exp, debug=True, **kwargs)

    log_path = osp.join(exp.session_data_dir, "logs.sqlite")
    log_args = ([SQLiteHandler(log_path)],)
    log_process = Process(target=logserver.run_server, args=log_args,
                          name="log_process")

    # Some funny business seems to be happening with PyEPL...
    @atexit.register
    def cleanup():
        time.sleep(0.25)
        for p in proc.children():
            p.kill()

    log_process.start()
    exp.start()
