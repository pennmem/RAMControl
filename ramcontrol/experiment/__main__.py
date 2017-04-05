"""Entry point for running experiments. This must be run with subprocess.Popen
because PyEPL is total garbage and hijacks things like command line parsing.

"""

import os
import os.path as osp
import time
import pickle
import json
import atexit
import psutil
from multiprocessing import Process

import logserver
from logserver.handlers import SQLiteHandler

from ..control import RAMControl
from ..util import absjoin
from .freerecall import FRExperiment, CatFRExperiment

from pyepl import exputils

# Maps experiment "families" to the class that should be used
class_map = {
    "FR": FRExperiment,
    "catFR": CatFRExperiment,
}

config = pickle.loads(os.environ["RAM_CONFIG"])

subject = config["subject"]
experiment = config["experiment"]
family = config["experiment_family"]
debug = config["debug"]
fullscreen = config["fullscreen"]

here = config["ramcontrol_path"]
archive_dir = absjoin(config["data_path"], experiment)
config_file = absjoin(here, "configs", family, "config.py")
sconfig_file = absjoin(here, "configs", family, experiment + "_config.py")

# This is only here because PyEPL screws up the voice server if we don't
# instantiate this *before* the PyEPL experiment.
RAMControl.instance(voiceserver=config["voiceserver"])

pid = os.getpid()
proc = psutil.Process(pid)

epl_exp = exputils.Experiment(subject=subject,
                              fullscreen=fullscreen, resolution="1440x900",
                              use_eeg=False,
                              archive=archive_dir,
                              config=config_file,
                              sconfig=sconfig_file)

kwargs = {
    "video_path": config["video_path"]
}
if debug:
    kwargs.update(config["debug_options"])

# epl_exp.setup()
epl_exp.setBreak()  # quit with Esc-F1

if debug:
    print(json.dumps(epl_exp.getConfig().config1.config, indent=2, sort_keys=True))
    print(json.dumps(epl_exp.getConfig().config2.config, indent=2, sort_keys=True))

ExperimentClass = class_map[family]
exp = ExperimentClass(epl_exp, family=family, debug=debug, **kwargs)

log_path = osp.join(exp.session_data_dir, "session.sqlite")
log_args = ([SQLiteHandler(log_path)],)
log_process = Process(target=logserver.run_server, args=log_args,
                      name="log_process")


# Some funny business seems to be happening with PyEPL... Shocking, I know.
@atexit.register
def cleanup():
    time.sleep(0.25)
    for p in proc.children():
        p.kill()

log_process.start()
exp.start()
