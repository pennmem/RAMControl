# -*- coding: utf-8 -*-

import os.path as osp
from copy import deepcopy
from collections import Counter
import itertools
import six
import pytest
from ramcontrol.util import data_path
from ramcontrol import wordpool
from ramcontrol.wordpool import WordList, WordPool


@pytest.fixture
def wordpool_en():
    yield osp.join(data_path(), "wordpool_en.txt")


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
    def test_create(self, wordpool_en):
        pool = WordPool(wordpool_en, 25)
        with open(wordpool_en) as f:
            words = f.read().split()

        # Check types
        for l in pool.lists:
            assert isinstance(l, WordList)

        # Check shape
        assert len(pool.lists) is 25
        assert all([len(l) == 12 for l in pool.lists])

        # Check all words are present
        for word in words:
            assert any([word in lst for lst in pool.lists])

        # Check uniqueness
        counter = Counter(list(itertools.chain(*pool.lists)))
        assert len(list(counter.elements())) == len(words)

        # Check num_lists arg fails if wrong
        with pytest.raises(AssertionError):
            WordPool(wordpool_en, 26)
            WordPool(wordpool_en, 50)

        # Check shuffling performed
        pool2 = WordPool(wordpool_en, 25)
        for n in range(len(pool.lists)):
            assert pool.lists[n] != pool2.lists[n]

    def test_str(self, wordpool_en):
        pool = WordPool(wordpool_en)
        assert str(pool) == str(pool.lists)

    def test_getitem(self, wordpool_en):
        pool = WordPool(wordpool_en)
        for n in range(len(pool.lists)):
            assert pool[n] == pool.lists[n]

    def test_len(self, wordpool_en):
        pool = WordPool(wordpool_en)
        assert len(pool) == len(pool.lists)

    def test_save(self):
        pass
