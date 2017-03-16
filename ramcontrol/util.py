"""Common utilities."""

import os.path as osp
import subprocess
import unicodedata
import random
from string import ascii_uppercase


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


def fake_subject():
    """Return a fake subject ID."""
    return "R{:04d}{:s}".format(random.randint(0, 999),
                                random.choice(ascii_uppercase))


def remove_accents(input_str):
    """Removes accented characters from an input string.

    :param str input_str:
    :rtype: str

    """
    nkfd_form = unicodedata.normalize('NFKD', input_str)
    return u"".join([c for c in nkfd_form if not unicodedata.combining(c)])


def make_env(no_host=False, voiceserver=False, ps4=False):
    """Return a dict to update/populate the ``RAM_CONFIG`` env var.

    :param bool no_host: Don't connect to the host.
    :param bool voiceserver: Don't boot the voiceserver.
    :param bool ps4: Run a combined PS4-xyz task.

    """
    return locals()
