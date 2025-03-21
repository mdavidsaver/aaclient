# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

from pathlib import Path
import unittest

import numpy as np
from numpy.testing import assert_equal

from .. import _ext, dtype

data_dir = Path(__file__).parent
testdata = (data_dir / 'testdata.pb').read_bytes()


class TestXCode(unittest.TestCase):
    def test_escape(self):
        for E, U, R in [
            # escaped, escaped, remaining
            (b'', [], b''),
            (b'\n', [b''], b''),
            (b'hello', [], b'hello'),
            (b'hello\n', [b'hello'], b''),
            (b'hello\nworld', [b'hello'], b'world'),
            (b'\x1b\x01\n\x1b\x02\n\x1b\x03\n', [b'\x1b', b'\n', b'\r'], b''),
            (b'q\x1b\x01q\nq\x1b\x02q\nq\x1b\x03q\n', [b'q\x1bq', b'q\nq', b'q\rq'], b''),
            ]:

            self.assertEqual((U,R), _ext.split(E))
            self.assertEqual(E, _ext.join(U)+R)

    def test_bad_escape(self):
        for E in [
            b'\x1b\n',
            b'xxx\x1b\n',
            b'\x1b\x1b\n',
            b'hello \x1bworld\n',
            ]:
            self.assertRaises(ValueError, _ext.split, E)

class TestEncode(unittest.TestCase):
    def setUp(self):
        self.td, rem = _ext.split(testdata)
        self.assertEqual(rem, b'')

    def test_PayloadInfo(self):
        I = _ext.decode_PayloadInfo(self.td[0])
        self.assertDictEqual(I, {
            'type': int(dtype.PayloadType.SCALAR_DOUBLE),
            'pvname': b'LN-AM{RadMon:1}DoseRate-I',
            'year': 2014,
            'elementCount': 1,
            'headers': [(b'EGU', b'mR/h'), (b'PREC',  b'2')],
            })

        B = _ext.encode_PayloadInfo(I)
        self.assertEqual(self.td[0], B)

    def test_sample(self):
        lines = _ext.encode_samples(dtype.PayloadType.SCALAR_DOUBLE, [
            {"val":0.03, "sec":1423234604-1420070400, "ns":887015782, "sevr":0, "status":0},
        ])
        self.assertListEqual(lines, self.td[9:10])

class DecodeTester:
    input = testdata
    """Verify that testdata is decoded as expected, both when
    process()'d all at once, and one byte at a time.
    """
    def assertOutputEqual(self, lhs, rhs):
        for i,((LV,LM), (RV, RM)) in enumerate(zip(lhs, rhs)):
            LV = np.asarray(LV)
            RV = np.asarray(RV)
            LM = np.asarray(LM, dtype=dtype.dbr_time)
            RM = np.asarray(RM, dtype=dtype.dbr_time)
            assert_equal(LV, RV)
            assert_equal(LM, RM)
        print(rhs)
        self.assertEqual(len(lhs), len(rhs), (lhs, rhs))

    def test_full(self):
        D = _ext.StreamDecoder(threshold=self.threshold, consolidate=self.consolidate)

        self.assertTrue(D.process(self.input, last=True))

        self.assertOutputEqual(self.expected, D.output)

    def test_bytebybyte(self):
        D = _ext.StreamDecoder(threshold=self.threshold, consolidate=self.consolidate)

        N=len(self.input)
        for i in range(N):
            inp = self.input[i:(i+1)]
            last = i+1==N
            nl = inp==b'\n'
            try:
                self.assertEqual(last or nl, D.process(inp, last=last), msg=(i, last, inp))
            except AssertionError:
                raise
            except:
                raise AssertionError((i, last, inp))

        self.assertOutputEqual(self.expected, D.output)

class TestDecodeRaw(unittest.TestCase, DecodeTester):
    threshold = 100 # too large to matter
    consolidate = False
    expected = [
            ([[ 0.03],[ 2.17],[ 0.45],[-0.15],[-0.31],[-0.21], [-0.14],[-0.08],[-0.02],[ 0.04],[ 0.02]],
             [(1423234604, 887015782, 0, 0), (1423248954, 139922833, 0, 0),
              (1423248955, 140245250, 0, 0), (1423248956, 140024882, 0, 0),
              (1423248957, 140228286, 0, 0), (1423248961, 145268115, 0, 0),
              (1423248963, 145419813, 0, 0), (1423248965, 145170191, 0, 0),
              (1423248969, 145384148, 0, 0), (1423249758, 541449008, 0, 0),
              (1423250956, 140990782, 0, 0)]
            ),
            ([[ 0.  ],[ 2.18],[ 0.44],[-0.14],[-0.32],[-0.26],[-0.21],[-0.14],[-0.09],[-0.03],[ 0.03]],
             [(1423250956, 0, 3904, 0), (1423263362, 434265082, 0, 0),
              (1423263363, 429269655, 0, 0), (1423263364, 434134740, 0, 0),
              (1423263365, 434277492, 0, 0), (1423263368, 434441414, 0, 0),
              (1423263369, 434220574, 0, 0), (1423263371, 434272868, 0, 0),
              (1423263373, 434366836, 0, 0), (1423263377, 439388932, 0, 0),
              (1423263404, 449503115, 0, 0)]
            ),
        ]

