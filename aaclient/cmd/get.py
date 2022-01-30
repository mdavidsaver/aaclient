# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import asyncio
from collections import OrderedDict
import logging
import sys

from .. import getArchive
from ..date import makeTime
from ..util import run_with_timeout, add_common_args, add_search_args, add_query_args

_log = logging.getLogger(__name__)

def getargs():
    from argparse import ArgumentParser
    P = ArgumentParser()

    add_common_args(P.add_argument_group("Common"))
    add_search_args(P.add_argument_group('Matching'))

    G = P.add_argument_group('Query')

    add_query_args(G)

    G = P.add_argument_group('Output')

    G.add_argument('--skip-first', default=False, action='store_true', dest='skipFirst',
                   help="Don't print first sample.  PVs with only one sample are omitted.")

    G.add_argument('--utc', action='store_true',
                   help='Display times in UTC')

    P.add_argument('names', nargs='*', default=[])

    P.add_argument('--pv-list', metavar='FILE', dest='pvlist',
                 help='Read PVs from file in addition to argument list ("-" for stdin)')

    return P

_sevr = {
    0: 'NO_ALARM',
    1: 'MINOR',
    2: 'MAJOR',
    3: 'INVALID',
    3904: 'DISCONNECT',
}

async def getnprint(args, arch, pv, printName=True):
    _log.debug("get %r : %s -> %s", pv, args.start, args.end)

    first = True
    def printpv(val, meta):
        nonlocal first
        if first and args.skipFirst:
            val, meta = val[1:, :], meta[1:]

        if meta.shape[0]==0:
            return
        first = False

        for i in range(meta.shape[0]):
            V, M = val[i,:], meta[i]
            T = makeTime((M['sec'], M['ns']))
            if not args.utc:
                T = T.astimezone()
            out = [
                T.strftime('%m-%d %H:%M:%S.%f')
            ]

            if printName:
                out.append(pv)

            if len(V.shape)==1: # scalar, print alarm after value
                out.append(str(V[0]))

            sevr = M['severity']
            if sevr:
                out += [_sevr.get(sevr) or str(sevr), str(M['status'])]

            if len(V.shape)!=1: # scalar, print alarm before value
                out.append(repr(V))

            print(' '.join(out))

    if args.how=='raw':
        async for val,meta in arch.raw_iter(pv, T0=args.start, Tend=args.end, chunkSize=args.chunk):
            printpv(val,meta)

    elif args.how=='plot':
        val, meta = await arch.plot(pv, T0=args.start, Tend=args.end, chunkSize=args.chunk)
        printpv(val,meta)

    else:
        raise ValueError(f"Unknown --how {args.how}")

async def amain(args):
    async with await getArchive(args.conf) as arch:

        matches = OrderedDict()
        if args.names:
            Qs = [arch.search(name, match=args.match) for name in args.names]

            grps = await asyncio.gather(*Qs)

            [matches.update(pvs) for pvs in grps]

        if args.pvlist:
            with open(args.pvlist, 'rb') as F:
                for line in F:
                    line = line.strip()
                    if not line or line[0:1]==b'#':
                        continue
                    matches[line] = ()

        printName = len(matches)==1

        if len(matches)==0:
            print("No PVs", file=sys.stderr)
            sys.exit(1)

        Qs = [getnprint(args, arch, pv, printName) for pv in matches]

        await asyncio.gather(*Qs)

def main():
    run_with_timeout(getargs, amain)

if __name__=='__main__':
    main()
