# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import re
import os
import sys
import logging
from pathlib import Path
from functools import wraps
from tempfile import TemporaryDirectory, TemporaryFile
import unittest
import asyncio

import numpy as np
from numpy.testing import assert_equal

from aiohttp.web import (
    Application,
    AppRunner,
    TCPSite,
    get as http_get,
    Response,
    json_response,
    HTTPNotFound,
)

from ..conf import loadConfig
from ..dtype import dbr_time
from ..util import WorkerLoop
from .. import (getArchive, MatchMode, __file__ as topfile)

_log = logging.getLogger(__name__)

testdata = (Path(__file__).parent / 'testdata.pb').read_bytes()

class AIOTest(type):
    """Wraps any test*() coroutine methods to be run by self.loop
    """
    def __new__(klass, name, bases, classdict):
        for name, mem in classdict.items():
            if name.startswith('test') and asyncio.iscoroutinefunction(mem):
                @wraps(mem)
                def _inloop(self, mem=mem):
                    self.worker(asyncio.wait_for(mem(self), timeout=self.timeout))
                classdict[name] = _inloop

        return type.__new__(klass, name, bases, classdict)

class DummyServer(metaclass=AIOTest):
    timeout = 15.0

    def setUp(self):
        super().setUp()
        self.worker = WorkerLoop(timeout=self.timeout, debug=True)
        self.worker(self.setUpServer())

    async def setUpServer(self):
        server_info = {
            'identity': 'dummy',
            'version': 'Archiver Appliance Version DUMMY',
        }
        async def getApplianceInfo(req):
            return json_response(server_info)

        all_pvs = [
            'test1',
            'test2',
            'other',
            'LN-AM{RadMon:1}DoseRate-I',
        ]
        async def getAllPVs(req):
            expr = re.compile(req.query.getone("regex"))
            pvs = [pv for pv in all_pvs if expr.match(pv) is not None]
            _log.debug("getAllPVs(%r) -> %s", expr.pattern, pvs)
            return json_response(pvs)

        async def getData_raw(req):
            pv = req.query.getone('pv')
            T0, T1 = req.query.getone('from'), req.query.getone('to')
            _log.debug('getData.raw(%r, %r, %r)', pv, T0, T1)
            if pv!='LN-AM{RadMon:1}DoseRate-I' and pv!='caplotbinning_4(LN-AM{RadMon:1}DoseRate-I)':
                raise HTTPNotFound(reason="No Data")
            return Response(body=testdata, content_type='foo/bar')

        self.app = Application()
        self.app.add_routes([
            http_get('/mgmt/bpl/getApplianceInfo', getApplianceInfo),
            http_get('/mgmt/bpl/getAllPVs', getAllPVs),
            http_get('/retrieval/data/getData.raw', getData_raw),
        ])

        self.runner = AppRunner(self.app)
        await self.runner.setup()
        self.site = TCPSite(self.runner, '127.0.0.1', 0)
        await self.site.start()

        host, port = self.site._server.sockets[0].getsockname()[:2]

        self.conf = loadConfig(paths=[])
        self.conf['host'] = 'localhost'
        self.conf['port'] = str(port)

        server_info.update({
            'retrievalURL': f'http://localhost:{port}/retrieval/bpl',
            'clusterInetPort': f'localhost:{port}',
            'etlURL': f'http://localhost:{port}/etl/bpl',
            'mgmtURL': f'http://localhost:{port}/mgmt/bpl',
            'dataRetrievalURL': f'http://localhost:{port}/retrieval'
        })

    async def tearDownServer(self):
        await self.runner.cleanup()

    def tearDown(self):
        self.worker(self.tearDownServer())
        self.worker.close()
        super().tearDown()

class TestAPI(DummyServer, unittest.TestCase):
    async def test_search(self):
        async with (await getArchive(self.conf)) as arch:
            for match, pat, exp in [
                (MatchMode.Regex, 'nope', set()),
                (MatchMode.Regex, 'test', {'test1', 'test2'}),
                (MatchMode.Regex, 'test.*', {'test1', 'test2'}),
                (MatchMode.Wildcard, 'test?', {'test1', 'test2'}),
                (MatchMode.Exact, 'test1', {'test1'}),
                (MatchMode.Regex, 'test1', {'test1'}),
                (MatchMode.Wildcard, 'test1', {'test1'}),
            ]:
                ret = await arch.search(pattern=pat, match=match)
                self.assertSetEqual(set(ret), exp, msg=pat)

    async def test_fetchraw(self):
        async with (await getArchive(self.conf)) as arch:
            val, meta = await arch.raw('LN-AM{RadMon:1}DoseRate-I',
                                       T0='-1h', Tend='now')

        assert_equal(val,
            [[ 0.03],[ 2.17],[ 0.45],[-0.15],[-0.31],[-0.21], [-0.14],[-0.08],[-0.02],[ 0.04],[ 0.02],
             [ 0.  ],[ 2.18],[ 0.44],[-0.14],[-0.32],[-0.26],[-0.21],[-0.14],[-0.09],[-0.03],[ 0.03]])

        assert_equal(meta,
                     np.asarray([(1423234604, 887015782, 0, 0), (1423248954, 139922833, 0, 0),
              (1423248955, 140245250, 0, 0), (1423248956, 140024882, 0, 0),
              (1423248957, 140228286, 0, 0), (1423248961, 145268115, 0, 0),
              (1423248963, 145419813, 0, 0), (1423248965, 145170191, 0, 0),
              (1423248969, 145384148, 0, 0), (1423249758, 541449008, 0, 0),
              (1423250956, 140990782, 0, 0),
              (1423250956, 0, 3904, 0), (1423263362, 434265082, 0, 0),
              (1423263363, 429269655, 0, 0), (1423263364, 434134740, 0, 0),
              (1423263365, 434277492, 0, 0), (1423263368, 434441414, 0, 0),
              (1423263369, 434220574, 0, 0), (1423263371, 434272868, 0, 0),
              (1423263373, 434366836, 0, 0), (1423263377, 439388932, 0, 0),
              (1423263404, 449503115, 0, 0)], dtype=dbr_time))

