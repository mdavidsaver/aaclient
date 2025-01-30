# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import logging
import re
import math
from urllib.parse import urlparse, urlunparse

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

# name with postprocessing operator
# eg. "caplotbinning_42(some*pattern)"
_op_pattern = re.compile(r'''
    ([a-zA-Z0-9]+_[0-9]+)\(([^\)]+)\)
''', re.VERBOSE)

_log = logging.getLogger(__name__)

class Appl(IArchive):
    def __init__(self, conf):
        self.conf = conf
        self._limit = asyncio.BoundedSemaphore(int(conf['maxquery']))
        self._threshold = int(conf['chunksize'])
        self._ctxt = aiohttp.ClientSession(raise_for_status=True, timeout=aiohttp.ClientTimeout())
        self._info = None

    async def close(self):
        if self._ctxt is not None:
            await self._ctxt.close()
            self._ctxt = None

    async def search(self, pattern: str, match=MatchMode.Wildcard, **kws):
        assert match in MatchMode, match
        if kws:
            _log.warn("Ignore unknown keywords %r", kws)

        opM = _op_pattern.match(pattern)
        if opM is not None:
            pattern = opM.group(2) # bare PV name pattern
            _log.debug('Detected operator %r', opM.group(1))

        if match is MatchMode.Exact:
            pattern = '^%s$'%re.escape(pattern)
            opM = None

        elif match is MatchMode.Wildcard:
            pattern = wild2re(pattern)

        else:
            assert match is MatchMode.Regex

        # Archive Appliance matches the entire line (implicit ^...$)
        # we default to partial match
        if not pattern.startswith('^') and not pattern.startswith('.*'):
            pattern='.*'+pattern
        if not pattern.endswith('$') and not pattern.endswith('.*'):
            pattern=pattern+'.*'

        _log.debug("searching for %r", pattern)

        pvs = await (await self.__get(self._info['mgmtURL']+'/getAllPVs', params={'regex':pattern})).json()

        if opM is not None:
            pvs = [f'{opM.group(1)}({pv})' for pv in pvs]

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

        resp = await self.__get(self._info['retrievalURL'].replace('/bpl','')+'/data/getData.raw', params=Q,
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
        try:
            async with self._limit:
                R = (await self._ctxt.get(url, *args, **kws))
        except:
            _log.exception("GET %r %s %s", url, args, kws)
            raise
        return R

async def getArchive(conf, **kws):
    appl = Appl(conf, **kws)
    try:
        entryURL = conf['url']
        aaHost = urlparse(entryURL).netloc.split(':',1)[0] # host/IP without port#
        async with appl._ctxt.get(entryURL) as R:
            appl._info = await R.json()

        # if appliance info yields component urls with localhost,
        # rewrite to use the request URL.
        for k,v in appl._info.items():
            if not v.startswith('http://') and not v.startswith('https://'):
                continue

            V = urlparse(v)
            netloc = V.netloc.rsplit(':',1)
            if netloc[0] in ('localhost', '127.0.0.1', ):
                netloc[0] = aaHost
                V = V._replace(netloc=':'.join(netloc))

            appl._info[k] = V.geturl()

        _log.debug("Server Info %r %r", conf['url'], appl._info)

        required = {'mgmtURL', 'retrievalURL'}
        if not set(appl._info.keys()).issuperset(required):
            raise RuntimeError(f"Server Info missing some required keys {required} from {appl._info}")

        return appl
    except:
        await appl.close()
        raise
