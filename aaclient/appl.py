# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import logging
import re
import math

import asyncio
import aiohttp

from . import MatchMode, IArchive
from .dtype import aameta
from .util import wild2re
from .date import makeTimeInterval, isoString
from ._ext import StreamDecoder

try:
    from asyncio import to_thread
except ImportError:
    import contextvars
    import functools
    async def to_thread(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        ctx = contextvars.copy_context()
        func_call = functools.partial(ctx.run, func, *args, **kwargs)
        return await loop.run_in_executor(None, func_call)


_log = logging.getLogger(__name__)

class Appl(IArchive):
    def __init__(self, conf):
        self.conf = conf
        self._limit = asyncio.BoundedSemaphore(int(conf['maxquery']))
        self._threshold = int(conf['chunksize'])
        self._ctxt = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout())
        self._info = None

    async def close(self):
        await self._ctxt.close()

    async def search(self, pattern=None, match=MatchMode.Wildcard, **kws):
        if kws:
            _log.warn("Ignore unknown keywords %r", kws)

        if not pattern:
            pattern = '^.*$' # list everything

        elif match is MatchMode.Exact:
            pattern = '^%s$'%re.escape(pattern)

        elif match is MatchMode.Wildcard:
            pattern = wild2re(pattern)

        # Archive Appliance matches the entire line (implicit ^...$)
        # we default to partial match
        if not pattern.startswith('^') and not pattern.startswith('.*'):
            pattern='.*'+pattern
        if not pattern.endswith('$') and not pattern.endswith('.*'):
            pattern=pattern+'.*'

        _log.debug("searching for %r", pattern)

        pvs = await (await self.__get(self._info['mgmtURL']+'/getAllPVs', params={'regex':pattern})).json()

        return {pv:None for pv in pvs}

    _consolidate = True

    async def raw_iter(self, pv, T0=None, Tend=None, chunkSize=None):
        T0, Tend = makeTimeInterval(T0 or self.conf['starttime'], Tend or self.conf['endtime'])
        Q = {
            'pv':pv,
            'from':isoString(T0),
            'to':isoString(Tend),
        }

        D = StreamDecoder(threshold=chunkSize or self._threshold, consolidate=self._consolidate)

        resp = await self.__get(self._info['dataRetrievalURL']+'/data/getData.raw', params=Q,
                                read_bufsize=2**20)

        async with resp:
            last = False
            while True:
                # TODO: pipeline with concurrent readany() of next and process() of previous

                blob = await resp.content.readany()
                if not blob:
                    blob, last = None, True

                if not await to_thread(D.process, blob, last=last):
                    continue # no additional output added

                output, D.output = D.output, []
                for value, meta in output:
                    _log.debug("YIELD samples %s", value.shape)
                    yield value, meta.view(aameta)

                if not blob:
                    break

    async def plot(self, pv, T0=None, Tend=None, count=None, **kws):
        """Request binned data suitable for a simple plot

        Attempts to return ~count samples
        """
        T0, Tend = makeTimeInterval(T0 or self.conf['starttime'], Tend or self.conf['endtime'])
        if not count:
            count = int(self.conf['defaultcount'])

        delta = abs((Tend-T0).total_seconds())
        N = math.ceil(delta/count) # average sample period

        if N<=1 or delta<=0:
            _log.info("Time range %s too short for plot bin %s, switching to raw", delta, count)
        else:
            pv = 'caplotbinning_%d(%s)'%(N,pv)

        return await self.raw(pv, T0=T0, Tend=Tend, **kws)

    async def __get(self, url, *args, **kws):
        _log.debug("GET %r %s %s", url, args, kws)
        async with self._limit:
            return (await self._ctxt.get(url, *args, **kws))

async def getArchive(conf, **kws):
    appl = Appl(conf, **kws)
    try:
        async with appl._ctxt.get(conf['url']) as R:
            appl._info = await R.json()

        _log.debug("Server Info %r %r", conf['url'], appl._info)

        required = {'mgmtURL', 'dataRetrievalURL'}
        if not set(appl._info.keys()).issuperset(required):
            raise RuntimeError(f"Server Info missing some required keys {required} from {appl._info}")

        return appl
    except:
        await appl.close()
        raise
