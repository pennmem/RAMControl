from tempfile import mkdtemp
import os.path as osp
import shutil
from functools import partial
import pytest

from ramcontrol.util import git_root, absjoin
from ramcontrol.experiment import Experiment
from ramcontrol.exc import LanguageError
from pyepl.exputils import Experiment as EPLExperiment


@pytest.fixture(scope="module")
def experiment():
    """Yields a generic experiment to test generic functionality
    (implements dummy methods for abstract methods).

    """
    class TestExperiment(Experiment):
        def prepare_experiment(self):
            pass

        def run(self):
            pass

    data_dir = mkdtemp()
    config = absjoin(git_root(), "ramcontrol", "configs", "FR", "config.py")
    sconfig = absjoin(git_root(), "ramcontrol", "configs", "FR", "FR5_config.py")
    EPLExperiment.parseArgs = lambda x: x
    epl_exp = EPLExperiment(archive=data_dir, subject="R0001E",
                            config=config, sconfig=sconfig,
                            fullscreen=False, use_eeg=False)
    epl_exp.setup()
    epl_exp.setBreak()
    experiment = TestExperiment(epl_exp)
    yield experiment
    try:
        epl_exp.breakfunc(True, None, False)
    except SystemExit:  # breakfunc stupidly calls sys.exit
        pass
    finally:
        shutil.rmtree(data_dir, ignore_errors=True)


@pytest.fixture
def tempdir():
    datadir = mkdtemp()
    yield datadir
    shutil.rmtree(datadir, ignore_errors=True)


def test_copy_word_pool(tempdir):
    doit = partial(Experiment.copy_word_pool, data_root=tempdir)
    doit(include_lures=True)
    assert osp.exists(osp.join(tempdir, "RAM_wordpool.txt"))
    assert osp.exists(osp.join(tempdir, "RAM_lurepool.txt"))

    with pytest.raises(LanguageError):
        doit(language="danish")
        doit(language="spanish", include_lures=True)
