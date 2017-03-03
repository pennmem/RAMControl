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
        assert session[0].metadata["type"] == "PRACTICE"

    with pytest.raises(AssertionError):
        listgen.generate_session_pool(13)
        listgen.generate_session_pool(num_lists=random.randrange(26))
        listgen.generate_session_pool(language="DA")
