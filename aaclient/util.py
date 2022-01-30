# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import asyncio
import argparse
import logging
import signal
import re
import sys

from threading import Thread, Event
from queue import Queue, Full

from . import MatchMode

_log = logging.getLogger(__name__)

_wild = re.compile(r'''
    (?:\\.) | [*?] | [^*?\\]+
''', re.VERBOSE)

def _w2e(M):
    I = M.group(0)
    if I=='?':
        return '.'
    elif I=='*':
        return '.*'
    elif I[0]=='\\':
        return I
    else:
        return re.escape(I)

def wild2re(pat):
    """Translate a wildcard pattern string into a regular expression string.
    """
    return _wild.sub(_w2e, pat)

class A2TQueue:
    """Queue with coroutine producer and consumer thread
    """

    def __init__(self, maxsize=0):
        self._Q = Queue(maxsize)
        self.__put_wait = []
        self.task_done = self._Q.task_done

    async def put(self, item):
        while True:
            try:
                self._Q.put(item, block=False)
                return
            except Full:
                while self._Q.full():
                    E = asyncio.Event()
                    self.__put_wait.append(E)
                    await E

    def get(self, *args, **kws):
        R = self._Q.get(*args, **kws)
        try:
            W = self.__put_wait.pop()
        except IndexError:
            pass
        else:
            W.set()
        return R

class WorkerLoop:
    """Runs an asyncio loop in a worker thread.  Use call() or __call__() to submit work.
    Must be explicitly close()'d as GC will not collect due to references held by worker.
    """
    __all_loops = set()

    def __init__(self, *, timeout=None, debug=False):
        self.debug = debug
        self.timeout = timeout
        rdy = Event()
        self._T = Thread(target=asyncio.run,
                         args=(self.__run(rdy),),
                         kwargs=dict(debug=debug),
                         name=__name__,
                         daemon=True)
        self._T.start()
        rdy.wait()
        self.__all_loops.add(self)
        assert self.__close is not None
        _log.debug("Started %r", self)

    def __enter__(self):
        return self
    def __exit__(self,A,B,C):
        self.close()

    def close(self):
        """Stop loop and block to join worker thread.
        """
        if self._T is not None:
            _log.debug("Stopping %r", self)
            self.__loop.call_soon_threadsafe(self.__close)
            self._T.join()
            self._T = None
            self.__all_loops.remove(self)
            _log.debug("Stopped %r", self)

    async def __run(self, rdy): # we are called via asyncio.run()
        done = asyncio.Event()
        self.__close = done.set
        self.__loop = asyncio.get_running_loop()

        if hasattr(signal, 'pthread_sigmask'):
            # try to force signal delivery to main()
            signal.pthread_sigmask(signal.SIG_BLOCK, {signal.SIGINT, signal.SIGTERM})

        rdy.set() # allow ctor to complete
        del rdy

        await done.wait() # park to keep loop alive while handling work

    def call(self, coro):
        """Submit work and return an concurrent.futures.Future
        """
        assert asyncio.iscoroutine(coro), coro
        return asyncio.run_coroutine_threadsafe(
            coro,
            self.__loop,
        )

    def __call__(self, coro, *, timeout=None):
        """Submit work and block until completion
        """
        return self.call(coro).result(timeout or self.timeout)

    @classmethod
    def _stop_worker_loops(klass):
        for L in klass.__all_loops.copy():
            L.close()
        assert klass.__all_loops==set(), klass.__all_loops

def add_common_args(P):
    P.add_argument('-C', '--conf', default='DEFAULT', help='Config file section name')
    P.add_argument('-w', '--timeout', type=float, default=30.0,
                   help='Operation timeout in seconds')
    P.add_argument('-v', '--verbose', dest='level', action='store_const',
                   const=logging.DEBUG, default=logging.INFO,
                   help='Make more noise')

def add_search_args(G):
    G.add_argument('-W', '--wildcard', action='store_const', dest='match', const=MatchMode.Wildcard,
                   help='Match names as wildcard patterns')
    G.add_argument('-R', '--regexp', action='store_const', dest='match', const=MatchMode.Regex,
                   default=MatchMode.Regex,
                   help='Match names as regular expressions  (default)')
    G.add_argument('--exact', action='store_const', dest='match', const=MatchMode.Exact,
                   help='Match names exactly')

class TimeHelp(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        from .date import __doc__ as msg
        print(msg)
        print("""
The --start (-s) and --end (-e) arguments may each by either an absolute or relative time.
If one is absolute and the other relative, then the relative time is interpreted with
respect to the absolute.  eg. the following are equivalent:

  -s "2021/1/13 00:00" -e "2021/1/13 02:00"
  -s "2021/1/13 00:00" -e "2 hours"
  -s="-2 hours" -e "2021/5/13 02:00"

If both are absolute, then they are interpreted wrt. the current date and time. eg.

  --start=-2h --end=now
  --start=-2h --end="-1 h"

Absolute date may be abbreviated by omitting the year or entire date.

  -s 12:00 -e 1h        # from 12:00 -> 13:00 of the current day
  -s "1/13 12:00" -e 1h # from 12:00 -> 13:00 on 13 Jan of the current year
""")
        sys.exit(0)

def add_query_args(G):
    G.add_argument('-s','--start', metavar='TIME',
                   help='Start of query window')
    G.add_argument('-e','--end', metavar='TIME', default=None,
                   help='End of query window)')
    G.add_argument('--help-time', action=TimeHelp, nargs=0,
                   help='Print help for TIME range specification')
    G.add_argument('-l','--chunk', metavar='NUM', type=int,
                   help='Query batch size in sample')

    G.add_argument('-H','--how', metavar='NAME', default='raw',
                   help="Query method (eg. raw or plot)")

def run_with_timeout(getargs, corofn):
    args = getargs().parse_args()
    logging.basicConfig(level=args.level)
    _log.debug('%r', args)
    try:
        asyncio.run(asyncio.wait_for(corofn(args), timeout=args.timeout or None))
    except asyncio.TimeoutError:
        print('Unexpected timeout', file=sys.stderr)
        sys.exit(1)
