import sys
import os
import os.path as osp
from tempfile import gettempdir
from ramcontrol import util
import pytest

here = osp.realpath(osp.dirname(__file__))


@pytest.fixture
def logfile():
    path = osp.join(gettempdir(), "log.txt")
    yield path
    try:
        os.remove(path)
    except:
        pass


def test_git_root():
    assert util.git_root() == osp.realpath(osp.join(here, ".."))


def test_data_path():
    assert util.data_path() == osp.realpath(osp.join(here, "data"))


def test_absjoin():
    assert util.absjoin(".", "tests") == here


def test_tee(logfile):
    stdout = sys.stdout
    stderr = sys.stderr

    with util.tee(logfile):
        print("testing")
        assert sys.stdout != stdout
        assert sys.stderr != stderr

    assert sys.stdout == stdout
    assert sys.stderr == stderr

    with open(logfile, 'r') as f:
        assert "testing" in f.read()
