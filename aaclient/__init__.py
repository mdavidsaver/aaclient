# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import asyncio
import atexit
import contextvars
import logging
import os
import platform
import enum
from typing import Any, AsyncIterable, Dict, Tuple
from weakref import WeakKeyDictionary
from importlib import import_module

import numpy as np

from .dtype import aameta

_log = logging.getLogger(__name__)

__all__ = (
    'getArchive',
    'MatchMode',
    'aaget',
    'aagrep',
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

    async def search(self, pattern=None, match=MatchMode.Wildcard, **kws) -> Dict[str, Any]:
        """Lookup PV names exactly or by matching a pattern.

        Returns a mapping of PV name to as yet unspecified information about the PV. ::

            with getArchive() as arch:
                pvs = await arch.search("wild?pattern*")
        """
        raise NotImplementedError()

    async def grep(self, pattern, **kws) -> Dict[str, Any]:
        """Alias for search() with MatchMode.Regex
        """
        return await self.search(pattern, match=MatchMode.Regex, **kws)

    async def raw_iter(self, pv, T0=None, Tend=None, chunkSize=None) -> AsyncIterable[Tuple[np.ndarray, aameta]]:
        """Request raw data in time range.

        Returns an async generator which will yield tuples of (ndarray, ndarray)
        with values and time+alarm meta-data.
        """
        raise NotImplementedError()

    async def raw(self, *args, **kws) -> Tuple[np.ndarray, aameta]:
        """raw(pv, T0=None, Tend=None, chunkSize=None) -> (ndarray, aameta)
        Request raw data in time range.

        Calls raw_iter() and accumulates results into a single pair of value and meta-data ndarrays.
        This requires that PV data-type/shape did not change during the request interval.
        """
        vals, metas = [], []
        async for V,M in self.raw_iter(*args, **kws):
            vals.append(V)
            metas.append(M)

        return np.concatenate(vals, axis=0), np.concatenate(metas, axis=0).view(aameta)

    async def plot(self, pv, T0=None, Tend=None, count=None, **kws) -> Tuple[np.ndarray, aameta]:
        """Request server-side binned data suitable for a simple plot.
        """
        raise NotImplementedError()


async def getArchive(conf='DEFAULT', **kws) -> IArchive:
    """Entry point for access to a data Archiver.  Completes with an IArchive

    :param conf: Either a string naming a section in an aaclient.conf file,
                 or a dict-like object having the necessary keys from such a file.
    :return: An sub-class of IArchive
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

async def aaget(*args, how='raw', conf=None, **kws):
    """aaget(pv, T0=None, Tend=None, how='raw', **kws)

    Request data from the DEFAULT archiver.  eg. for use with ipython ::

        from aaclient import aaget
        V,M=await aaget('some:pv', T0='-1h')

    :param str pv: PV name to request
    :param T0: Absolute or relative start time for the interval.
               Defaults to the current time.  (String or datetime)
    :param Tend: Absolute or relative end time for the interval.
                 Defaults to the current time.  (String or datetime)
    :param str how: Request method.  eg 'raw' or 'plot'.
    """
    async with await getArchive(conf) as arch:
        meth = getattr(arch, how)
        return await meth(*args, **kws)

async def aasearch(*args, conf=None, **kws):
    """aagrep(pattern=None, match=MatchMode.Regex, **kws)

    Search for PV names available from the DEFAULT archiver.  eg. for use with ipython ::

        from aaclient import aagrep
        V,M=await aagrep('some:.*')

    :param str pattern: PV name pattern
    :param MatchMode match: How to match pattern.  Defaults to regular expression.
    """
    async with await getArchive(conf) as arch:
        return await arch.search(*args, **kws)
