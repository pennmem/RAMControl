"""Utility functions for loading and manipulating word lists.

TODO: rework into a WordList class

"""

import random
import codecs
import unicodedata
import shutil


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


def read_list(filename):
    """Read words from a word pool.

    :param str filename: Path to word pool.
    :return: List of words.

    """
    with codecs.open(filename, encoding="utf-8") as list_file:
        return list_file.read().split()


def remove_accents(input_str):
    """Removes accented characters from an input string.

    :param str input_str:
    :rtype: str

    """
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])


def copy_word_pool(src, dest):
    """Copy a word pool with and without accents from one place to another.

    :param str src: Source path.
    :param str dest: Destination path.

    from FR.py::

        sess_path = self.exp.session.fullPath()

        # With accents
        shutil.copy(self.config.wp, os.path.join(sess_path, '..'))

        # Without accents
        no_accents_wp = [wordlist.remove_accents(line.strip())
                         for line in codecs.open(self.config.wp, 'r', 'utf-8').readlines()]
        open(os.path.join(sess_path,'..', self.config.noAcc_wp), 'w').write('\n'.join(no_accents_wp))

    """
    raise NotImplementedError
