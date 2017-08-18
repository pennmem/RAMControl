"""Script to start RAM experiments."""

from __future__ import print_function

import os
import pickle
from configparser import ConfigParser
from argparse import ArgumentParser
import re
import subprocess

from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.contrib.completers import WordCompleter

import ramcontrol
from ramcontrol.util import absjoin


def get_subject(subject=""):
    """Prompt for the subject ID.

    :param str subject: Default option.

    """
    history = InMemoryHistory()
    validate = lambda s: len(re.findall(r"R\d{4}[A-Z]", s)) == 1
    while True:
        # response = prompt(u"Subject [{}]: ".format(subject), history=history)
        response = prompt(u"Subject: ")
        if len(response) == 0 and validate(subject):
            return subject.encode()
        elif validate(response):
            return response.encode()
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
        # response = prompt(u"Experiment (press tab to see available) [{}]: ".format(experiment),
        #                   completer=completer, complete_while_typing=True)
        response = prompt(u"Experiment (press tab to see available): ",
                          completer=completer, complete_while_typing=True)
        if len(response) == 0 and experiment in available:
            return experiment.encode()
        elif response in available:
            return response.encode()
        else:
            experiment = ""
            print("Invalid experiment")


def get_language(languages):
    """Prompt for the language to use in the experiment."""
    completer = WordCompleter(languages)
    while True:
        response = prompt(u"Language (press tab to see available: ",
                          completer=completer, complete_while_typing=True)
        if response in languages:
            return response.encode()
        else:
            print("Unavailable language")


def main():
    config = ConfigParser()
    config.read("ramcontrol.ini")

    parser = ArgumentParser()
    parser.add_argument("-s", "--subject", help="Subject ID", default=None)
    parser.add_argument("-x", "--experiment", default=None, help="Experiment to run")
    parser.add_argument("-l", "--language",
                        choices=["english", "spanish"],
                        help="Language to use in experiment")
    parser.add_argument("-d", "--debug", action="store_true", default=False,
                        help="Enable debug mode")
    parser.add_argument("--no-fs", action="store_true", default=False,
                        help="Disable fullscreen mode")
    args = parser.parse_args()

    experiments = config["general"]["experiments"].split()

    if args.debug:
        print("!"*80)
        print("{:^80}".format("DEBUG MODE ENABLED!"))
        print("{:^80}".format("Restart NOW if this is a real experiment!!!"))
        print("!"*80)

    if args.subject is None:
        args.subject = get_subject()
    if args.experiment is None:
        args.experiment = get_experiment(experiments)
    if args.language is None:
        args.language = get_language(config["general"]["languages"].split())

    env = {
        "subject": args.subject,
        "experiment": args.experiment,
        "experiment_family": config.get(args.experiment, "family"),
        "language": args.language,

        "voiceserver": config[args.experiment].getboolean("voiceserver", fallback=False),

        "video_path": os.path.abspath(os.path.expanduser(config["videos"]["path"])),
        "data_path": absjoin("./data"),
        "ramcontrol_path": os.path.dirname(ramcontrol.__file__),

        "fullscreen": not (args.debug or args.no_fs),
        "debug": args.debug,
        "debug_options": config["debug"].items()
    }

    penv = os.environ.copy()
    penv["RAM_CONFIG"] = pickle.dumps(env)

    p = subprocess.Popen(["python", "-m", "ramcontrol.experiment"],
                         cwd=absjoin("."), env=penv)
    p.wait()


if __name__ == "__main__":
    main()
