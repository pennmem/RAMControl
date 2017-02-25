"""Common utilities."""

import os.path as osp
import subprocess


def git_root():
    """Return the path to the root git directory."""
    path = subprocess.check_output("git rev-parse --show-toplevel".split())
    return path.strip()


def data_path():
    """Return the path containing test data."""
    return osp.join(git_root(), "tests", "data")
