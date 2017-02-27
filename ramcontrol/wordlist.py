"""Utility functions for loading and manipulating word lists."""

import random
import codecs
import unicodedata


def shuffle_inner_lists(lists):
    """Shuffles items within each list in place

    :param list lists: 2D list of size nLists x wordsPerList

    """
    for l in lists:
        random.shuffle(l)


def shuffle_together(*lists):
    zipped_lists = zip(*lists)
    random.shuffle(zipped_lists)
    return zip(*zipped_lists)


def read_lures(filename):
    """Read lure words from the lure pool.

    :param str filename: Path to lure list.
    :return: List of lures.

    """
    with codecs.open(filename, encoding="utf-8") as lures_file:
        return lures_file.read().split()


def remove_accents(input_str):
    """Removes accented characters from an input string.

    :param str input_str:
    :rtype: str

    """
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