class TestDecodeSplit(unittest.TestCase, DecodeTester):
    threshold = 6 # split each block in two
    consolidate = False
    expected = [
            ([[ 0.03],[ 2.17],[ 0.45],[-0.15],[-0.31],[-0.21]],
             [(1423234604, 887015782, 0, 0), (1423248954, 139922833, 0, 0),
              (1423248955, 140245250, 0, 0), (1423248956, 140024882, 0, 0),
              (1423248957, 140228286, 0, 0), (1423248961, 145268115, 0, 0)]
            ),
            ([[-0.14],[-0.08],[-0.02],[ 0.04],[ 0.02]],
             [(1423248963, 145419813, 0, 0), (1423248965, 145170191, 0, 0),
              (1423248969, 145384148, 0, 0), (1423249758, 541449008, 0, 0),
              (1423250956, 140990782, 0, 0)]
            ),
            ([[ 0.  ],[ 2.18],[ 0.44],[-0.14],[-0.32],[-0.26]],
             [(1423250956, 0, 3904, 0), (1423263362, 434265082, 0, 0),
              (1423263363, 429269655, 0, 0), (1423263364, 434134740, 0, 0),
              (1423263365, 434277492, 0, 0), (1423263368, 434441414, 0, 0)]
            ),
            ([[-0.21],[-0.14],[-0.09],[-0.03],[ 0.03]],
             [(1423263369, 434220574, 0, 0), (1423263371, 434272868, 0, 0),
              (1423263373, 434366836, 0, 0), (1423263377, 439388932, 0, 0),
              (1423263404, 449503115, 0, 0)]
            ),
        ]

class TestDecodeJoin(unittest.TestCase, DecodeTester):
    threshold = 100 # too large to matter
    consolidate = True
    expected = [
            ([[ 0.03],[ 2.17],[ 0.45],[-0.15],[-0.31],[-0.21], [-0.14],[-0.08],[-0.02],[ 0.04],[ 0.02],
              [ 0.  ],[ 2.18],[ 0.44],[-0.14],[-0.32],[-0.26],[-0.21],[-0.14],[-0.09],[-0.03],[ 0.03]],
             [(1423234604, 887015782, 0, 0), (1423248954, 139922833, 0, 0),
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
              (1423263404, 449503115, 0, 0)]
            ),
        ]

# 01-13 19:07:07.630240 ext:2:RH-I 37.0
# 01-14 11:52:57.066158 ext:2:RH-I 34.0
# 01-14 12:15:27.092548 ext:2:RH-I 31.0
# 01-14 13:32:27.081810 ext:2:RH-I 32.0 INVALID 9
# 01-14 13:37:07.112121 ext:2:RH-I 32.0
# 01-14 13:43:17.198643 ext:2:RH-I 32.0 INVALID 9
# 01-14 13:43:47.136166 ext:2:RH-I 33.0
# 01-14 14:21:16.871574 ext:2:RH-I 34.0
# 01-14 21:16:16.956306 ext:2:RH-I 37.0
# 01-15 03:23:46.492364 ext:2:RH-I 40.0
# 01-15 07:06:36.370090 ext:2:RH-I 39.0 INVALID 9
# 12-31 16:00:00.000000 ext:2:RH-I 0.0 DISCONNECT 0
# 01-15 16:32:39.853402 ext:2:RH-I 39.0 INVALID 9

class TestDisconn(unittest.TestCase, DecodeTester):
    input = (data_dir / 'test_RH.pb').read_bytes()
    threshold = 6 # split each block in two
    consolidate = False
    expected = [
        ([[37.], [34.], [31.], [32.], [32.], [32.]],
         [(1736824027, 630240554, 0, 0), (1736884377,  66158141, 0, 0),
          (1736885727,  92547883, 0, 0), (1736890347,  81810589, 3, 9),
          (1736890627, 112120816, 0, 0), (1736890997, 198643196, 3, 9)]),
        ([[33.], [34.]],
         [(1736891027, 136165894, 0, 0), (1736893276, 871574215, 0, 0)]),
        ([[37.], [40.], [39.]],
         [(1736918176, 956306539, 0, 0), (1736940226, 492364266, 0, 0),
          (1736953596, 370090287, 3, 9)]),
        ([[39.]],
         [(1736987559, 853402206,    3, 9)]),
    ]
