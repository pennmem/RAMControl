"""Common utilities."""

import os.path as osp
import subprocess
import random
import unicodedata


def git_root():
    """Return the path to the root git directory."""
    path = subprocess.check_output("git rev-parse --show-toplevel".split())
    return path.strip()


def data_path():
    """Return the path containing test data."""
    return osp.join(git_root(), "tests", "data")


def shuffle_together(*lists):
    zipped_lists = zip(*lists)
    random.shuffle(zipped_lists)
    return zip(*zipped_lists)


def shuffle_inner_lists(lists):
    """Shuffles items within each list in place

    :param list lists: 2D list of size nLists x wordsPerList

    """
    for l in lists:
        random.shuffle(l)


def seed_rng(seed):
    """
    Seeds the random number generator with the input argument
    :param seed: the element to seed Random with
    """
    random.seed(seed)


def remove_accents(input_str):
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
