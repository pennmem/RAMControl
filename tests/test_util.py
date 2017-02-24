import os.path as osp
import util

here = osp.realpath(osp.dirname(__file__))


def test_git_root():
    assert util.git_root() == osp.realpath(osp.join(here, ".."))


def test_data_path():
    assert util.data_path() == osp.realpath(osp.join(here, "data"))
