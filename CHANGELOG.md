# Changes

## Version 3.1.11

**2017-08-11**

* Disabled REC1 in catFR5/FR5 by default. 

## Version 3.1.10

**2017-07-12**

* Improved logging

## Version 3.1.9

**2017-05-23**

* New practice lists are available for FR and catFR experiments.
* List generation has been moved into the separate [wordpool][] package.
* `use_eeg` for PyEPL is now set to `True`. This is for the benefit of some
  sites and has no effect for others.

To upgrade from version 3.1.8:

```
git checkout v3.1
git pull
pip install -U -r requirements.txt
```

[wordpool]: https://github.com/pennmem/wordpool

## Version 3.1.8

**2017-05-16**

Major additions:

* Added support for PAL1 and PAL5

Other changes:

* Updated practice lists in FR/catFR experiments to be presented in random order
  (consistent with the tasks prior to System 3).
* Updated the `run_experiment` bash script to keep the terminal window open
  until enter is pressed.
* PS4 sessions are now limited to PS4_FR5 and stop after 10 lists (on the host).
* The `getvideos.sh` script now uses rsync to only download what is missing or
  updated.

To upgrade:

```
git checkout v3.1
git pull
./getvideos.sh
```

## Version 3.1.7

**2017-04-28**

* Critical bug fix: ensure that lists displayed are unique to each session.
* Updated defaults in the upload tool.

To upgrade:

```
git checkout v3.1 && git pull
```

## Version 3.1.6

**2017-04-21**

* Two views now exist on the SQLite session logs: `events` and `word_onsets`.
  These can be used to select the JSON messages for all events and all word
  onsets, respectively.
* Fixed issue where `*.lst` files didn't always contain the correct words.
* Word pools written to session folders are in a more human-friendly format (a
  tab-separated table instead of JSON).

To upgrade:

```
git checkout v3.1 && git pull
```

## Version 3.1.5

**2017-04-12**

* We don't need to use a dumb naming convention for `*.lst` files after all.
  They are now named `0.lst`, `1.lst`, etc.

To upgrade:

```
git checkout v3.1 && git pull
```

## Version 3.1.4

**2017-04-12**

* Fixed issue with wrong word list being written to catFR data directories.
* Re-added writing of `*.lst` files. These had been removed because it was
  incorrectly thought that they were not used in post-processing, but in reality
  they are used during annotation.
* System version numbers are now explicitly logged in the SQLite session log.

To upgrade from previous 3.1.x versions:

```
git checkout v3.1 && git pull
```

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
