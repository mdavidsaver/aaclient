# Client for EPICS Archive Appliance

Utilities for interacting with an EPICS
[Archiver Appliance](https://slacmshankar.github.io/epicsarchiver_docs/)
server.

For fidelity, data is retrieved in the binary protobuf encoding native to AA.

Intended to supplant https://github.com/epicsdeb/carchivetools

## Building

Requirements from the python ecosystem (eg. pip)

* python >= 3.7
* aiohttp >= 3.7.0 (and perhaps earlier)
* numpy >= 1.7
* Cython >= 0.20
* setuptools >= 40.9.0

Requirements from outside the python ecosystem (eg. rpm, deb, etc.)

* Working C++11 toolchain
* protobuf compiler
* protobuf-lite library and headers for >= 3.0

```sh
apt-get install protobuf-compiler libprotobuf-dev

yum install protobuf-compiler libprotobuf-devel

dnf install protobuf-compiler libprotobuf-devel

brew install protobuf

choco install protoc
```

Build and install with pip

```sh
virtualenv aa
. aa/bin/activate
pip install -U pip
pip install Cython
./setup.py sdist
pip install dist/aaclient-*.tar.gz
arget -h
```

Alternately, for in-place usage (eg. evaluation or troubleshooting).

```sh
./setup.py build_ext -i
python -m aaclient.cmd.get -h
```

In either case a configuration file is **required**.

```sh
cp aaclient.conf.example aaclient.conf
# edit aaclient.conf and fill in at least "host="
```

## Command Line Interface

This package provides several CLI tools for interacting with
an Archiver Appliance server.

See the [example configuration file](aaclient.conf.example).

### `argrep` Searching for PVs

Running `argrep` without arguments will attempt to print a full
list of PV names being archived.
Otherwise query patterns (wildcard or regexp) will be applied.
If multiple patterns are provided, the output will be all
PV names which matched any pattern.

```
$ argrep RH
CO2:RH-I
```

### `arget` Printing data

Query data from a set of PV names for a certain time range
and print the results.

```
$ arget --start='-1 h' --end=now CO2:RH-I
01-30 07:50:11.958813 CO2:RH-I 45.10040283203125
01-30 08:13:04.816086 CO2:RH-I 44.56939697265625
01-30 08:40:41.527406 CO2:RH-I 44.06585693359375
```

### `arh5` Extract to HDF5 file

Queries like `arget`, with results written to a HDF5 file
instead of being printed to screen.

```
$ arh5 --start='-1 h' --end=now out.h5 CO2:RH-I
INFO:__main__:'CO2:RH-I' : (3, 1)
$ h5ls -r out.h5 
/                        Group
/CO2:RH-I                Group
/CO2:RH-I/meta           Dataset {3/Inf}
/CO2:RH-I/value          Dataset {3/Inf, 1/Inf}
```

### Alternate entry points.

* `arget` -> `python -m aaclient.cmd.get`
* `argrep` -> `python -m aaclient.cmd.grep`
* `arh5` -> `python -m aaclient.cmd.h5`


## API

The API behind the CLI executables is (primarily) asyncio based.

```py
import asyncio
from aaclient import getArchive

async def demo():
    A= await getArchive()

    V,M = await A.raw('CO2:CO2-I', T0='-12 h')
    print(V.shape, M.shape)

asyncio.run(demo())
```

The entry point for API usage is `aaclient.getArchive()`,
which returns an object inheriting from `aaclient.IArchive`.

### Streaming

The `aaclient.IArchive.raw_iter()` method allows for incremental
retrieval of arbitrarily large data for long time range.

### Blocking API

A blocking (threaded) API is also provided as a convenience
for interactive usage.

```py
from matplotlib.pyplot import *
from aaclient.threading import getArchive
A=getArchive()

# Request ~1000 points of "caplotbinning" data
# suitable for quick/efficient visualization of a
# long time range
V,M = A.plot('CO2:CO2-I', T0='-7 d', count=1000)

figure()
plot_date(M.time_mpl, V[:,0], '-')
grid(True)

# Request complete (raw) data for a (shorter)
# time range
figure()
V,M = A.raw('CO2:CO2-I', T0='-12 h')
plot_date(M.time_mpl, V[:,0], '-')
grid(True)

show()
```
