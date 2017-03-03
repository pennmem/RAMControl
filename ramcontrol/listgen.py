"""List generation and I/O."""

import random
from wordpool import WordList, WordPool
from wordpool.data import read_list

RAM_LIST_EN = WordList(read_list("ram_wordpool_en.txt"))
RAM_LIST_SP = WordList(read_list("ram_wordpool_sp.txt"))
PRACTICE_LIST_EN = WordList(read_list("practice_en.txt"),
                            metadata={"type": "PRACTICE"})
PRACTICE_LIST_SP = WordList(read_list("practice_sp.txt"),
                            metadata={"type": "PRACTICE"})


def generate_session_pool(words_per_list=12, num_lists=25,
                          language="EN"):
    """Generate the pool of words for a single task session. This does *not*
    assign stim, no-stim, or PS metadata since this part depends on the
    experiment.

    :param int words_per_list: Number of words in each list.
    :param int num_lists: Total number of lists excluding the practice list.
    :param str language: Session language (``EN`` or ``SP``).
    :returns: Word pool
    :rtype: WordPool

    """
    assert language in ("EN", "SP")
    all_words = RAM_LIST_EN if language == "EN" else RAM_LIST_SP
    practice = PRACTICE_LIST_EN if language == "EN" else PRACTICE_LIST_SP
    assert len(all_words) == words_per_list * num_lists
    all_words.shuffle()
    lists = [all_words[n:words_per_list + n]
             for n in range(0, len(all_words), words_per_list)]
    lists.insert(0, practice)
    return WordPool(lists)


def assign_list_types(pool, num_baseline, num_nonstim, num_stim, num_ps=0):
    """Assign list types to a pool.

    For legacy reasons, stim/non-stim lists are given types ``STIM ENCODING``
    and ``NON-STIM ENCODING``, respectively, and PS trials are given type
    ``PS ENCODING`` for consistency.

    :param WordPool pool:
    :param int num_baseline: Number of baseline trials *excluding* the practice
        list.
    :param int num_nonstim: Number of non-stim trials.
    :param int num_stim: Number of stim trials.
    :param int num_ps: Number of parameter search trials.
    :returns: pool with assigned types
    :rtype: WordPool

    """
    assert len(pool) == num_baseline + num_nonstim + num_stim + num_ps + 1

    # Assign baseline
    for n in range(1, num_baseline + 1):
        pool[n].metadata["type"] = "NON-STIM ENCODING"

    # Assign PS
    for n in range(1 + num_baseline, 2 + num_baseline + num_ps):  # FIXME: WRONG
        pool[n].metadata["type"] = "PS ENCODING"

    # Assign stim/non-stim
    rest = ["NON-STIM ENCODING"]*num_nonstim + ["STIM ENCODING"]*num_stim
    random.shuffle(rest)
    for i, n in enumerate(range(2 + num_baseline + num_ps, len(pool))):
        pool[n].metadata["type"] = rest[i]

    return pool


if __name__ == "__main__":
    pool = generate_session_pool()
    pool = assign_list_types(pool, 3, 22, 0, 0)
    for list_ in pool:
        print(list_.metadata["type"])
