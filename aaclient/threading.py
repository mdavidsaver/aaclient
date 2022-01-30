# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import logging
from functools import wraps

from . import (getArchive as getArchiveAsyncio, IArchive)
from .util import WorkerLoop, A2TQueue

_log = logging.getLogger(__name__)

__all__ = (
    'getArchive',
)

class BlockingArchive:
    def __init__(self, *args, timeout=5.0, debug=False, **kws):
        self._W = WorkerLoop(timeout=timeout, debug=debug)

        try:
            self.__arch = self._W(getArchiveAsyncio(*args, **kws))
        except:
            self._W = None # avoid secondary error during __del__()
            raise

    def __enter__(self):
        return self
    def __exit__(self,A,B,C):
        self.close()

    def __del__(self):
        self.close()

    @wraps(IArchive.close)
    def close(self, timeout=None):
        if self._W is not None:
            self._W(self.__arch.close())
            self._W.close()
            self._W = None

    @wraps(IArchive.search)
    def search(self, *args, timeout=None, **kws):
        return self._W(self.__arch.search(*args, **kws), timeout=timeout)

    @wraps(IArchive.grep)
    def grep(self, *args, timeout=None, **kws):
        return self._W(self.__arch.grep(*args, **kws), timeout=timeout)

    @wraps(IArchive.raw)
    def raw(self, *args, timeout=None, **kws):
        return self._W(self.__arch.raw(*args, **kws), timeout=timeout)

    @wraps(IArchive.plot)
    def plot(self, *args, timeout=None, **kws):
        return self._W(self.__arch.plot(*args, **kws), timeout=timeout)

    @wraps(IArchive.raw_iter)
    def raw_iter(self, *args, timeout=None, **kws):
        Q = A2TQueue(4)
        F = self._W.call(self.__raw_iter(Q, *args, **kws))
        while True:
            P = Q.get(timeout or self._W.timeout)
            if P is None:
                break
            yield P
            Q.task_done()
        F.result()

    async def __raw_iter(self, Q, *args, **kws):
        try:
            async for P in self.__arch.raw_iter(*args, **kws):
                await Q.put(P)

        finally:
            await Q.put(None)

getArchive = BlockingArchive
