# -*- coding: utf-8 -*-

import os.path as osp
from copy import deepcopy
import six
import pytest
from ramcontrol.util import data_path
from ramcontrol import wordlist


def test_shuffle_inner_lists():
    lists = [list(range(10)) for _ in range(10)]
    other = deepcopy(lists)
    wordlist.shuffle_inner_lists(other)
    assert lists != other


@pytest.mark.skip(reason="Not sure what this means yet")
def test_shuffle_together():
    pass


def test_read_list():
    filename = osp.join(data_path(), "lures_EN.txt")
    lures = wordlist.read_list(filename)
    assert isinstance(lures, list)
    assert len(lures) is 65
    for lure in lures:
        assert isinstance(lure, six.text_type)


@pytest.mark.skip(reason="Not sure how to test this right now")
def test_remove_accents():
    string = u"ÆØÅæøå"
    removed = wordlist.remove_accents(string)
    assert len(removed) == len(string)
