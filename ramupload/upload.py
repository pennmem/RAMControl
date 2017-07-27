import os.path as osp
from functools import wraps
from subprocess import check_call

from . import upload_log


def log(func):
    """Decorator for logging the results of uploading data."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            successful = func(*args, **kwargs)
            if successful:
                upload_log.info("%s successfully completed", func.__name__)
            else:
                upload_log.error("%s failed!", func.__name__)
        except Exception:
            upload_log.error("Uncaught exception from %s", func.__name__)
        return successful
    return wrapper


class Uploader(object):
    """Class responsible for handling the uploading of data.

    :param str subject: Subject ID

    """
    def __init__(self, subject):
        self.subject = subject

    @log
    def rsync(self, src, dest):
        """Uploads data using rsync.

        :param str src: Source path.
        :param str dest: Destination path (uses ssh if in the proper format).

        """
        assert osp.exists(src)
        command = [
            'rsync',
            '-z',  # compress
            '--archive',
            '-P',  # --partial and --progress
            '--human-readable',
            src, dest
        ]
        return check_call(command)

    @log
    def upload_imaging(self, path):
        """Upload imaging data.

        :param str path: Directory to upload data from.

        """
        if not osp.isdir(path):
            raise OSError("Path either doesn't exist or isn't a directory")
        return True

    @log
    def upload_clinical_eeg(self):
        """Upload clinical EEG data."""
        return True

    @log
    def transfer_host_data(self):
        """Fetches the data from the host PC to be uploaded to ramtransfer."""
        return True

    @log
    def upload_experiment_data(self):
        """Upload all data from an experiment.

        Step 1: transfer EEG data from host PC
        Step 2: upload *

        """
        return True
