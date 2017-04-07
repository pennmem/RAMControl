# RAM System 3.1 Task Laptop code

## Upgrading from version 3.0

### As the `admin` user

* Ensure permissions are correct: `sudo chown -R exp /Users/exp/miniconda2/lib`
* Check if Xcode needs to be updated (you'll need Xcode version 8.x) by opening
  the App Store.
* If [homebrew](https://brew.sh/) is not installed, install it
* Install portaudio: `brew install portaudio`

### As the `exp` user

Clone the `v3.1` branch of RAMControl:

```
$ git clone https://github.com/ramdarpaprojectorg/RAMControl.git -b v3.1 ~/RAM_3.1
```

Then `cd ~/RAM_3.1` and run:

```
./install.sh
```

## Upgrading from previous 3.1.x versions

Please see the `CHANGELOG.md` file for instructions.

## Supported experiments

As of 2017-03-28, the following experiments are supported:

* FR1
* catFR1
* FR3
* catFR3
* PS4/FR5
* PS4/catFR5
* FR5/REC1
* catFR5/REC1

## Troubleshooting

Tasks can be started in debug mode to diagnose problems. This requires opening
a terminal, navigating to the directory with the task code, and running with:

```
$ python run.py -d
```

(see also `--help` to see other options). This will start PyEPL in windowed
mode and allow you to check output in the terminal.

### ZMQ errors

This happens when the ethernet cable is unplugged from either the task laptop,
the host PC, or both.

1. Check that the cable is plugged into both computers. Try starting the
   experiment again.
2. Unplug and replug the cables and try again.
3. See if a zombie process is hogging the TCP port and kill by PID if so:
   `lsof -i tcp:8889`

## Notes for developers

### Debugger

For testing host applications, there is a debugger script included. You can
generate scripted messages from the host PC's `output.log`
(see `tests/FR1_output.log`). Example:

```
$ python -m ramcontrol.debugger.py generate -s test -x FR1 -n 1 -o fr1_script.csv -f tests/FR1_output.log
```

To run the generated script:

```
$ python -m ramcontrol.debugger.py run -f fr1_script.csv
```

Caveat emptor: Make sure you have loaded the experimental configuration on the
host PC first!

### Testing

Unit testing is in the process of being added. To run existing tests, you'll
need to run

```
$ pip install -r requirements.txt
$ pip install -e .
```

Then tests are run with

```
$ pytest
```
