# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import asyncio
import sys

from .. import getArchive
from ..util import run_with_timeout, add_common_args, add_search_args

def getargs():
    from argparse import ArgumentParser
    P = ArgumentParser()

    add_common_args(P.add_argument_group("Common"))
    add_search_args(P.add_argument_group('Matching'))

    P.add_argument('names', nargs='*', default=['.*'], help='PV names/patterns')

    return P

async def amain(args):
    async with await getArchive(args.conf) as arch:

        Qs = [arch.search(name, match=args.match) for name in args.names]

        grps = await asyncio.gather(*Qs)

        matches = {}
        [matches.update(pvs) for pvs in grps]

        matches = sorted(matches.keys())

        for pv in matches:
            print(pv)

        if len(matches)==0:
            sys.exit(1)
            

def main():
    run_with_timeout(getargs, amain)

if __name__=='__main__':
    main()
