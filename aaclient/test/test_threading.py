# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import asyncio
import unittest
import concurrent.futures as confut

from numpy.testing import assert_equal

from ..util import WorkerLoop
from ..threading import getArchive
from .test_aa import DummyServer

class TestWorkerLoop(unittest.TestCase):
    timeout = 1.0

    def test_start_stop(self):
        with WorkerLoop(timeout=self.timeout, debug=True):
            pass

    def test_work(self):
        with WorkerLoop(timeout=self.timeout, debug=True) as W:
            async def fortytwo():
                return 42
            self.assertEqual(42, W(fortytwo()))

    def test_cancel(self):
        with WorkerLoop(timeout=self.timeout, debug=True) as W:
            async def slow():
                await asyncio.sleep(1000)
            CF = W.call(slow())
            self.assertFalse(CF.done())
            self.assertTrue(CF.cancel())
            self.assertTrue(CF.done())
            with self.assertRaises(confut.CancelledError):
                CF.result()

class TestAPI(DummyServer, unittest.TestCase):
    timeout = 5.0
    def test_api(self):
        with getArchive(self.conf, timeout=self.timeout) as arch:
            self.assertSetEqual({'test1', 'test2'},
                                set(arch.search("test")))

            V, M = arch.raw('LN-AM{RadMon:1}DoseRate-I',
                            T0='-1h', Tend='now')
            assert_equal(V.shape, [22,1])

            V, M = arch.plot('LN-AM{RadMon:1}DoseRate-I',
                            T0='-1h', Tend='now', count=1000)
            assert_equal(V.shape, [22,1])

            arch._consolidate = False
            parts = [V.shape for V,M in arch.raw_iter('LN-AM{RadMon:1}DoseRate-I',
                                                        T0='-1h', Tend='now')]

            self.assertListEqual(parts, [(22,1)])
