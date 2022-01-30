# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import sys
import os
import re
import logging
import asyncio
from collections import OrderedDict

from .. import getArchive
from ..util import run_with_timeout, add_common_args, add_search_args, add_query_args

_log = logging.getLogger(__name__)

def _pv2grp(M):
    return rf'\\{M.group(0)}'

def pv2grp(name):
    return re.sub(r'[./]', _pv2grp, name)

def getargs():
    from argparse import ArgumentParser
    P = ArgumentParser()

    add_common_args(P.add_argument_group("Common"))
    add_search_args(P.add_argument_group('Matching'))

    G = P.add_argument_group('Query')

    add_query_args(G)

    P.add_argument('output', help='Output .h5 file name, with optional group.  eg. "file.h5:/grp"')

    P.add_argument('names', nargs='*', default=[])

    P.add_argument('--pv-list', metavar='FILE', dest='pvlist',
                 help='Read PVs from file in addition to argument list ("-" for stdin)')

    return P

async def getnprint(args, arch, pv, grp):
    esc = pv2grp(pv)
    grp = grp.require_group(esc)
    Vs, Ms = None, None

    async for V,M in arch.raw_iter(pv, T0=args.start, Tend=args.end, chunkSize=args.chunk):
        if Vs is None: # first iteration
            Vs = grp.create_dataset('value',
                                    shape = (0,0),
                                    dtype = V.dtype,
                                    maxshape = (None,None),
                                    chunks = V.shape,
                                    shuffle=True,
                                    compression='gzip')
            Ms = grp.create_dataset('meta',
                                    shape = (0,),
                                    dtype = M.dtype,
                                    maxshape = (None,),
                                    chunks = M.shape,
                                    shuffle=True,
                                    compression='gzip')

            check_type = V.dtype

        elif check_type.dtype!=V.dtype:
            ok = check_type.dtype.kind  in ('i','f') and V.dtype.kind in ('i', 'f')
            check_type = V.dtype
            if ok:
                _log.warn('Type change %r -> %r.  Using implicit cast', check_type, V.dtype)
            else:
                _log.error('Type change %r -> %r not supported.  Dropping samples.', check_type, V.dtype)
                continue

        mstart = Ms.shape[0]
        Vs.resize((mstart+V.shape[0], max(Vs.shape[1], V.shape[1])))
        Vs[mstart:,:V.shape[1]] = V
        Ms.resize((mstart+M.shape[0],))
        Ms[mstart:] = M

    if Vs is None:
        _log.warn('%r : No data', pv)
    else:
        _log.info('%r : %r', pv, Vs.shape)

async def amain(args):

    try:
        from h5py import File
    except ImportError:
        _log.exception("Unable to import h5py, which must be installed to export as HDF5")
        sys.exit(1)

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

        if len(matches)==0:
            print("No PVs", file=sys.stderr)
            sys.exit(1)

        sep = args.output.rfind(':')
        if sep<=2: # colon not found, or (probably) windows drive letter
            fname, gname = args.output, '/'
        else:
            fname, gname = args.output[:sep], args.output[1+sep:]

        _log.debug("Opening %s w. %s", fname, gname)

        with File(fname, mode="a") as h5:
            _log.info('Writing %s', os.path.join(os.getcwd(), h5.filename))
            grp = h5.require_group(gname)

            Qs = [getnprint(args, arch, pv, grp) for pv in matches]

            await asyncio.gather(*Qs)

            h5.flush()

def main():
    run_with_timeout(getargs, amain)

if __name__=='__main__':
    main()
