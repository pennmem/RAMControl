import os.path as osp
import pytest


if __name__ == "__main__":
    # TODO: use pytest markers to selectively disable tests
    tests = [osp.join("tests", test) for test in [
        "test_util.py",
        "test_voiceserver.py",
        "test_debugger.py"
    ]]
    pytest.main(["-vs", "--lf"] + tests)
