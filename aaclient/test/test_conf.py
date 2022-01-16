# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

from pathlib import Path
import unittest
from tempfile import TemporaryDirectory

from .. import conf

class TestConf(unittest.TestCase):
    def test_empty(self):
        with TemporaryDirectory() as T:
            F = Path(T) / 'test.conf'
            F.write_text('''
[myappl]
host = myhost
''')

            S = conf.loadConfig('myappl', paths=[F])

        self.assertEqual(S['url'], 'http://myhost:17665/mgmt/bpl/getApplianceInfo')
        self.assertEqual(S['urltype'], '.appl')
