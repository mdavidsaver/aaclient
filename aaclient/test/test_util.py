# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import unittest

from .. import util

class TestWild(unittest.TestCase):
    def test_ok(self):
        for inp, exp in [
                (r"hello", r"hello"),
                (r"hello.", r"hello\."),
                (r"he?lo.", r"he.lo\."),
                (r"he?lo. wor\?d", r"he.lo\.\ wor\?d"),
                (r"hel*w\*rld", r"hel.*w\*rld"),
            ]:
            out = util.wild2re(inp)
            self.assertEqual(exp, out, msg=inp)
