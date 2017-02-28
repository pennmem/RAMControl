# RAM System 3 Task Laptop code

## Basic setup

**Note**: These instructions assume PyEPL is already installed.

Clone this repository to a sensible place, e.g.,
`~/src/task_laptop/ram_tasks`. Experiments are included in this repository via
git submodules. To obtain:

```
$ git submodule init
$ git submodule update
```

Next, videos must be extracted or else the tasks will crash whenever
encountering a video:

```
$ ./vidextract.sh
```


## Updating

```
$ git pull
$ git submodule update
```

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
