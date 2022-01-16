# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import unittest
from datetime import datetime, timedelta, timezone

from .. import date

class TestMakeTime(unittest.TestCase):
    def setUp(self):
        self.unow = datetime.now(timezone.utc)
        self.lnow = datetime.fromtimestamp(self.unow.timestamp())

    def test_passthrough(self):
        self.assertIs(self.unow, date.makeTime(self.unow, self.unow))
        self.assertIs(self.unow, date.makeTime('now', self.unow))

    def test_loc(self):
        self.assertEqual(self.unow, date.makeTime(self.lnow, self.unow))

    def test_rel(self):
        for inp, exp in [
            ("0 s", timedelta()),
            ("0s", timedelta()),
            ("1d 1s", timedelta(days=1, seconds=1)),
            ("1d -1s", timedelta(seconds=60*60*24-1)),
            ("1 ms", timedelta(milliseconds=1)),
            ("0.5 ms", timedelta(microseconds=500)),
            ("-1.5 h", timedelta(seconds=-60*90)),
        ]:
            out = date.makeTime(inp, self.unow)
            self.assertEqual(exp, out)

    def test_sec(self):
        self.assertEqual(self.unow, date.makeTime(str(self.unow.timestamp()), self.unow))

    def test_tuple(self):
        t = date.makeTime((1642362501, 492563730), self.unow)
        self.assertEqual(t, datetime(2022, 1, 16, 19, 48, 21, 492564, tzinfo=timezone.utc))

    def test_bad(self):
        for inp in [
            "",
            "s",
            "1d 1",
            "1d s",
            "s1d",
        ]:
            self.assertRaises(ValueError, date.makeTime, inp, self.unow)

class TestParseAbs(unittest.TestCase):
    def setUp(self):
        self.unow = datetime.now(timezone.utc)
        self.lnow = datetime.fromtimestamp(self.unow.timestamp())

    def test_utc(self):
        for inp, exp in [
            ('%Y/%m/%d %H:%M:%S.%fZ', self.unow),
            ('%Y-%m-%d %H:%M:%S.%fZ', self.unow),
            ('%Y/%m/%d %H:%M:%SZ', self.unow.replace(microsecond=0)),
            ('%Y-%m-%d %H:%M:%SZ', self.unow.replace(microsecond=0)),
            ('%m-%d %H:%MZ', self.unow.replace(second=0, microsecond=0)),
            ('%m/%d %H:%MZ', self.unow.replace(second=0, microsecond=0)),
            ('%H:%MZ', self.unow.replace(second=0, microsecond=0)),
            ('%H:%MZ', self.unow.replace(second=0, microsecond=0)),
        ]:
            out = date.makeTime(self.unow.strftime(inp), self.unow)
            self.assertEqual(out, exp)

    def test_local(self):
        for inp, exp in [
            ('%Y/%m/%d %H:%M:%S.%f', self.lnow),
            ('%Y-%m-%d %H:%M:%S.%f', self.lnow),
            ('%Y/%m/%d %H:%M:%S', self.lnow.replace(microsecond=0)),
            ('%Y-%m-%d %H:%M:%S', self.lnow.replace(microsecond=0)),
            ('%m-%d %H:%M', self.lnow.replace(second=0, microsecond=0)),
            ('%m/%d %H:%M', self.lnow.replace(second=0, microsecond=0)),
            ('%H:%M', self.lnow.replace(second=0, microsecond=0)),
            ('%H:%M', self.lnow.replace(second=0, microsecond=0)),
        ]:
            out = date.makeTime(self.lnow.strftime(inp), self.unow)
            assert self.lnow.tzinfo is None, self.lnow
            exp = datetime.fromtimestamp(exp.timestamp(), timezone.utc)
            self.assertEqual(out, exp)

    def test_bad(self):
        for inp in [
            '1/14',
            '2022-1/14 1:1',
        ]:
            self.assertRaises(ValueError, date.makeTime, inp, self.unow)

class TestMakeInterval(unittest.TestCase):
    def setUp(self):
        self.unow = datetime.now(timezone.utc)
        self.lnow = datetime.fromtimestamp(self.unow.timestamp())

    def test_ok(self):
        for A, B, S, E in [
            ('now', 'now', self.unow, self.unow),
            ('now', '1m', self.unow, self.unow+timedelta(minutes=1)),
            ('1m', 'now', self.unow, self.unow+timedelta(minutes=1)),
            ('now', '-1m', self.unow+timedelta(minutes=-1), self.unow),
            ('-1m', 'now', self.unow+timedelta(minutes=-1), self.unow),
            ('-2m', '-1m', self.unow+timedelta(minutes=-2), self.unow+timedelta(minutes=-1)),
        ]:
            X, Y = date.makeTimeInterval(A, B, self.unow)

            self.assertEqual(S, X)
            self.assertEqual(E, Y)

class TestISO(unittest.TestCase):
    def setUp(self):
        self.unow = datetime.now(timezone.utc)

    def test_format(self):
        now = 1642363905.9422555 # Sun Jan 16 12:11:45 2022 PST

        self.assertEqual(date.isoString(date.makeTime(now, self.unow)),
                         '2022-01-16T20:11:45.942255Z')
