import os
import os.path as osp
import shutil
import random
from contextlib import contextmanager
import pytest
import pandas as pd

import wordpool
from ramcontrol import listgen, exc


@contextmanager
def subdir(parent, name="sub"):
    path = osp.join(str(parent), name)
    os.mkdir(path)
    yield path
    shutil.rmtree(path, ignore_errors=True)


def test_write_wordpool(tmpdir):
    fn = listgen.write_wordpool_txt

    # unsupported language
    with pytest.raises(exc.LanguageError):
        fn(tmpdir, "DA")

    # missing rec words for supported language
    with pytest.raises(exc.LanguageError):
        fn(tmpdir, "SP", True)

    # writing without lures
    with subdir(tmpdir) as path:
        ret = fn(path, "EN")
        assert len(os.listdir(path)) == 1
        assert len(ret) == 1
        assert ret[0] == osp.join(path, "RAM_wordpool.txt")

        with open(ret[0]) as f:
            words = pd.Series([l.strip() for l in f.readlines()])
            assert (words == wordpool.load("ram_wordpool_en.txt").word).all()

    # Writing with lures
    with subdir(tmpdir) as path:
        ret = fn(path, "EN", True)
        assert len(os.listdir(path)) == 2
        assert len(ret) == 2
        assert ret[0] == osp.join(path, "RAM_wordpool.txt")
        assert ret[1] == osp.join(path, "RAM_lurepool.txt")

        # targets
        with open(ret[0]) as f:
            words = pd.Series([l.strip() for l in f.readlines()])
            assert (words == wordpool.load("ram_wordpool_en.txt").word).all()

        # lures
        with open(ret[1]) as f:
            words = pd.Series([l.strip() for l in f.readlines()])
            assert (words == wordpool.load("REC1_lures_en.txt").word).all()


def test_generate_session_pool():
    # Test basic things like types and lengths being correct
    for language in "EN", "SP":
        session = listgen.generate_session_pool(language=language)
        assert type(session) is pd.DataFrame
        assert len(session.word) == 26*12

        for listno in session.listno.unique():
            df = session[session.listno == listno]
            assert type(df) is pd.DataFrame
            assert len(df) is 12

    with pytest.raises(AssertionError):
        listgen.generate_session_pool(13)
        listgen.generate_session_pool(num_lists=random.randrange(26))
        listgen.generate_session_pool(language="DA")

    # Test uniqueness
    session1 = listgen.generate_session_pool()
    session2 = listgen.generate_session_pool()
    for n in session1.listno.unique():
        first = session1[session1.listno == n]
        second = session2[session2.listno == n]
        if n == 0:
            # practice lists always the same
            assert (first.word == second.word).all()
        else:
            assert not (first.word == second.word).all()


def test_assign_list_types():
    session = listgen.generate_session_pool()
    session = listgen.assign_list_types(session, 3, 7, 11, 4)
    words_per_list = 12

    grouped = session.groupby("type")
    counts = grouped.count()
    assert len(counts.index) == 5
    assert counts.loc["PRACTICE"].listno / words_per_list == 1
    assert counts.loc["BASELINE"].listno / words_per_list == 3
    assert counts.loc["NON-STIM"].listno / words_per_list == 7
    assert counts.loc["STIM"].listno / words_per_list == 11
    assert counts.loc["PS"].listno / words_per_list == 4

    assert all(session[session["type"] == "PRACTICE"].listno == 0)

    for n in range(1, 4):
        assert n in session[session["type"] == "BASELINE"].listno.unique()

    for n in range(4, 8):
        assert n in session[session["type"] == "PS"].listno.unique()

    for n in range(8, 26):
        assert session[session.listno == n]["type"].isin(["STIM", "NON-STIM"]).all()


def test_generate_rec1_blocks():
    pool = listgen.generate_session_pool()
    assigned = listgen.assign_list_types(pool, 3, 6, 16, 0)
    lures = wordpool.load("REC1_lures_en.txt")
    blocks = listgen.generate_rec1_blocks(assigned, lures)

    assert isinstance(blocks, pd.DataFrame)
    assert not all([s == u for s, u in zip(sorted(blocks.listno), blocks.listno)])

    blocks2 = listgen.generate_rec1_blocks(assigned, lures)
    for n in range(len(blocks.word)):
        if blocks.word.iloc[0] != blocks2.word.iloc[0]:
            break
    assert n < len(blocks.word)


class TestCatFR:
    @property
    def catpool(self):
        return wordpool.load("ram_categorized_en.txt")

    def test_assign_word_numbers(self):
        # categories are balanced
        with pytest.raises(AssertionError):
            df = pd.DataFrame({
                "word": ["a", "b", "c"],
                "category": ["cat1", "cat1", "cat2"]
            })
            listgen.catfr.assign_word_numbers(df)

        pool = listgen.catfr.assign_word_numbers(self.catpool)
        assert len(pool.word.unique()) == 300
        assert "category" in pool.columns
        assert "word" in pool.columns
        assert "wordno" in pool.columns

        # check word numbers assigned correctly
        for cat in pool.category:
            for n, row in pool[pool.category == cat].reset_index().iterrows():
                assert n == row.wordno

    def test_assign_list_numbers(self):
        # must assign word numbers first
        with pytest.raises(AssertionError):
            listgen.catfr.assign_list_numbers(self.catpool)

        pool = listgen.catfr.assign_word_numbers(self.catpool)
        assigned = listgen.catfr.assign_list_numbers(pool)

        assert len(assigned) == 300
        assert len(assigned.word.unique()) == 300
        assert "listno" in assigned.columns
        assert len(assigned[assigned.listno < 0]) == 0
        counts = assigned.groupby("listno").listno.count()
        for count in counts:
            assert counts[count] == 12

    def test_sort_pairs(self):
        pool = self.catpool.copy()
        with pytest.raises(AssertionError):
            listgen.catfr.sort_pairs(pool)
            listgen.catfr.sort_pairs(listgen.catfr.assign_word_numbers(pool))

        pool = listgen.catfr.sort_pairs(listgen.catfr.assign_list_numbers(
            listgen.catfr.assign_word_numbers(pool)))

        # check uniqueness and that all words/categories are used
        assert len(pool.word.unique()) == 300
        assert len(pool.category.unique()) == 25

        # check that words come in pairs
        for n in pool.index[::2]:
            assert pool.category[n] == pool.category[n + 1]

        # check that last middle categories don't repeat
        for n in range(5, len(pool), 12):
            assert pool.category[n] != pool.category[n + 1]

    def test_generate_cat_session_pool(self):
        with pytest.raises(exc.LanguageError):
            listgen.catfr.generate_session_pool(language="DA")

        pool = listgen.catfr.generate_session_pool()
        assert len(pool) == 312
        assert "listno" in pool
        assert "category" in pool
        assert not any(pool.category.isnull())

        # no repeated words and all words used
        assert len(pool.word.unique()) == 312

        # all categories used
        assert len(pool.category.unique()) == 26
