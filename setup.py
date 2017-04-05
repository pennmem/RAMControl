import os
from setuptools import setup
from subprocess import check_call as run, Popen


# this doesn't work...
def pre_install_tasks():
    run("conda install -y numpy pandas".split())
    run("pip install -U pip".split())
    run("pip install -U setuptools".split())
    run("pip install -r requirements.txt".split())

    # install pyaudio
    env = os.environ.copy()
    env.update({
        "CPATH": "/usr/local/include",
        "LIBRARY_PATH": "LIBRARY_PATH=/usr/local/lib"
    })
    Popen("pip install pyaudio".split(), env=env).wait(timeout=30)

    run("./getvideos.sh")

    print("All done!")

# with open("requirements.txt") as f:
#     requirements = f.read()

# setup(
#     name="ramcontrol",
#     packages=["ramcontrol"],
#     install_requires=requirements
# )
