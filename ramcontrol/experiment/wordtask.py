import os.path as osp

from ..extendedPyepl import customMathDistract, customMicTest
from ..util import absjoin, get_instructions
from ..exc import ExperimentError, MicTestAbort
from .experiment import Experiment, skippable

from pyepl.display import Text
from pyepl.convenience import waitForAnyKey


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

    def display_word(self, word_info, serialpos, wait=False, keys=["SPACE"]):
        """Displays a single word in the list.

        :param pd.Series word_info: Word to display and metadata.
        :param int serialpos: Serial position in the list of the word.
        :param bool wait: When False, display the word for an amount of time
            set by the experimental configuration; when True, wait until a key
            is pressed.
        :param list keys: List of keys to accept when ``wait`` is True.
        :returns: None if not waiting, otherwise the key pressed and the
            timestamp.

        """
        text = Text(word_info.word, size=self.config.wordHeight)

        kwargs = {
            "word": word_info.word,
            "listno": word_info.listno,
            "serialpos": serialpos,
            "phase_type": word_info.type
        }
        kwargs.update({
            key: word_info[key]
            for key in word_info.index
            if key not in ["word", "listno", "type"]
        })
        with self.state_context("WORD", **kwargs):
            if not wait:
                text.present(self.clock, self.timings.word_duration)
            else:
                key, timestamp = self.epl_helpers.show_text_and_wait_for_keyboard_input(
                    word_info.word, self.config.wordHeight, keys)
                return key, timestamp



    @skippable
    def run_instructions(self, allow_skip):
        """Instruction period to explain the task to the subject.

        :param bool allow_skip: True if allowed to skip the video.

        """
        with self.state_context("INSTRUCT"):
            filename = absjoin(osp.expanduser(self.kwargs["video_path"]),
                               self.config.introMovie.format(language=self.config.LANGUAGE))
            self.epl_helpers.play_intro_movie(filename, allow_skip=allow_skip)

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
        if self.debug:
            min_duration = self.kwargs.get("min_distraction_duration", self.config.MATH_minDuration)
        else:
            min_duration = self.config.MATH_minDuration

        num_problems = 1 if self.debug and self.kwargs.get("one_math_problem", False) else self.config.MATH_maxProbs
        with self.state_context("DISTRACT", phase_type=phase_type):
            customMathDistract(clk=self.clock,
                               mathlog=self.mathlog,
                               numVars=self.config.MATH_numVars,
                               maxProbs=num_problems,
                               plusAndMinus=self.config.MATH_plusAndMinus,
                               minDuration=min_duration,
                               textSize=self.config.MATH_textSize,
                               callback=self.controller.send_math_message)

    @skippable
    def run_encoding(self, words, phase_type):
        """Run an encoding phase.

        :param pd.DataFrame words:
        :param str phase_type: Phase type (BASELINE, ...)

        """
        with self.state_context("ENCODING", phase_type=phase_type):
            for n, (_, row) in enumerate(words.iterrows()):
                self.clock.delay(self.timings.isi, self.timings.jitter)
                self.clock.wait()
                self.display_word(row, n)

    @skippable
    def run_orient(self, phase_type, orient_text, beep=False):
        """Run an orient phase.

        :param str phase_type:
        :param str orient_text: The text to display.
        :param bool beep: Whether or not to play a beep.

        """
        with self.state_context("ORIENT", phase_type=phase_type):
            text = Text(orient_text)

            text.present(self.clock, self.timings.encoding_delay,
                         jitter=self.timings.encoding_jitter)

            if self.kwargs.get("play_beeps", True) and beep:
                self.epl_helpers.play_start_beep()

            self.video.unshow(text)

    @skippable
    def run_retrieval(self, phase_type):
        """Run a retrieval (a.k.a. recall) phase."""
        self.clock.delay(self.config.PauseBeforeRecall, jitter=self.config.JitterBeforeRecall)

        if not (self.debug and self.kwargs.get("skip_orient", False)):
            with self.state_context("RETRIEVAL_ORIENT"):
                start_text = self.video.showCentered(
                    Text(self.config.recallStartText,
                         size=self.config.wordHeight))
                self.video.updateScreen(self.clock)
                self.epl_helpers.play_start_beep()
                self.clock.delay(self.config.PauseBeforeRecall)
                self.clock.wait()
                self.video.unshow(start_text)
                self.video.updateScreen(self.clock)

        with self.controller.voice_detector():  # this should do nothing if VAD is disabled
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

        with self.state_context("RECOGNITION_INSTRUCT"):
            # FIXME: allow Spanish
            text = get_instructions("rec1_en.txt").format(
                recognition_no_key=self.config.recognition_no_key,
                recognition_yes_key=self.config.recognition_yes_key
            )
            self.epl_helpers.show_text_and_wait(text, 0.05)

        with self.state_context("RECOGNITION"):
            keys = [self.config.recognition_yes_key,
                    self.config.recognition_no_key]
            for n, item in rec_list.iterrows():
                key, timestamp = self.display_word(item, n, wait=True, keys=keys)

                yes = key.name == self.config.recognition_yes_key
                no = key.name == self.config.recognition_no_key
                self.log_event("KEYPRESS", key=key.name, yes=yes, no=no)

                if self.debug and n > self.kwargs.get("rec_limit", len(rec_list) - 1):
                    return
