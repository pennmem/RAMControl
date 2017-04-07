"""FR list generation."""

import pandas as pd
import wordpool

RAM_LIST_EN = wordpool.load("ram_wordpool_en.txt")
RAM_LIST_SP = wordpool.load("ram_wordpool_sp.txt")

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")


def generate_session_pool(words_per_list=12, num_lists=25,
                          language="EN"):
    """Generate the pool of words for a single task session. This does *not*
    assign stim, no-stim, or PS metadata since this part depends on the
    experiment.

    :param int words_per_list: Number of words in each list.
    :param int num_lists: Total number of lists excluding the practice list.
    :param str language: Session language (``EN`` or ``SP``).
    :returns: Word pool
    :rtype: pd.DataFrame

    """
    assert language in ("EN", "SP")

    practice = PRACTICE_LIST_EN if language == "EN" else PRACTICE_LIST_SP
    practice["type"] = "PRACTICE"
    practice["listno"] = 0

    words = RAM_LIST_EN if language == "EN" else RAM_LIST_SP
    assert len(words) == words_per_list * num_lists
    words = wordpool.assign_list_numbers(wordpool.shuffle_words(words),
                                         num_lists, start=1)
    return pd.concat([practice, words]).reset_index(drop=True)
