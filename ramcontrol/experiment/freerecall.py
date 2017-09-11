from __future__ import print_function

import os
import os.path as osp

from wordpool import listgen
from ..messages import TrialMessage
from ..exc import ExperimentError
from ..util import get_instructions
from .wordtask import WordTask


class FRExperiment(WordTask):
    """Base for FR tasks."""
    def prepare_experiment(self):
        """Pre-generate all word lists and copy files to the proper locations.

        """
        # Copy word pool to the data directory
        include_rec = self.config.recognition_enabled
        self.logger.info("Copying word pool(s) to data directory")
        self.copy_word_pool(osp.join(self.data_root, self.subject), include_rec)

        # Generate all session lists and REC blocks
        self.logger.info("Pre-generating all word lists for %d sessions",
                         self.config.numSessions)
        all_lists = []
        all_rec_blocks = []
        all_learning_blocks = []

        for session in range(self.config.numSessions):
            self.logger.info("Pre-generating word lists for session %d",
                             session)
            if self.family == "FR":
                gen_pool = listgen.fr.generate_session_pool
            elif self.family == "catFR":
                gen_pool = listgen.catfr.generate_session_pool
            else:
                raise ExperimentError(
                    "Unexpected experiment family encountered: " + self.name)

            pool = gen_pool(language=self.language[:2].upper())
            n_baseline = self.config.n_baseline
            n_nonstim = self.config.n_nonstim
            n_stim = self.config.n_stim
            n_ps = self.config.n_ps
            assigned = listgen.assign_list_types(pool, n_baseline, n_nonstim,
                                                 n_stim, n_ps)

            # Reassign stim lists for multistim
            if self.config.experiment in ['FR6', 'catFR6']:
                stimspec = {
                    (0,): self.config.n_stim_A,
                    (1,): self.config.n_stim_B,
                    (0, 1): self.config.n_stim_AB
                }
                assert sum(stimspec.values()) == n_stim, \
                    "Total number of stim lists doesn't match multistim specs"
                assigned = listgen.assign_multistim(assigned, stimspec)

            if self.debug:
                print(assigned)

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
                entries.word.to_csv(osp.join(session_dir, name), index=False,
                                    header=False, encoding='latin1')

            all_lists.append(assigned)

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

            # Generate repeated list learning (LEARN1) blocks if this
            # experiment needs it
            if self.config.learning_subtask:
                self.logger.info("Pre-generating LEARN1 blocks for session %d",
                                 session)
                blocks = listgen.generate_learn1_blocks(assigned, 2, 2, stim_channels=(0, 1))

                if self.debug:
                    print(blocks)

                # Write .lst files to session folders for use in TotalRecall
                for listno in blocks.listno.unique():
                    name = "learn_{:d}.lst".format(listno)
                    entries = blocks[blocks.block_listno == listno]
                    entries.word.to_csv(osp.join(session_dir, name), index=False,
                                        header=False, encoding='latin1')

                # save to session folder
                blocks.to_csv(osp.join(session_dir, 'learn1_blocks.csv'))

                all_learning_blocks.append(blocks)

        # Store lists in the state
        self.all_lists = all_lists
        self.all_rec_blocks = all_rec_blocks
        self.all_learning_blocks = all_learning_blocks

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
        wordlist = self.all_lists[self.session]

        self.run_instructions(allow_skip=(self.session > 0))

        # Confirm that we should proceed
        if not self.run_confirm(
            "Running {:s} in session {:d} of {:s}\n({:s}).\n".format(
                self.subject, self.session, self.name,
                self.language) + "Press Y to continue, N to quit"):
            self.logger.info("Quitting due to negative confirmation.")
            return

        self.run_mic_test()

        for listno in range(self.list_index, len(wordlist.listno.unique())):
            words = wordlist[wordlist.listno == listno]

            phase_type = words.type.iloc[0]
            assert all(words.type == phase_type)  # check that phase type assignments are correct

            # TODO: make this more flexible: allow varying stim-allowed sites per list
            stim_channels = words.stim_channels.iloc[0]

            with self.state_context("TRIAL", listno=listno, phase_type=phase_type):
                self.log_event("TRIAL", listno=listno, phase_type=phase_type)  # FIXME: host should get this with state message
                self.controller.send(TrialMessage(listno))

                # Countdown to encoding
                num = "practice trial" if listno is 0 else "trial {:d}".format(
                    listno)
                self.run_wait_for_keypress("Press any key for {:s}".format(num))
                self.run_countdown()
                self.run_orient(phase_type, self.config.orientText)

                # Encoding
                self.run_encoding(words, phase_type, stim_channels=stim_channels)

                # Distract
                self.run_distraction(phase_type, stim_channels=stim_channels)

                # Delay before retrieval
                self.clock.delay(self.timings.recall_delay,
                                 jitter=self.timings.recall_jitter)
                self.clock.wait()

                # Retrieval
                # self.run_orient(phase_type, self.config.recallStartText, beep=True)
                self.run_retrieval(phase_type, stim_channels=stim_channels)

                if phase_type == "PRACTICE":
                    with self.state_context("PRACTICE_POST_INSTRUCT"):
                        text = get_instructions("fr_post_practice_{:s}.txt".format(
                            self.language[:2].lower()))
                        self.epl_helpers.show_text_and_wait(text, 0.05)

            # Update list index stored in state
            self.list_index += 1

        if self.config.recognition_enabled:
            self.run_recognition()

        if self.config.learning_subtask:
            self.run_learning(self.all_learning_blocks[self.session])

        self.run_wait_for_keypress("Thank you!\nYou have completed the session.")

        # Update session number stored in state and reset list index
        self.update_state(
            session_number=self.session + 1,
            session_started=False
        )
