import os
import os.path as osp
import codecs

from .. import listgen
from ..messages import TrialMessage
from ..exc import ExperimentError
from ..util import get_instructions
from .wordtask import WordTask
from .experiment import skippable
from random import shuffle

from pyepl.display import Text
from pyepl.convenience import waitForAnyKey

class PALExperiment(WordTask):


    def make_test_order(self):
        evens = range(0,self.config.n_pairs,2)
        odds = range(1,self.config.n_pairs,2)
        shuffle(odds)
        shuffle(evens)
        order = []
        for i in range(self.config.n_pairs):
            order.append(odds.pop() if i%2 else evens.pop())
        return order


    def run_cued_retrieval(self, words, phase_type):
        order = self.make_test_order()
        with self.state_context("RETRIEVAL", phase_type=phase_type):
            for row_ind in order:
                row = words.iloc[row_ind]
                self.clock.delay(self.config.pre_cue, self.config.pre_cue_jitter)
                self.clock.wait()
                self.display_cue(row,row_ind)

    def display_cue(self, word_info,serialpos):
        direction = (word_info['cue_pos'] == 'word2')
        kwargs = {
            'probe': word_info[word_info['cue_pos']],
            'expecting': word_info['word1' if direction else 'word2'],
            'direction': int(direction),
            'serialpos':serialpos
        }

        text = Text(word_info[word_info.cue_pos], size=self.config.wordHeight)

        with self.state_context('REC', **kwargs):
            with self.state_context('PROBE', **kwargs):
                text.present(self.clock, self.config.cue_duration)

            self.clock.delay(self.config.post_cue)
            self.clock.wait()

    @skippable
    def run_encoding(self, words, phase_type):
        """Run an encoding phase.

        :param pd.DataFrame words:
        :param str phase_type: Phase type (BASELINE, ...)

        """
        with self.state_context("ENCODING", phase_type=phase_type):
            for n, (_, row) in enumerate(words.iterrows()):
                self.run_orient(phase_type, self.config.orientText)
                self.clock.delay(self.timings.isi, self.timings.jitter)
                self.clock.wait()
                self.display_word(row, n)

    def display_word(self, word_info, serialpos, wait=False, keys=["SPACE"]):
        text = Text('{}\n\n{}'.format(word_info.word1, word_info.word2))

        kwargs = {
            'word1': word_info.word1,
            'word2': word_info.word2,
            'listno': word_info.listno,
            'serialpos': serialpos,
            'phase_type': word_info.type,
        }
        kwargs.update({
                          key: word_info[key] for key in word_info.index
                          if key not in ['word1', 'word2', 'listno', 'type']
                          })
        with self.state_context('STUDY_PAIR', **kwargs):
            if not wait:
                text.present(self.clock, self.timings.word_duration)
            else:
                key, timestamp = self.epl_helpers.show_text_and_wait_for_keyboard_input(
                    '{}\n\n{}'.format(word_info.word1, word_info.word2),
                    self.config.wordHeight, keys)
                return key, timestamp

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
        all_sessions = listgen.pal.generate_n_session_pairs(self.config.numSessions)
        for session,pool in enumerate(all_sessions):
            # self.logger.info("Pre-generating word lists for session %d",
            #                  session)
            n_baseline = self.config.n_baseline
            n_nonstim = self.config.n_nonstim
            n_stim = self.config.n_stim
            n_ps = self.config.n_ps
            if self.debug:
                print(pool)

            if self.config.experiment=="PAL3":
                assigned = listgen.assign_balanced_list_types(pool,n_baseline,n_nonstim,n_stim,n_ps,num_groups=2)
            else:
                assigned = listgen.assign_list_types(pool, n_baseline, n_nonstim,
                                                 n_stim, n_ps)

            if self.debug:
                print(assigned)

            all_lists.append(assigned)

            # Create session directory if it doesn't yet exist
            session_dir = osp.join(self.data_root, self.subject,
                                   "session_{:d}".format(session))
            try:
                os.makedirs(session_dir)
            except OSError:
                self.logger.warning("Session %d already created", session)

            # Write assigned list to session folders
            assigned.to_csv(osp.join(session_dir, "pool.tsv"), sep='\t')

            # Write .lst files to session folders (used in TotalRecall
            # during annotation).
            for listno in sorted(assigned.listno.unique()):
                name = "{:d}.lst".format(listno)
                entries = assigned[assigned.listno == listno]
                with codecs.open(osp.join(session_dir, name), 'w', encoding="utf8") as f:
                    f.writelines(row.word1 + "\t" +row.word2 + "\n" for _, row in entries.iterrows())


            # Generate recognition phase lists if this experiment supports it
            # and save to session folder
            if self.config.recognition_enabled:
                self.logger.info("Pre-generating REC1 blocks for session %d",
                                 session)

                # Load lures
                # TODO: update when Spanish allowed
                lures = listgen.LURES_LIST_EN
                rec_blocks = listgen.generate_rec1_blocks(pool, lures)

                # Save to session folder
                rec_blocks.to_json(osp.join(session_dir, "rec_blocks.json"),
                                   orient="records")

                all_rec_blocks.append(rec_blocks)

        # Store lists and REC blocks in the state
        self.all_lists = all_lists
        self.all_rec_blocks = all_rec_blocks

    def prepare_session(self):
        # Nothing to do here, but this is an abstract method so must be
        # implemented.
        pass

    def run(self):
        self.video.clear("black")

        # Send session info to the host
        self.controller.send_experiment_info(self.name, self.config.version,
                                             self.subject, self.session)

        # Get the current list
        try:
            idx = self.list_index
        except AttributeError:  # first time
            idx = 0
            self.list_index = idx

        if self.list_index > len(self.all_lists):  # reset required
            self.list_index = 0
        wordlist = self.all_lists[self.list_index]

        self.run_instructions(allow_skip=(self.session > 0))

        # Confirm that we should proceed
        if not self.run_confirm(
            "Running {:s} in session {:d} of {:s}\n({:s}).\n".format(
                self.subject, self.session, self.name,
                self.config.LANGUAGE) + "Press Y to continue, N to quit"):
            self.logger.info("Quitting due to negative confirmation.")
            return

        self.run_mic_test()

        for listno in range(self.list_index, len(wordlist.listno.unique())):
            words = wordlist[wordlist.listno == listno]

            # check that phase type assignments are correct
            phase_type = words.type.iloc[0]
            assert all(words.type == phase_type)

            with self.state_context("TRIAL", listno=listno, phase_type=phase_type):
                self.log_event("TRIAL", listno=listno, phase_type=phase_type)  # FIXME: host should get this with state message
                self.controller.send(TrialMessage(listno))

                # Countdown to encoding
                num = "practice trial" if listno is 0 else "trial {:d}".format(
                    listno)
                self.run_wait_for_keypress("Press any key for {:s}".format(num))
                self.run_countdown()

                # Encoding
                self.run_orient(phase_type,self.config.encodingStartText,beep=True)
                self.run_encoding(words, phase_type)

                # Distract
                self.run_distraction(phase_type)

                # Delay before retrieval
                self.clock.delay(self.timings.recall_delay,
                                 jitter=self.timings.recall_jitter)
                self.clock.wait()

                # Retrieval
                self.run_orient(phase_type,self.config.recallStartText,beep=True)
                self.run_cued_retrieval(words,phase_type)

                if phase_type == "PRACTICE":
                    with self.state_context("PRACTICE_POST_INSTRUCT"):
                        text = get_instructions("fr_post_practice_{:s}.txt".format(
                            self.config.LANGUAGE.lower()))
                        self.epl_helpers.show_text_and_wait(text, 0.05)

            # Update list index stored in state
            self.list_index += 1

        if self.config.recognition_enabled:
            self.run_recognition()

        self.run_wait_for_keypress("Thank you!\nYou have completed the session.")

        # Update session number stored in state and reset list index
        self.update_state(
            session_number=self.session + 1,
            session_started=False
        )






