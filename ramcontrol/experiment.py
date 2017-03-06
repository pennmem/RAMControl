from abc import ABCMeta, abstractmethod
import json
import os
import sys
import six

from ramcontrol.control import RAMControl
from ramcontrol.extendedPyepl import CustomAudioTrack
from pyepl import exputils
from pyepl.display import VideoTrack, Text
from pyepl.keyboard import KeyTrack, Key
from pyepl.mechinput import ButtonChooser
from pyepl.textlog import LogTrack
from pyepl.convenience import waitForAnyKey, flashStimulus

ram_control = RAMControl.instance()


@six.add_metaclass(ABCMeta)
class Experiment(object):
    """Base class to run a RAM experiment. General usage::

        epl_exp = Experiment()
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
        self.experiment = epl_exp

        self.clock = exputils.PresentationClock()
        self.config = self.experiment.getConfig()
        self.name = self.config.experiment

        # Session must be set before creating tracks, apparently
        state = self.experiment.restoreState()
        try:
            session = state.sessionNum
        except AttributeError:
            session = 0
        self.experiment.setSession(session)

        # Create all tracks
        self.log = LogTrack("session")
        self.mathlog = LogTrack("math")
        self.keyboard = KeyTrack("keyboard")
        self.video = VideoTrack("video")
        self.audio = CustomAudioTrack("audio")

        # Prepare the experiment if not already done
        if not self.experiment_started:
            self.prepare_experiment()
        # TODO: save/restore state here??? or just do it in prepare_experiment

        # Read environment variable config
        self.ram_config_env = json.loads(os.environ["RAM_CONFIG"])

        # If the session should be skipped, do a hard exit
        if self._should_skip_session(state):
            sys.exit(0)

        # Set up the RAMControl instance
        ram_control.configure(self.config.experiment, self.config.version,
                              session, self.config.stim_type,
                              self.config.subject, self.config.state_list)

    @property
    def experiment_started(self):
        """Has the experiment been started previously?"""
        return True if self.exp.restoreState() is not None else False

    @property
    def session_started(self):
        """Has the session been started previously?"""
        return self.exp.restoreState().session_started

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
                self.experiment.saveState(state)
                waitForAnyKey(self.clock, Text('Session skipped\nRestart RAM_%s to run next session' %
                                               self.config.experiment))
                return True
        return False

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

    def connect_to_control_pc(self):
        if not self.ram_config_env["no_host"]:
            if not self.config.control_pc:
                return
            video = VideoTrack.lastInstance()
            video.clear('black')

            if not ram_control.initiate_connection():
                waitForAnyKey(self.clock,
                              Text(
                                  "CANNOT SYNC TO CONTROL PC\n"
                                  "Check connections and restart the experiment",
                                  size=.05))
                sys.exit(1)

            cb = lambda: flashStimulus(
                Text("Waiting for start from control PC..."))
            ram_control.wait_for_start_message(poll_callback=cb)
        else:
            print("***** PROCEEDING WITHOUT CONNECTING TO HOST PC! *****")

    @abstractmethod
    def prepare_experiment(self):
        """Code for preparing an entire experiment across all sessions should
        go here.

        This is a byproduct of the weird architecture of PyEPL. Ideally, only
        each session would be prepared rather than pre-initializing everything
        on the first run.

        """

    @abstractmethod
    def run(self):
        """Experiment logic should go here."""


class WordTask(Experiment):
    """Class for "word"-based tasks (e.g., free recall).

    This class mainly exists to define helpers common to all RAM verbal tasks.

    """
    def run_instructions(self):
        """Instruction period to explain the task to the subject."""

    def run_distraction(self):
        """Distraction phase."""


class FRExperiment(WordTask):
    """Base for FR tasks.

    :param pyepl.exputils.Experiment:
    :param

    """
    def __init__(self, experiment, clock, log, mathlog, video, audio):
        self.experiment = experiment
        self.
        super(FRExperiment, self).__init__("FRx", config)

    def prepare_experiment(self):
        """Pre-generate all word lists and copy files to the proper locations.

        """
        # copy word pool

    def run(self):
        self.run_instructions()


# class CatFRExperiment(FRExperiment):
#     """Base for CatFR tasks."""
#
#
# class PALExperiment(WordTask):
#     """Base for PAL tasks."""
