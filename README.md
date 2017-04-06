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

## Supported experiments

As of 2017-03-28, the following experiments are supported:

* FR1
* FR3
* PS4/FR5
* FR5/REC1

## Troubleshooting

* ZMQerror: check network cable; unplug/replug network cable; kill zombie processes

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
