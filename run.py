"""Script to start RAM experiments."""

import json
import subprocess
import os
import argparse
import six


def absjoin(*paths):
    """Join some paths and make it an absolute path."""
    return os.path.abspath(os.path.join(*paths))


def run_experiment(exp_config):
    """Run the experiment.

    :param dict exp_config:

    """
    exp_dir = absjoin(exp_config['experiment_dir'], exp_config['RAM_exp'])

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

    # Flag that we shouldn't try to connect to the host PC (for development
    # purposes)
    env["RAM_CONFIG"] = json.dumps(dict(no_host=exp_config.pop("no_host")))

    p = subprocess.Popen(args, env=env, cwd=exp_dir)
    p.wait()


def build_exp_config(json_config, experiment, **kwargs):
    """Build experiment configuration from the JSON config file.

    :param dict json_config:
    :param str experiment: Name of the experiment.
    :param dict kwargs:
    :rtype: dict

    """
    exp_config = json_config['experiments'][experiment]
    json_config.update(exp_config)
    json_config.update(kwargs)
    json_config['experiment'] = experiment
    return json_config


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', '-s', dest='subject', default=None, help='Subject Code')
    parser.add_argument('--experiment', '-x', dest='experiment', default=None, help='Experiment name')
    parser.add_argument('--resolution', '-r', dest='resolution', default=None, help='Screen resolution')
    parser.add_argument('--archive', '-a', dest='archive', default=None, help='Data storage directory')
    parser.add_argument('--no-fs', dest='no_fs', default=False, action='store_true', help='Turn off fullscreen')
    parser.add_argument("--no-host", default=False, action="store_true",
                        help="Run without connecting to the host PC (for development only)")
    parser.add_argument("--experiment-dir", "-e", help="Directory containing experiments")
    return {k: v for k, v in vars(parser.parse_args()).items() if v is not None}


if __name__ == '__main__':
    config = json.load(open("run_config.json", 'r'))
    args = parse_args()

    while 'experiment' not in args:
        experiment = six.moves.input("Enter experiment name: ")
        if experiment not in config['experiments']:
            print("Experiment must be one of: " + ', '.join(sorted(config['experiments'].keys())))
        else:
            args['experiment'] = experiment

    while 'subject' not in args:
        subject = six.moves.input("Enter subject code: ")
        if len(subject.strip()) != 0:
            args['subject'] = subject

    # Override default experiment dir
    if "experiment_dir" in args:
        config["experiment_dir"] = args["experiment_dir"]

    exp_config = build_exp_config(config, **args)

    run_experiment(exp_config)
