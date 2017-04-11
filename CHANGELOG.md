# Changes

## Version 3.1.3

**2017-04-11**

* Fixed bug preventing the session number from automatically incrementing upon
  session completion.
  
To upgrade from previous 3.1.x versions:

```
git pull
git checkout v3.1.3
```

## Version 3.1.2

**2017-04-07**

* Added support for catFR1, catFR3, catFR5, and PS4_catFR5

### Upgrade instructions

To upgrade from previous 3.1.x versions, do a git pull and checkout the
v3.1.2 tag:

```
git pull
git checkout v3.1.2
```

## Version 3.1.1

**2017-03-28**

Point release to add video downloading script. See the notes for
[v3.1.0](#version-310) below for upgrade instructions.

## Version 3.1.0

**2017-03-27**

* Supported experiments: FR1, FR3, FR5, PS4_FR5
* Ramulator version required: 3.1.
* Introduces voice activity detection (VAD) during retrieval

### Notes

VAD can be enabled during retrieval by modifying the configuration file variable
`vad_during_retrieval`. By default, this is `False` in all FR experiments, but
enabled in FR5 and PS4_FR5.

Setting the microphone input volume too high results in many VAD false positives
from ambient noises. The input volume on the laptop should be set somewhere in
the middle (more precise recommendations will be made later based on comparisons
between annotations and recorded VAD events).

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
* Copy videos to `./videos`: `./getvideos.sh`

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