# real end-to-end test of CLI.
# everything except the setuptools generated entry point scripts
class TestCLI(DummyServer, unittest.TestCase):
    maxDiff = 16*1024
    async def runCLI(self, name, *args):
        if sys.version_info<(3,8):
            # until 3.8, asyncio.create_subprocess_exec() only works for default loop/main thread
            raise unittest.SkipTest('cf. https://bugs.python.org/issue35621')

        env = os.environ.copy()
        # ensure our code is reachable after changing to temp dir
        env['PYTHONPATH'] = ''.join([str(Path(topfile).parent.parent), os.pathsep, env.get('PYTHONPATH', '')])

        with TemporaryDirectory() as tdir, TemporaryFile("r+") as out:
            (Path(tdir) / "aaclient.conf").write_text(f'''
[DEFAULT]
host = localhost
port = {self.conf['port']}
''')

            A = ('-m', 'aaclient.cmd.'+name) + args
            print("Running", A, tdir, env['PYTHONPATH'])
            P = await asyncio.create_subprocess_exec(sys.executable, *A,
                                                     stdout=out, cwd=tdir, env=env)
            try:
                await asyncio.wait_for(P.wait(), self.timeout)
            except:
                P.kill()
                raise

            out.seek(0)
            return P.returncode, out.read()

    async def test_aagrep_none(self):
        code, out = await self.runCLI("grep", '--verbose', "--exact", "nosuchpv")
        self.assertEqual(code, 1)
        self.assertEqual(out, '')

    async def test_aagrep_one(self):
        code, out = await self.runCLI("grep", '--verbose', "--exact", "test1")
        self.assertEqual(code, 0)
        self.assertEqual(out, 'test1\n')

    async def test_aagrep_wild(self):
        code, out = await self.runCLI("grep", '--verbose', "--wildcard", "test?")
        self.assertEqual(code, 0)
        self.assertEqual(out, 'test1\ntest2\n')

    async def test_aagrep_re(self):
        code, out = await self.runCLI("grep", '--verbose', "--regexp", "test[12]")
        self.assertEqual(code, 0)
        self.assertEqual(out, 'test1\ntest2\n')

    async def test_aaget(self):
        # dummy server ignore time range
        code, out = await self.runCLI("get", '--verbose', "--utc", "-s=-1h", "-e", "now", "LN-AM{RadMon:1}DoseRate-I")
        self.assertEqual(code, 0)
        self.assertEqual(out, '''
02-06 14:56:44.887016 LN-AM{RadMon:1}DoseRate-I 0.03
02-06 18:55:54.139923 LN-AM{RadMon:1}DoseRate-I 2.17
02-06 18:55:55.140245 LN-AM{RadMon:1}DoseRate-I 0.45
02-06 18:55:56.140025 LN-AM{RadMon:1}DoseRate-I -0.15
02-06 18:55:57.140228 LN-AM{RadMon:1}DoseRate-I -0.31
02-06 18:56:01.145268 LN-AM{RadMon:1}DoseRate-I -0.21
02-06 18:56:03.145420 LN-AM{RadMon:1}DoseRate-I -0.14
02-06 18:56:05.145170 LN-AM{RadMon:1}DoseRate-I -0.08
02-06 18:56:09.145384 LN-AM{RadMon:1}DoseRate-I -0.02
02-06 19:09:18.541449 LN-AM{RadMon:1}DoseRate-I 0.04
02-06 19:29:16.140991 LN-AM{RadMon:1}DoseRate-I 0.02
02-06 19:29:16.000000 LN-AM{RadMon:1}DoseRate-I 0.0 DISCONNECT 0
02-06 22:56:02.434265 LN-AM{RadMon:1}DoseRate-I 2.18
02-06 22:56:03.429270 LN-AM{RadMon:1}DoseRate-I 0.44
02-06 22:56:04.434135 LN-AM{RadMon:1}DoseRate-I -0.14
02-06 22:56:05.434278 LN-AM{RadMon:1}DoseRate-I -0.32
02-06 22:56:08.434441 LN-AM{RadMon:1}DoseRate-I -0.26
02-06 22:56:09.434221 LN-AM{RadMon:1}DoseRate-I -0.21
02-06 22:56:11.434273 LN-AM{RadMon:1}DoseRate-I -0.14
02-06 22:56:13.434367 LN-AM{RadMon:1}DoseRate-I -0.09
02-06 22:56:17.439389 LN-AM{RadMon:1}DoseRate-I -0.03
02-06 22:56:44.449503 LN-AM{RadMon:1}DoseRate-I 0.03
'''.lstrip())

    async def test_aah5(self):
        try:
            import h5py
        except ImportError:
            raise unittest.SkipTest('h5py not installed')

        with TemporaryDirectory() as outdir:
            outfile = Path(outdir) / "out.h5"

            code, out = await self.runCLI("h5", '--verbose', "-s=-1h", "-e", "now", str(outfile)+':/tst/grp', "LN-AM{RadMon:1}DoseRate-I")
            self.assertEqual(code, 0)

            from h5py import File
            with File(outfile, 'r') as F:
                G = F['/tst/grp/LN-AM{RadMon:1}DoseRate-I']

                self.assertEqual(G['value'].shape, (22,1))
                self.assertEqual(G['meta'].shape, (22,))
