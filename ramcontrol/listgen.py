"""List generation and I/O."""

import random
import os.path as osp
import numpy.random as npr
import pandas as pd
import wordpool
from . import exc

RAM_LIST_EN = wordpool.load("ram_wordpool_en.txt")
RAM_LIST_SP = wordpool.load("ram_wordpool_sp.txt")

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")

LURES_LIST_EN = wordpool.load("REC1_lures_en.txt")


def write_wordpool_txt(path, language="EN", include_lure_words=False):
    """Write `RAM_wordpool.txt` to a file. This is used in event
    post-processing.

    :param str path: Directory to write file to.
    :param str language: Language to use ("EN" or "SP").
    :param bool include_lure_words: Also write lure words to ``path``.
    :returns: list of filenames written

    """
    if language not in ["EN", "SP"]:
        raise exc.LanguageError("Invalid language specified")
    if language == "SP" and include_lure_words:
        raise exc.LanguageError("Spanish lure words don't exist yet")

    kwargs = {
        "index": False,
        "header": False,
        "encoding": "utf8"
    }

    words = RAM_LIST_EN if language == "EN" else RAM_LIST_SP
    filename = osp.join(path, "RAM_wordpool.txt")
    ret = [filename]
    words.word.to_csv(filename, **kwargs)

    if include_lure_words:
        lures = LURES_LIST_EN
        filename = osp.join(path, "RAM_lurepool.txt")
        lures.to_csv(filename, **kwargs)
        ret.append(filename)

    return ret


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


def assign_list_types(pool, num_baseline, num_nonstim, num_stim, num_ps=0):
    """Assign list types to a pool. The types are:

    * ``PRACTICE``
    * ``BASELINE``
    * ``PS``
    * ``STIM``
    * ``NON-STIM``

    :param pd.DataFrame pool: Input word pool
    :param int num_baseline: Number of baseline trials *excluding* the practice
        list.
    :param int num_nonstim: Number of non-stim trials.
    :param int num_stim: Number of stim trials.
    :param int num_ps: Number of parameter search trials.
    :returns: pool with assigned types
    :rtype: WordPool

    """
    # List numbers should already be assigned and sorted
    listnos = pool.listno.unique()
    assert all([n == m for n, m in zip(listnos, sorted(listnos))])

    # Check that the inputs match the number of lists
    assert len(listnos) == num_baseline + num_nonstim + num_stim + num_ps + 1

    start = listnos[1]
    end = start + num_baseline
    baselines = pool.listno.isin(range(start, end))
    pool.loc[baselines, "type"] = "BASELINE"

    start = end
    end = start + num_ps
    if start != end:
        pses = pool.listno.isin(range(start, end))
        pool.loc[pses, "type"] = "PS"
        start = end

    stim_or_nostim = ["NON-STIM"] * num_nonstim + ["STIM"] * num_stim
    random.shuffle(stim_or_nostim)
    for n, type_ in enumerate(stim_or_nostim):
        pool.loc[pool.listno == start + n, "type"] = type_

    return pool


def generate_rec1_blocks(pool, lures):
    """Generate REC1 word blocks.

    :param pd.DataFrame pool: Word pool used in verbal task session.
    :param pd.DataFrame lures: Lures to use.
    :returns: :class:`pd.DataFrame`.

    """
    # Remove practice and baseline lists
    allowed = pool[~pool.isin(["PRACTICE", "BASELINE"])]

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
    lures["type"] = "LURE"
    lures["listno"] = npr.choice(targets.listno.unique(), len(lures))

    # Combine lures and targets
    combined = pd.concat([targets, lures]).sort_values(by="listno")
    listnos = combined.listno.unique()

    # Break into two blocks and shuffle
    block_listnos = [listnos[:int(len(listnos)/2)], listnos[int(len(listnos)/2):]]
    blocks = [combined[combined.listno.isin(idx)].sample(frac=1) for idx in block_listnos]
    return pd.concat(blocks)
