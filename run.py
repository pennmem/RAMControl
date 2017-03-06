"""Script to start RAM experiments."""

from __future__ import print_function
import json
import subprocess
import os
import argparse
from ramcontrol.launcher import Launcher


def absjoin(*paths):
    """Join some paths and make it an absolute path."""
    return os.path.abspath(os.path.join(*paths))


def run_experiment(exp_config):
    """Run the experiment.

    :param dict exp_config:

    """
    exp_dir = absjoin(exp_config['experiment_dir'], exp_config['subdir'])

    pyepl_config_file = absjoin(exp_dir, exp_config['config_file'])
    pyepl_sconfig_file = absjoin(exp_dir, exp_config['sconfig_file'])

    archive_dir = absjoin(exp_config['archive_dir'], exp_config['experiment'])

    options = [
        '--subject', exp_config['subject'],
        '--config', pyepl_config_file,
        '--sconfig', pyepl_sconfig_file,  # secondary config (e.g., differences between FR1 and FR3)
        '--resolution', exp_config['resolution'],
        '--archive', archive_dir,
    ]
    if exp_config['no_fs']:
        options.append('--no-fs')

    exp_file = absjoin(exp_dir, exp_config['exp_py'])

    args = ['python', exp_file] + options

    # FIXME: rework experiments to not need path manipulation
    env = os.environ.copy()
    env["PYTHONPATH"] = absjoin(".")

    # Additional config options to signal via env vars
    env["RAM_CONFIG"] = json.dumps({
        "no_host": exp_config.pop("no_host"),
        "voiceserver": exp_config["experiment"] is "FR5",  # TODO: make switchable
        "ps4": exp_config["ps4"]
    })

    p = subprocess.Popen(args, env=env, cwd=exp_dir)
    p.wait()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', '-s', default=None, help='Subject Code')
    parser.add_argument('--experiment', '-x', default=None, help='Experiment name')
    parser.add_argument('--resolution', '-r', default=None, help='Screen resolution')
    parser.add_argument('--archive', '-a', default=None, help='Data storage directory')
    parser.add_argument("--ps4", default=False, action="store_true",
                        help="Run as a PS4 session (only some experiments support this)")
    parser.add_argument('--no-fs', dest="no_fs", default=False, action='store_true',
                        help='Turn off fullscreen')
    parser.add_argument("--no-host", default=False, action="store_true",
                        help="Run without connecting to the host PC (for development only)")
    parser.add_argument("--experiment-dir", "-e", help="Directory containing experiments")
    return {k: v for k, v in vars(parser.parse_args()).items() if v is not None}


if __name__ == '__main__':
    config = json.load(open("ramcontrol.json", 'r'))
    args = parse_args()

    if "experiment" not in args or "subject" not in args:
        args = Launcher.get_updated_args(sorted(config["experiments"].keys()),
                                         args, config["ps4able"])

    if args is not None:
        # Override default experiment dir
        if "experiment_dir" in args:
            config["experiment_dir"] = args["experiment_dir"]

        config.update(config["experiments"][args["experiment"]])
        config.update(args)
        config["experiment"] = args["experiment"]

        print("Using configuration\n\n",
              json.dumps(config, indent=2, sort_keys=True))
        run_experiment(config)
    else:
        print("Canceled!")
