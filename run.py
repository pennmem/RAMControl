import json
import subprocess
import os
import argparse

JSON_CONFIG = 'source/run_config.json'

def run_experiment(exp_config):
    exp_dir = os.path.abspath(os.path.join(exp_config['experiment_dir'], exp_config['RAM_exp']))

    pyepl_config_file = os.path.join(exp_dir, exp_config['config_file'])
    pyepl_sconfig_file = os.path.join(exp_dir, exp_config['sconfig_file'])

    archive_dir = os.path.abspath(os.path.join(exp_config['archive_dir'], exp_config['experiment']))

    options = [
        '--subject', exp_config['subject'],
        '--config', pyepl_config_file,
        '--sconfig', pyepl_sconfig_file,
        '--resolution', exp_config['resolution'],
        '--archive', archive_dir,
    ]
    if exp_config['no_fs']:
        options.append('--no-fs')

    exp_file = os.path.join(exp_dir, exp_config['exp_py'])

    args = ['python', exp_file] + options

    env = os.environ.copy()
    if 'PYTHONPATH' in env:
        env['PYTHONPATH'] = os.path.abspath(exp_config['pythonpath']) + ":" + env['PYTHONPATH']
    else:
        env['PYTHONPATH'] = os.path.abspath(exp_config['pythonpath'])
    
    os.chdir(exp_dir)

    p = subprocess.Popen(args, env=env)
    p.wait()

def build_exp_config(json_config, experiment, **kwargs):
    exp_config = json_config['experiments'][experiment]
    json_config.update(exp_config)
    json_config.update(kwargs)
    json_config['experiment'] = experiment
    return config

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--subject', '-s', dest='subject', default=None, help='Subject Code')
    parser.add_argument('--experiment', '-x', dest='experiment', default=None, help='Experiment name')
    parser.add_argument('--resolution', '-r', dest='resolution', default=None, help='Screen resolution')
    parser.add_argument('--archive', '-a', dest='archive', default=None, help='Data storage directory')
    parser.add_argument('--no-fs', dest='no_fs', default=False, action='store_true', help='Turn off fullscreen')
    return {k:v for k,v in vars(parser.parse_args()).items() if v is not None}


if __name__ == '__main__':
    config = json.load(open(JSON_CONFIG,'r'))
    args = parse_args()

    while 'experiment' not in args:
        experiment = raw_input("Enter experiment name: ")
        if experiment not in config['experiments']:
            print("Experiment must be one of: " + ', '.join(sorted(config['experiments'].keys())))
        else:
            args['experiment'] = experiment

    while 'subject' not in args:
        subject = raw_input("Enter subject code: ")
        if len(subject.strip())!=0:
            args['subject'] = subject

    exp_config = build_exp_config(config, **args)

    run_experiment(exp_config)

