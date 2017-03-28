# RAM System 3.1 Task Laptop code

## Upgrading

Please see [RELEASE_NOTES.md]() for upgrade instructions.

## Supported experiments

As of 2017-03-28, the following experiments are supported:

* FR1
* FR3
* PS4/FR5
* FR5/REC1

## Debugger

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

## Testing

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
