"""List generation and I/O."""

import random
import numpy as np
import numpy.random as npr
import pandas as pd
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
    """Assign list types to a pool. The types are:

    * ``PRACTICE``
    * ``BASELINE``
    * ``PS``
    * ``STIM``
    * ``NON-STIM``

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
    practice = [pool.lists.pop(0)]

    baseline = [pool.lists.pop(0) for _ in range(num_baseline)]
    for item in baseline:
        item.metadata["type"] = "BASELINE"

    ps = [pool.lists.pop(0) for _ in range(num_ps)]
    for item in ps:
        item.metadata["type"] = "PS"

    stim_or_nostim = ["NON-STIM"]*num_nonstim + ["STIM"]*num_stim
    random.shuffle(stim_or_nostim)
    for n, kind in enumerate(stim_or_nostim):
        pool.lists[n].metadata["type"] = kind

    pool.lists = practice + baseline + ps + pool.lists
    return pool


def generate_rec1_blocks(pool, lures):
    """Generate REC1 word blocks.

    :param WordPool pool: :class:`WordPool` used in verbal task session.
    :param WordList lures: List of lures to use.
    :returns: :class:`pd.DataFrame`.

    """
    df = pool.to_dataframe()

    # Remove practice and baseline lists
    allowed = df[~df.isin(["PRACTICE", "BASELINE"])]

    # Divide into stim lists (exclude if in last four)...
    stims = allowed[(allowed.type == "STIM") & (allowed.listno <= allowed.listno.max() - 4)]

    # ...and nonstim lists (take all)
    nonstims = allowed[allowed.type == "NON-STIM"]

    # Randomly select stim list numbers
    stim_idx = pd.Series(stims.listno.unique()).sample(6)
    rec_stims = stims[stims.listno.isin(stim_idx)]
    rec_nonstims = nonstims

    # Combine selected words
    targets = pd.concat([rec_stims, rec_nonstims])

    # Give lures list numbers
    lures = lures.to_dataframe()
    lures["type"] = "LURE"
    lures["listno"] = npr.choice(targets.listno.unique(), len(lures))

    # Combine lures and targets
    combined = pd.concat([targets, lures]).sort_values(by="listno")
    listnos = combined.listno.unique()

    # Break into two blocks and shuffle
    block_listnos = [listnos[:int(len(listnos)/2)], listnos[int(len(listnos)/2):]]
    blocks = [combined[combined.listno.isin(idx)].sample(frac=1) for idx in block_listnos]
    return pd.concat(blocks)


if __name__ == "__main__":
    pool = generate_session_pool()
    assigned = assign_list_types(pool, 3, 6, 16, 0)
    lures = WordList(read_list("REC1_lures_en.txt"))
    blocks = generate_rec1_blocks(assigned, lures)
    for block in blocks:
        print(block)
