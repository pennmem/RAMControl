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
