# TODO: reorganize repo to not have to manipulate paths!
import os.path as osp
import sys
sys.path.append(osp.abspath(osp.join(".", "source", "pylib")))

import pytest


if __name__ == "__main__":
    # TODO: use pytest markers to selectively disable tests
    tests = [osp.join("tests", test) for test in [
        "test_util.py",
        "test_voiceserver.py"
    ]]
    pytest.main(["-vs"] + tests)
