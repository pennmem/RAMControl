from setuptools import setup

with open("requirements.txt") as f:
    requirements = f.read()

setup(
    name="ramcontrol",
    packages=["ramcontrol"],
    install_requires=requirements
)
