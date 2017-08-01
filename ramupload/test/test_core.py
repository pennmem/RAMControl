import os
import os.path as osp
from tempfile import mkdtemp
import shutil
import random
import pytest

from ramupload import core

EXPERIMENTS = ['FR{:d}'.format(n) for n in range(5)] + \
              ['catFR{:d}'.format(n) for n in range(5)]
SESSIONS = ['session_{:d}'.format(n) for n in range(10)]
SUBJECTS = ['R0{:03d}'.format(random.randint(0, 999)) for _ in range(10)]


@pytest.fixture
def datapath():
    path = mkdtemp()
    for experiment in EXPERIMENTS:
        os.mkdir(osp.join(path, experiment))
        for subject in SUBJECTS:
            os.mkdir(osp.join(path, experiment, subject))
            for session in SESSIONS:
                os.mkdir(osp.join(path, experiment, subject, session))
    yield path
    shutil.rmtree(path)


def test_crawl_data_dir(datapath):
    subjects = core.crawl_data_dir(datapath)
    for subject in subjects:
        assert subject in SUBJECTS
        for experiment in subjects[subject]:
            assert experiment in EXPERIMENTS


def test_get_sessions(datapath):
    subject = random.choice(SUBJECTS)
    experiment = random.choice(EXPERIMENTS)
    session = random.choice(range(10))
    path = osp.join(datapath, experiment, subject,
                    "session_{:d}".format(session), "session.log")
    with open(path, 'w') as logfile:
        logfile.write("I'm a log!")

    sessions = core.get_sessions(subject, experiment, path=datapath)
    assert len(sessions) == 1
    assert sessions[0] == session


def test_check_internet_connection():
    core.check_internet_connection()
    with pytest.raises(RuntimeError):
        core.check_internet_connection(0.00001)
