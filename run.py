"""Script to start RAM experiments."""

from __future__ import print_function

import os
import time
from multiprocessing import Process
import json
from configparser import ConfigParser
import atexit
import re

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.contrib.completers import WordCompleter

import psutil
import logserver
from logserver.handlers import SQLiteHandler

import pyepl.exputils
from ramcontrol.control import RAMControl
from ramcontrol.experiment import FRExperiment


def absjoin(*paths):
    """Join some paths and make it an absolute path."""
    return os.path.abspath(os.path.join(*paths))


def get_subject(subject=""):
    """Prompt for the subject ID.

    :param str subject: Default option.

    """
    history = InMemoryHistory()
    validate = lambda s: len(re.findall(r"R\d{4}[A-Z]", s)) == 1
    while True:
        response = prompt(u"Subject [{}]: ".format(subject), history=history)
        if len(response) == 0 and validate(subject):
            return subject
        elif validate(response):
            return response
        else:
            subject = response
            print("Invalid subject ID")


def get_experiment(available, experiment=""):
    """Prompt for the experiment to run.

    :param list available: Available experiments.
    :param str experiment: Default choice.

    """
    completer = WordCompleter(available)
    while True:
        response = prompt(u"Experiment (press tab to see available) [{}]: ".format(experiment),
                          completer=completer, complete_while_typing=True)
        if len(response) == 0 and experiment in available:
            return experiment
        elif response in available:
            return response
        else:
            experiment = ""
            print("Invalid experiment")


def main():
    config = ConfigParser()
    config.read("ramcontrol.ini")

    experiments = config["general"]["experiments"].split()
    debug = config["general"]["debug"]
    if debug:
        print("!"*80)
        print("DEBUG MODE ENABLED!")
        print("Change this in ramulator.ini NOW if this is a real experiment!")
        print("!"*80)

    pid = os.getpid()
    main_proc = psutil.Process(pid)
    here = os.path.realpath(os.path.dirname(__file__))
    last_settings_file = os.path.expanduser(config["startup"]["last_settings"])

    # Read last inputs
    try:
        with open(last_settings_file, "r") as f:
            last_settings = json.load(f)
    except IOError:
        last_settings = {
            "subject": "",
            "experiment": ""
        }

    # Get runtime options
    settings = {
        "subject": get_subject(last_settings["subject"]),
        "experiment": get_experiment(experiments, last_settings["experiment"])
    }
    fullscreen = False if debug else True

    # Store last settings for convenience next time
    with open(last_settings_file, "w") as f:
        json.dump(settings, f)

    # Setup arguments to pass to PyEPL
    pyepl_kwargs = {
        "use_eeg": False,
        "archive": absjoin(here, "data", settings["experiment"]),
        "subject": settings["subject"],
        "fullscreen": fullscreen,
        "resolution": "1440x900",

        # FIXME for more experiments
        "config": absjoin(here, "ramcontrol", "configs", "FR", "config.py"),
        "sconfig": absjoin(here, "ramcontrol", "configs", "FR", settings["experiment"] + "_config.py"),
    }

    # This is only here because PyEPL screws up the voice server if we don't
    # instantiate this *before* the PyEPL experiment.
    RAMControl.instance()

    # Setup PyEPL
    epl_exp = pyepl.exputils.Experiment(**pyepl_kwargs)
    epl_exp.setBreak()  # quit with Esc-F1

    # Setup the main experiment
    kwargs = {
        "video_path": os.path.expanduser(config["videos"]["path"])
    }
    if debug:
        kwargs.update(dict(config["debug"].items()))
    exp = FRExperiment(epl_exp, debug=debug, **kwargs)

    # Some funny business seems to be happening with PyEPL...
    @atexit.register
    def cleanup():
        time.sleep(0.25)
        for p in main_proc.children():
            p.kill()

    # Configure and start the logging server
    log_path = os.path.join(exp.session_data_dir, "session.sqlite")
    log_args = ([SQLiteHandler(log_path)],)
    log_process = Process(target=logserver.run_server, args=log_args,
                          name="log_process")
    log_process.start()

    # Finally, we are ready!
    exp.start()


if __name__ == "__main__":
    main()
