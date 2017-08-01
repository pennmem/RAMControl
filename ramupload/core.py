from __future__ import print_function

import os
import os.path as osp
import shutil
from glob import glob
import logging
from collections import defaultdict
import subprocess
import shlex
from datetime import datetime

from . import upload_log

logger = logging.getLogger(__name__)


def _get_data_path(path=None):
    if path is None:
        output = subprocess.check_output(shlex.split('git worktree list')).decode()
        root = output.split()[0]
        found_path = osp.join(root, 'data')
    else:
        found_path = osp.abspath(path)
    assert osp.exists(found_path)
    logger.debug("Data path: %s", found_path)
    return found_path


def get_session_path(subject, experiment, session, path):
    return osp.join(path, experiment, subject, "session_{:d}".format(session))


def crawl_data_dir(path=None):
    """Crawl the data directory to find available data for uploading.

    :param str path: Path to look in.
    :returns: Dictionary of subjects. Keys are subjects, values are a list of
        experiments the subject has participated in.

    """
    path = _get_data_path(path)
    experiments = os.listdir(path)
    subjects = defaultdict(list)
    for exp in experiments:
        if exp.startswith('.'):
            continue
        for sdir in os.listdir(osp.join(path, exp)):
            if sdir.startswith('.'):
                continue
            subjects[sdir].append(exp)
            logger.info("Found experiment %s for subject %s", sdir, exp)
    return subjects


def get_sessions(subject, experiment, exclude_uploaded=True, path=None):
    """Get available sessions to upload.

    :param str subject:
    :param str experiment:
    :param bool exclude_uploaded: Exclude already uploaded data
        (not yet implemented).
    :param str path:

    """
    path = _get_data_path(path)
    sessions = []
    for session in range(20):
        subdir = get_session_path(subject, experiment, session, path)
        pattern = osp.join(subdir, "*.*log")
        if len(glob(pattern)):
            sessions.append(session)
    return sessions


def remove_transferred_eeg_data(path, lifetime):
    """Removes transferred EEG data that is older than the lifetime limit.

    :param str path: Path where transferred EEG data was moved to.
    :param int lifetime: Threshold number of days for determining if data can be
        expunged.

    """
    for path_ in os.listdir(path):
        age = osp.getmtime()
        dt = datetime.now() - datetime.fromtimestamp(age)
        if dt.days > lifetime:
            upload_log.info("Removing %s since it is %d days old", path_, dt.days)
            shutil.rmtree(path_)


def copytree(src, dest):
    """Same as shutil.copytree, but with progress updates."""
    def callback(path, contents):
        for file in contents:
            now = datetime.isoformat(datetime.now()).replace('T', ' ')
            print("[{}]".format(now), "Copying", osp.join(path, file))
        return []

    shutil.copytree(src, dest, ignore=callback)
