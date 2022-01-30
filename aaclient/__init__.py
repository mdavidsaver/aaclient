# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import os
import platform
import enum
from importlib import import_module

import numpy as np

from .dtype import aameta

__all__ = (
    'getArchive',
    'MatchMode',
)

# finding bundled libprotobuf-lite.dll in wheel builds
if hasattr(os, 'add_dll_directory'): # windows
    os.add_dll_directory(os.path.dirname(__file__))
elif platform.system()=='Windows':
    os.environ['PATH'] = os.pathsep.join([
        os.path.dirname(__file__),
        os.environ['PATH'],
    ])

class MatchMode(enum.Enum):
    Exact = 0
    Wildcard = 1
    Regex = 2

class IArchive:
    """Archiver system access
    """
    async def __aenter__(self):
        return self
    async def __aexit__(self,A,B,C):
        await self.close()

    async def close(self):
        """Cleanup
        """
        raise NotImplementedError()

    async def search(self, pattern=None, match=MatchMode.Wildcard, **kws):
        """Lookup PV names exactly or by matching a pattern.

        Returns a mapping of PV name to as yet unspecified information about the PV. ::

            with getArchive() as arch:
                pvs = await arch.search("wild?pattern*")
        """
        raise NotImplementedError()

    async def grep(self, pattern, **kws):
        """Alias for search() with MatchMode.Regex
        """
        return await self.search(pattern, match=MatchMode.Regex, **kws)

    async def raw_iter(self, pv, T0=None, Tend=None, chunkSize=None):
        """Request raw data in time range.

        Returns an async generator which will yield tuples of (ndarray, ndarray)
        with values and time+alarm meta-data.
        """
        raise NotImplementedError()

    async def raw(self, *args, **kws):
        """raw(pv, T0=None, Tend=None, chunkSize=None)
        Request raw data in time range.

        Calls raw_iter() and accumulates results into a single pair of value and meta-data ndarrays.
        This requires that PV data-type/shape did not change during the request interval.
        """
        vals, metas = [], []
        async for V,M in self.raw_iter(*args, **kws):
            vals.append(V)
            metas.append(M)

        return np.concatenate(vals, axis=0), np.concatenate(metas, axis=0).view(aameta)

    async def plot(self, pv, T0=None, Tend=None, count=None, **kws):
        """Request server-side binned data suitable for a simple plot.
        """
        raise NotImplementedError()


async def getArchive(conf='DEFAULT', **kws):
    """Completes with an IArchive instance which
    """
    if conf is None or isinstance(conf, str):
        from .conf import loadConfig
        conf = loadConfig(conf)

    utype = conf['urltype']
    try:
        mod = import_module(utype, __name__)
        gA = mod.getArchive
    except ImportError:
        raise RuntimeError(f"urltype {utype!r} is not a python module name")
    except AttributeError:
        raise RuntimeError(f"urltype {utype!r} is not a backend")
    ret = await gA(conf, **kws)
    assert isinstance(ret, IArchive), ret
    return ret
