# -*- coding: utf-8 -*-

import os.path as osp
from copy import deepcopy
import six
import pytest
from ramcontrol.util import data_path
from ramcontrol import wordpool
from ramcontrol.wordpool import WordList


def test_shuffle_inner_lists():
    lists = [list(range(10)) for _ in range(10)]
    other = deepcopy(lists)
    wordpool.shuffle_inner_lists(other)
    assert lists != other


@pytest.mark.skip(reason="Not sure what this means yet")
def test_shuffle_together():
    pass


def test_read_list():
    filename = osp.join(data_path(), "lures_EN.txt")
    lures = wordpool.read_list(filename)
    assert isinstance(lures, list)
    assert len(lures) is 65
    for lure in lures:
        assert isinstance(lure, six.text_type)


@pytest.mark.skip(reason="Not sure how to test this right now")
def test_remove_accents():
    string = u"ÆØÅæøå"
    removed = wordpool.remove_accents(string)
    assert len(removed) == len(string)


class TestWordList:
    def test_from_file(self):
        words = WordList(osp.join(data_path(), "lures_EN.txt"))
        assert len(words) is 65
        for word in words:
            assert isinstance(word, six.text_type)

    def test_shuffle(self):
        num = 10
        words = WordList(range(num))
        res = words.shuffle()
        assert res is words
        assert len(res) is num
        for n in range(num):
            assert n in res


class TestWordPool:
    def test_save(self):
        assert pytest.raises(NotImplementedError)
