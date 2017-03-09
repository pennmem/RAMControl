from abc import ABCMeta, abstractmethod
import os
import os.path as osp
import sys
import json
import codecs
from contextlib import contextmanager
import logging
from collections import namedtuple

import six
import numpy as np

from wordpool import WordList, WordPool
import wordpool.data
from ramcontrol import listgen
from ramcontrol.control import RAMControl
from ramcontrol.util import DEFAULT_ENV
from ramcontrol.exc import LanguageError
from ramcontrol.messages import (
    StateMessage
)
from ramcontrol.extendedPyepl import (
    CustomAudioTrack, waitForAnyKeyWithCallback, customMathDistract
)
from ramcontrol.epl import play_intro_movie

from pyepl import exputils, timing
from pyepl.display import VideoTrack, Text
from pyepl.keyboard import KeyTrack, Key
from pyepl.mechinput import ButtonChooser
from pyepl.textlog import LogTrack
from pyepl.convenience import waitForAnyKey, flashStimulus

logger = logging.getLogger(__name__)


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

    :param exputils.Experiment epl_exp:

    """
    def __init__(self, epl_exp):
        assert isinstance(epl_exp, exputils.Experiment)
        self.epl_exp = epl_exp
        self.controller = RAMControl.instance()

        self.clock = exputils.PresentationClock()
        self.config = self.epl_exp.getConfig()
        logger.debug("config1:\n%s",
                     json.dumps(self.config.config1.config, indent=2, sort_keys=True))
        logger.debug("config2:\n%s",
                     json.dumps(self.config.config2.config, indent=2, sort_keys=True))
        self.name = self.config.experiment
        self.subject = self.epl_exp.getOptions().get("subject")

        # Session must be set before creating tracks, apparently
        state = self.epl_exp.restoreState()
        try:
            session = state.sessionNum
        except AttributeError:
            session = 0
        self.epl_exp.setSession(session)
        self.session = session

        # Create all tracks
        self.log = LogTrack("session")
        self.mathlog = LogTrack("math")
        self.keyboard = KeyTrack("keyboard")
        self.video = VideoTrack("video")
        self.audio = CustomAudioTrack("audio")

        # Read environment variable config
        try:
            self.ram_config_env = json.loads(os.environ["RAM_CONFIG"])
        except KeyError:
            self.ram_config_env = DEFAULT_ENV

        # Prepare the experiment if not already done
        if not self.experiment_started:
            self.prepare_experiment()
        # TODO: save/restore state here??? or just do it in prepare_experiment

        # If the session should be skipped, do a hard exit
        if self._should_skip_session(state):
            sys.exit(0)

        # Finalize preparation for the session
        self.prepare_session()

        # Set up the RAMControl instance
        # TODO: get rid of this monstrosity
        self.controller.configure(self.config.experiment, self.config.version,
                                  session,
                                  "" if not hasattr(self.config, "stim_type") else self.config.stim_type,
                                  self.subject)

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
        state = self.epl_exp.restoreState()
        if state is None:
            return False
        else:
            try:
                return state.session_started
            except AttributeError:  # a crash most likely happened last time
                return False

    def _should_skip_session(self, state):
        """Check if session should be skipped

        :return: True if session is skipped, False otherwise

        """
        if self.session_started:
            bc = ButtonChooser(Key('SPACE') & Key('RETURN'), Key('ESCAPE'))
            self.video.clear('black')
            _, button, timestamp = Text(
                'Session %d was previously started\n' % (state.sessionNum + 1) +
                'Press SPACE + RETURN to skip session\n' +
                'Press ESCAPE to continue'
            ).present(self.clock, bc=bc)
            if 'AND' in button.name:
                self.log_message('SESSION_SKIPPED', timestamp)
                state.sessionNum += 1
                state.trialNum = 0
                state.practiceDone = False
                state.session_started = False
                self.epl_exp.saveState(state)
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

    @contextmanager
    def state_context(self, state):
        """Context manager to log and send state messages. Usage example::

            with self.state_context("COUNTDOWN") as state:
                self.countdown()
                # Do something with state. Or not. It's really up to you.

        :param str state: Name of state.

        """
        exp_state = self.epl_exp.restoreState()
        self.log.logMessage(state + "_START", self.clock)
        self.controller.send(StateMessage(state, True, timestamp=timing.now()))
        yield exp_state
        self.controller.send(StateMessage(state, False, timestamp=timing.now()))
        self.log.logMessage(state + "_END", self.clock)

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
            print("***** PROCEEDING WITHOUT CONNECTING TO HOST PC! *****")

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


class WordTask(Experiment):
    """Class for "word"-based tasks (e.g., free recall)."""
    def define_state_variables(self):
        """Defines the following state variables:

        * ``all_lists`` - generated lists for as many sessions as allowed by
          the config file. Type: list
        * ``list_index`` - current list number. Type: int

        All variables are initially set to ``None`` until initialized and are
        accessible as properties.

        """
        kwargs = dict()
        if not hasattr(self.state, "all_lists"):
            kwargs["all_lists"] = None
        if not hasattr(self.state, "list_index"):
            kwargs["list_index"] = None
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
        assert isinstance(new_index, list)
        self.update_state(list_index=new_index)

    def run_instructions(self):
        """Instruction period to explain the task to the subject."""
        with self.state_context("INSTRUCT"):
            play_intro_movie(self.epl_exp, self.video, self.keyboard, True,
                             self.config.LANGUAGE)

    def run_distraction(self):
        """Distraction phase."""
        with self.state_context("DISTRACT"):  # TODO: check on save
            customMathDistract(clk=self.clock,
                               mathlog=self.mathlog,
                               numVars=self.config.MATH_numVars,
                               maxProbs=self.config.MATH_maxProbs,
                               plusAndMinus=self.config.MATH_plusAndMinus,
                               minDuration=self.config.MATH_minDuration,
                               textSize=self.config.MATH_textSize,
                               callback=self.control.send_math_message)

    def run_encoding(self):
        """Run an encoding phase."""
        with self.state_context("ENCODING_PHASE"):
            pass
            # 0. log trial number
            # 1. resynchronize (not used)
            # 2. countdown
            # 3. crosshairs

    def run_practice(self, words):
        """Run a practice encoding phase.

        :param list words: Words to use in the practice encoding phase.

        """
        with self.state_context("PRACTICE") as state:
            self.clock.tare()  # FIXME: is this necessary?
            self.run_encoding()

        filename = "FIXME"  # path to instructions in the appropriate langauge
        waitForAnyKeyWithCallback(
            self.clock,
            Text(codecs.open(filename, encoding='utf-8').read()),
                 onscreenCallback=lambda: self.controller.send(StateMessage('INSTRUCT', True)),
                 offscreenCallback=lambda: self.controller.send(StateMessage('INSTRUCT', False)))

    def run_orient(self):
        """Run an orient (crosshairs) phase."""
        with self.state_context("ORIENT"):
            start_text = self.video.showCentered(
                Text(self.config.recallStartText,
                     size=self.config.wordHeight))
            self.start_beep.present(self.clock)
            self.video.unshow(start_text)

    def run_retrieval(self):
        """Run a retrieval (a.k.a. recall) phase."""
        # Delay before recall
        # TODO: maybe move to general run method
        self.clock.delay(self.config.PauseBeforeRecall,
                         jitter=self.config.JitterBeforeRecall)

        # TODO: maybe move to general run method
        self.run_orient()

        with self.state_context("RETRIEVAL") as state:
            label = str(state.trialNum)

            # Record responses
            rec, timestamp = self.audio.record(
                self.config.recallDuration, label, t=self.clock)

            # Ending beep
            end_timestamp = self.stop_beep.present(self.clock)

    def run_recognition(self):
        """Run a recognition phase."""


class FRExperiment(WordTask):
    """Base for FR tasks."""
    def prepare_experiment(self):
        """Pre-generate all word lists and copy files to the proper locations.

        """
        # Copy word pool to the data directory
        # TODO: only copy lures for tasks using REC1
        self.copy_word_pool(self.data_root, self.config.LANGUAGE, True)

        # Generate all session lists
        all_lists = []
        for session in range(self.config.numSessions):
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
                logger.warning("Session %d already created", session)

            # Write assigned list to session folders
            assigned.to_json(osp.join(session_dir, "pool.json"))

            all_lists.append(assigned)

        # Store lists in the state
        self.all_lists = all_lists

        # Generate recognition phase lists if this experiment supports it
        if self.config.recognition_enabled:
            # Load lures
            # TODO: update when Spanish allowed
            lures = WordList(wordpool.data.read_list("REC1_lures_en.txt"))

    def prepare_session(self):
        pass

    def run(self):
        self.run_instructions()

        # for listno, list_ in enumerate(lists):
        #     if
        #     self.run_practice(words)

# class CatFRExperiment(FRExperiment):
#     """Base for CatFR tasks."""
#
#
# class PALExperiment(WordTask):
#     """Base for PAL tasks."""


if __name__ == "__main__":
    import os.path as osp
    from ramcontrol.util import fake_subject
    here = osp.realpath(osp.dirname(__file__))

    logging.basicConfig(level=logging.DEBUG)

    subject = fake_subject()
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
    print(epl_exp.options)
    epl_exp.setup()
    epl_exp.setBreak()  # quit with Esc-F1

    exp = FRExperiment(epl_exp)
    exp.run()
