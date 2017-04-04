"""List generation and I/O."""

import random
import os.path as osp
import functools
import numpy as np
import numpy.random as npr
import pandas as pd
import wordpool
from . import exc

RAM_LIST_EN = wordpool.load("ram_wordpool_en.txt")
RAM_LIST_SP = wordpool.load("ram_wordpool_sp.txt")

PRACTICE_LIST_EN = wordpool.load("practice_en.txt")
PRACTICE_LIST_SP = wordpool.load("practice_sp.txt")

LURES_LIST_EN = wordpool.load("REC1_lures_en.txt")


class catfr:
    """Namespace to contain catFR list generation functions."""
    @staticmethod
    def assign_word_numbers(pool):
        """Assign a serial number to each word in a category."""
        pool["wordno"] = -1

        word_count = pool.groupby("category").count().word
        n_words = word_count[0]
        assert all([n_words == word_count[n] for n in range(1, len(word_count))])

        # Assign word numbers
        for cat in pool.category.unique():
            pool.loc[pool.category == cat, "wordno"] = range(n_words)

        return pool

    @staticmethod
    def assign_list_numbers(pool, n_lists=26, list_start=1):
        """Assign list numbers to words in the pool."""
        assert "wordno" in pool.columns
        pool["listno"] = -1

        def condition(half, category):
            if half == 0:
                half_cond = pool.wordno % 2 == 0
            else:
                half_cond = pool.wordno % 2 == 1
            return (
                (pool.category == category) &
                (half_cond) &
                (pool.listno == -1)
            )

        original = pool.copy()
        while True:
            pool = original.copy()
            try:
                for listno in range(list_start, n_lists):
                    choices = pool.category[(pool.listno == -1)].unique()
                    cats = np.random.choice(choices, 3, replace=False)
                    ixf, ixs = [], []

                    for cat in cats:
                        cond = functools.partial(condition, category=cat)
                        ixf.append(pool.word[cond(0)].sample(2).index)
                        ixs.append(pool.word[cond(1)].sample(2).index)
                    ix = pd.Index(np.array(ixf + ixs).flatten())
                    pool.loc[ix, "listno"] = listno
                return pool
            except ValueError:
                pass

    @staticmethod
    def sort_pairs(pool):
        """Arrange categorical pairs of words."""
        assert "category" in pool.columns
        assert "listno" in pool.columns
        assert "wordno" in pool.columns

        def cond(category, listno, excluded):
            return (
                (pool.listno == listno) &
                (pool.category == category) &
                ~(pool.word.isin(excluded))
            )

        lists = []
        used = []
        for listno in sorted(pool.listno.unique()):
            order_1 = pool.category[pool.listno == listno].unique()
            order_2 = np.random.permutation(order_1)
            while order_2[0] == order_1[-1]:
                order_2 = np.random.permutation(order_1)
            order = np.append(order_1, order_2)

            list_ = None
            for cat in order:
                row = pool[cond(cat, listno, used)].sample(2)
                list_ = pd.concat([list_, row])
                used.extend(list_.iloc[-2:].word)
            lists.append(list_)

        return pd.concat(lists).reset_index(drop=True)

    @staticmethod
    def generate_session_pool(num_lists=25, listno_start=1,
                                          language="EN"):
        """Generate a single session pool for catFR experiments.

        :param str language: Language to load words in.
        :param int num_lists: Number of lists to assign.
        :param int listno_start: Where to start numbering from.
        :returns: Shuffled, categorized word pool.

        """
        # validate language
        if language.lower() not in ["en", "sp"]:
            raise exc.LanguageError(
                "Language must be 'EN' or 'SP'".format(language))

        # Load and shuffle order of words in categories
        filename = "ram_categorized_{:s}.txt".format(language.lower())
        pool = wordpool.shuffle_within_groups(
            wordpool.load(filename),
            "category")
        words = catfr.sort_pairs(
            catfr.assign_list_numbers(
                catfr.assign_word_numbers(pool)
            )
        )

        all_words = wordpool.load('practice_cat_{:s}.txt'.format(language.lower()))
        all_words['listno'] = 0
        all_words['wordno'] = range(12)
        all_words['category'] = "X"
        all_words['category_num'] = -999
        return all_words.append(words).reset_index(drop=True)


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
