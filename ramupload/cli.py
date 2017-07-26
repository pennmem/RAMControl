"""Command-line interface for uploading data."""

from argparse import ArgumentParser
import prompt_toolkit as ptk


def make_imaging_parser(subparsers):
    parser = subparsers.add_parser('imaging', help='Upload imaging data')
    return parser


def make_host_parser(subparsers):
    parser = subparsers.add_parser('host', help="Transfer data from host PC")
    return parser


def make_clinical_parser(subparsers):
    parser = subparsers.add_parser('clinical', help="Upload clinical EEG data")
    return parser


def make_upload_parser(subparsers):
    parser = subparsers.add_parser('upload', help="Upload experiment data")
    return parser


def parse_args():
    """Define and parse command-line arguments."""
    parser = ArgumentParser(description="Upload RAM data")

    parser.add_argument('--subject', '-s', type=str, help="Subject ID")
    parser.add_argument('--experiment', '-x', type=str, help="Experiment type")
    parser.add_argument('--session', '-n', type=int, help="Session number")

    subparsers = parser.add_subparsers(dest='subcommand')
    make_host_parser(subparsers)
    make_imaging_parser(subparsers)

    return parser.parse_args()


def main():
    args = parse_args()
