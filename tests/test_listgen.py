import random
import pytest
from wordpool import WordList, WordPool
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


def test_assign_list_types():
    session = listgen.generate_session_pool()
    session = listgen.assign_list_types(session, 3, 7, 11, 4)
    n_ps, n_ns, n_s = 0, 0, 0
    for n, list_ in enumerate(session):
        if n == 0:
            assert session[n].metadata["type"] == "PRACTICE"
            continue
        kind = session[n].metadata["type"]
        if kind == "PS ENCODING":
            n_ps += 1
        elif kind == "NON-STIM ENCODING":
            n_ns += 1
        elif kind == "STIM ENCODING":
            n_s += 1

    for n in range(1, 4):
        assert session[n].metadata["type"] == "NON-STIM ENCODING"

    assert n_ps is 4
    assert n_ns is 10
    assert n_s is 11
