import random
import pytest
import pandas as pd
from wordpool import WordList, WordPool
from wordpool.data import read_list
from ramcontrol import listgen


def test_generate_session_pool():
    # Test basic things like types and lengths being correct
    for language in "EN", "SP":
        session = listgen.generate_session_pool(language=language)
        assert type(session) is WordPool
        assert len(session) is 26
        for list_ in session:
            assert type(list_) is WordList
            assert len(list_) is 12

    with pytest.raises(AssertionError):
        listgen.generate_session_pool(13)
        listgen.generate_session_pool(num_lists=random.randrange(26))
        listgen.generate_session_pool(language="DA")

    # Test uniqueness
    session1 = listgen.generate_session_pool()
    session2 = listgen.generate_session_pool()
    for n in range(len(session1)):
        if n is 0:
            assert session1[n] == session2[n]  # practice lists always the same
        else:
            assert session1[n] != session2[n]


def test_assign_list_types():
    session = listgen.generate_session_pool()
    session = listgen.assign_list_types(session, 3, 7, 11, 4)
    n_ps, n_ns, n_s = 0, 0, 0
    for n, list_ in enumerate(session):
        if n == 0:
            assert session[n].metadata["type"] == "PRACTICE"
            continue
        kind = session[n].metadata["type"]
        if kind == "PS":
            n_ps += 1
        elif kind == "NON-STIM" or kind == "BASELINE":
            n_ns += 1
        elif kind == "STIM":
            n_s += 1

    for n in range(1, 4):
        assert session[n].metadata["type"] == "BASELINE"

    assert n_ps is 4
    assert n_ns is 10
    assert n_s is 11


def test_generate_rec1_blocks():
    pool = listgen.generate_session_pool()
    assigned = listgen.assign_list_types(pool, 3, 6, 16, 0)
    lures = WordList(read_list("REC1_lures_en.txt"))
    blocks = listgen.generate_rec1_blocks(assigned, lures)

    assert isinstance(blocks, pd.DataFrame)
    assert not all([s == u for s, u in zip(sorted(blocks.listno), blocks.listno)])

    blocks2 = listgen.generate_rec1_blocks(assigned, lures)
    for n in range(len(blocks.word)):
        if blocks.word.iloc[0] != blocks2.word.iloc[0]:
            break
    assert n < len(blocks.word)
