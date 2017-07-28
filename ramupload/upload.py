from __future__ import unicode_literals, print_function

import os
import os.path as osp
import shutil
from functools import wraps
from subprocess import check_call
from configparser import ConfigParser, NoSectionError, NoOptionError
import logging
from contextlib import contextmanager
from tempfile import mkdtemp

from prompt_toolkit import prompt

from . import upload_log

logger = logging.getLogger(__name__)


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
            upload_log.error("Uncaught exception from %s", func.__name__,
                             exc_info=True)
            raise
        return successful
    return wrapper


@contextmanager
def tempdir():
    """Create a temporary directory and remove it when finished."""
    path = mkdtemp()
    yield path
    try:
        os.rmdir(path)
    except OSError:
        logger.warning("Unable to remove temporary directory %s", path)


class Uploader(object):
    """Class responsible for handling the uploading of data.

    :param str subject: Subject ID
    :param str dataroot: Path to root data directory.

    """
    def __init__(self, subject, dataroot=None):
        self.subject = subject

        if dataroot is None:
            self.dataroot = osp.abspath(osp.join(osp.dirname(__file__), '..', 'data'))
        else:
            self.dataroot = dataroot

        parser = ConfigParser()
        parser.read(osp.join(osp.dirname(__file__), 'config.ini'))

        # Host PC settings
        self.host_pc = dict(parser['host_pc'])

        # Uploaded data settings
        self.transferred = dict(parser['transferred'])

        # Get the host PC password. This should only need to be done once unless
        # the password is changed.
        user_file = osp.expanduser('~/.ramupload.ini')
        user_parser = ConfigParser()
        user_parser.read(user_file)
        try:
            self.host_pc['password'] = user_parser.get('host_pc', 'password')
        except (NoSectionError, NoOptionError):
            password = prompt('Host PC password: ', is_password=True)
            try:
                user_parser.add_section('host_pc')
            except:  # already exists
                pass
            user_parser.set('host_pc', 'password', password)
            with open(user_file, 'w') as f:
                user_parser.write(f)
            self.host_pc['password'] = password

    def get_session_dir(self, experiment, session):
        """Return the path to a given session's data.

        :param str experiment:
        :param int session:

        """
        return osp.join(self.dataroot, experiment, self.subject,
                        'session_{:d}'.format(session))

    @log
    def rsync(self, src, dest):
        """Uploads data using rsync.

        :param str src: Source path.
        :param str dest: Destination path (uses ssh if in the proper format).

        """
        assert osp.exists(src)

        # Add a trailing slash if necessary
        if not src.endswith(osp.sep):
            src += osp.sep

        command = [
            'rsync',
            '-z',  # compress
            '--archive',
            '-P',  # --partial and --progress
            '--human-readable',
            src, dest
        ]
        return check_call(command)

    # FIXME: add default to dest
    @log
    def upload_imaging(self, src, dest):
        """Upload imaging data.

        :param str src: Directory to upload data from.
        :param str dest: Location to upload data to.

        """
        if not osp.isdir(src):
            raise OSError("Path either doesn't exist or isn't a directory")
        return self.rsync(src, dest)

    # FIXME: add default to dest
    @log
    def upload_clinical_eeg(self, src, dest):
        """Upload clinical EEG data. This is the same as :meth:`upload_imaging`
        but with a different destination.

        :param str src:
        :param str dest:

        """
        return self.upload_imaging(src, dest)

    @contextmanager
    def _mount_host_pc(self, mount_point):
        """Mount the host PC for transferring data."""
        addr_string = "//{user:s}:{password:s}@{addr:s}/{datadir:s}".format(**self.host_pc)
        print("Mounting host PC. This may take several seconds...")
        check_call(["mount_smbfs", addr_string, mount_point])
        yield
        print("Unmounting host PC...")
        check_call(["umount", mount_point])

    @log
    def transfer_host_data(self, experiment, session):
        """Fetches the data from the host PC to be uploaded to ramtransfer.

        :param str experiment:
        :param int session:

        """
        with tempdir() as mount_point:
            with self._mount_host_pc(mount_point):
                # Note that host and task computers differ in session numbering.
                host_dir = osp.join(mount_point, self.subject, experiment,
                                    'session_{:d}'.format(session + 1))
                task_dir = self.get_session_dir(experiment, session)
                shutil.copy(host_dir, task_dir)

        return True

    @log
    def move_eeg_to_transferred(self, experiment, session):
        """Moves EEG data to the transferred directory to be deleted when it's
        old enough.

        :param str experiment:
        :param int session:

        """
        trans_dir = osp.expanduser(self.transferred['dir'])
        if not osp.exists(trans_dir):
            os.makedirs(trans_dir)

        src = self.get_session_dir(experiment, session)
        dest = osp.join(trans_dir, self.subject, experiment,
                        'session_{:d}'.format(session))
        shutil.move(osp.join(src, 'host_pc'), dest)

    @log
    def upload_experiment_data(self, experiment, session, dest):
        """Upload all data from an experiment.

        :param str experiment:
        :param int session:
        :param str dest: Destination to rsync to.

        Step 1: transfer EEG data from host PC
        Step 2: upload *
        Step 3: move EEG data to temp dir, to be cleaned out every N days

        """
        self.transfer_host_data(experiment, session)
        if self.rsync(self.get_session_dir(experiment, session), dest):
            self.move_eeg_to_transferred(experiment, session)
            return True
        else:
            return False
