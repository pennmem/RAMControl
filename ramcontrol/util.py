"""Common utilities."""

import os.path as osp
import subprocess
import unicodedata

# Default RAM environment variable (to be JSONified)
DEFAULT_ENV = {
    "no_host": False,
    "voiceserver": False,
    "ps4": False
}


def git_root():
    """Return the path to the root git directory."""
    path = subprocess.check_output("git rev-parse --show-toplevel".split())
    return path.strip()


def data_path():
    """Return the path containing test data."""
    return osp.join(git_root(), "tests", "data")


def absjoin(*paths):
    """Join a list of paths and return the absolute path."""
    return osp.abspath(osp.join(*paths))


def remove_accents(input_str):
    """Removes accented characters from an input string.

    :param str input_str:
    :rtype: str

    """
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])
