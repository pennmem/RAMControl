"""Command-line interface for uploading data."""

from __future__ import unicode_literals, print_function

import os.path as osp
from argparse import ArgumentParser
from configparser import ConfigParser
from collections import OrderedDict
from functools import partial

from prompt_toolkit import prompt as ptkprompt
from prompt_toolkit.token import Token
from prompt_toolkit.contrib.completers import WordCompleter

from .core import crawl_data_dir, get_sessions
from .upload import Uploader

SUBCOMMANDS = ("host", "imaging", "clinical", "upload")


def make_parser():
    """Define command-line arguments."""
    parser = ArgumentParser(description="Upload RAM data", prog="ramup")
    parser.add_argument('--experiment', '-x', type=str, help="Experiment type")
    parser.add_argument('--session', '-n', type=int, help="Session number")
    parser.add_argument('--dataroot', type=str, help="Root data directory")
    parser.add_argument('subcommand', type=str, choices=SUBCOMMANDS, nargs='?',
                        help="Action to run")
    return parser


def toolbar(cli):
    return [(Token.Toolbar, 'Press tab to see options')]

prompt = partial(ptkprompt, get_bottom_toolbar_tokens=toolbar)


def prompt_subcommand():
    """Prompt for the subcommand to run if not given on the command-line."""
    mapped = OrderedDict([
        ("clinical", "Upload clinical EEG data"),
        ("imaging", "Upload imaging data"),
        ("host", "Transfer EEG data from the host PC"),
        ("experiment", "Upload all experimental data")
    ])
    completer = WordCompleter([value for _, value in mapped.items()])
    cmd = ''
    while cmd not in SUBCOMMANDS:
        res = prompt("Action: ", completer=completer)
        for key in mapped:
            if res == mapped[key]:
                cmd = key
    return cmd


def prompt_subject(subjects):
    """Prompt for the subject to upload data for."""
    completer = WordCompleter(subjects)
    subject = ''
    while subject not in subjects:
        subject = prompt("Subject: ", completer=completer)
    return subject


def prompt_experiment(experiments):
    """Prompt for the experiment type to upload."""
    completer = WordCompleter(experiments)
    exp = ''
    while exp not in experiments:
        exp = prompt("Experiment: ", completer=completer)
    return exp


def prompt_session(sessions):
    """Prompt for the session number to upload."""
    completer = WordCompleter(['{}'.format(session) for session in sessions])
    session = -1
    while session not in sessions:
        try:
            session = int(prompt("Session: ", completer=completer))
        except TypeError:
            continue
    return session


def main():
    # Read config file for default settings
    config = ConfigParser()
    config.read(osp.join(osp.dirname(__file__), 'config.ini'))
    host_pc = dict(config['host_pc'])  # Host PC settings
    transferred = dict(config['transferred'])  # Uploaded data settings

    parser = make_parser()
    parser.add_argument('--subject', '-s', type=str, help="Subject ID")
    args = parser.parse_args()

    available = crawl_data_dir(path=args.dataroot)
    subcommand = args.subcommand or prompt_subcommand()
    subject = args.subject or prompt_subject(list(available.keys()))
    uploader = Uploader(subject, host_pc, transferred, dataroot=args.dataroot)

    if subcommand in ['host', 'upload']:
        experiment = args.experiment or prompt_experiment(available[subject])
        session = args.session or prompt_session(get_sessions(subject, experiment, path=args.dataroot))

        dest = None  # FIXME

        if args.subcommand == 'upload':
            uploader.upload_experiment_data(experiment, session, dest)
        elif args.subcommand == 'host':
            # This shouldn't need to be called separately since the upload task
            # calls it automatically, but it may be useful to do this ahead of
            # time.
            uploader.transfer_host_data(experiment, session)
    else:
        if args.subcommand == 'imaging':
            src = None  # FIXME
            dest = None  # FIXME
            uploader.upload_imaging(src, dest)
        elif args.subcommand == 'clinical':
            src = None  # FIXME
            dest = None  # FIXME
            uploader.upload_clinical_eeg(src, dest)
