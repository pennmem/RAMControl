# Release notes

## Version 3.1.0

**Soon**

* Supported experiments: FR1, FR3, FR5, PS4_FR5
* Ramulator version required: 3.x.y
* ENSGateway version required: 3.x.y

### Upgrading from version 3.0

As the **admin** user:

* Ensure permissions are correct: `sudo chown -R exp /Users/exp/miniconda2/lib`
* Install portaudio: `brew install portaudio`

As the **exp** user:

* Ensure that conda, pip, and setuptools are up to date:

```
$ conda update conda
$ pip install -U pip
$ pip install -U setuptools
```

* Fetch the latest version of this repository with git.
* Install [PyAudio][]: `CPATH=/usr/local/include LIBRARY_PATH=/usr/local/lib pip install pyaudio`
* Install numpy and friends:

```
conda install -y numpy pandas
```

* Install other Python requirements: `pip install -r requirements.txt`
* Copy videos to `./videos` (TODO: make available more robustly)

[PyAudio]: https://people.csail.mit.edu/hubert/pyaudio/

## Version 3.0.0

**2017-02-09**

* Supported experiments: FR1, CatFR1, PAL1, FR3, CatFR3, PAL3
* Ramulator version required: 3.0.0
* ENSGateway version required: 3.0.0

### Installation

The installation procedure requires an existing install of RAM 2.0 software. The
upgrade procedure is detailed in the [pyepl_upgrade][] repository README file.

[pyepl_upgrade]: https://github.com/ramdarpaprojectorg/pyepl_upgrade
