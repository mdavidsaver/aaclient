# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

from enum import IntEnum

import numpy as np

try:
    from matplotlib.dates import epoch2num
except ImportError:
    def epoch2num(e):
        raise NotImplementedError("Must install matplotlib")

dbr_time = [
    ('sec', np.uint32),
    ('ns', np.uint32),
    ('severity', np.uint32),
    ('status', np.uint32),
]

class aameta(np.ndarray):
    """Augmented type for meta-data arrays.
    """
    @property
    def timestamp(self):
        """Array of timestamp as float seconds (POSIX epoch)
        """
        return self['sec'] + 1e-9*self['ns']

    @property
    def time_mpl(self):
        """Array of timestamp as float days wrt. the matplotlib epoch
        """
        return epoch2num(self.timestamp)

class PayloadType(IntEnum):
    SCALAR_STRING = 0 
    SCALAR_SHORT = 1
    SCALAR_FLOAT = 2
    SCALAR_ENUM = 3
    SCALAR_BYTE = 4
    SCALAR_INT = 5
    SCALAR_DOUBLE = 6
    WAVEFORM_STRING = 7
    WAVEFORM_SHORT = 8
    WAVEFORM_FLOAT = 9
    WAVEFORM_ENUM = 10
    WAVEFORM_BYTE = 11
    WAVEFORM_INT = 12
    WAVEFORM_DOUBLE = 13
    V4_GENERIC_BYTES = 14

pt2dt = {
    PayloadType.SCALAR_STRING: np.dtype('40c'),
    PayloadType.SCALAR_SHORT: np.dtype('i2'),
    PayloadType.SCALAR_FLOAT: np.dtype('f4'),
    PayloadType.SCALAR_ENUM: np.dtype('i2'),
    PayloadType.SCALAR_BYTE: np.dtype('i1'),
    PayloadType.SCALAR_INT: np.dtype('i4'),
    PayloadType.SCALAR_DOUBLE: np.dtype('f8'),
    PayloadType.WAVEFORM_STRING: np.dtype('40c'),
    PayloadType.WAVEFORM_SHORT: np.dtype('i2'),
    PayloadType.WAVEFORM_FLOAT: np.dtype('f4'),
    PayloadType.WAVEFORM_ENUM: np.dtype('i2'),
    PayloadType.WAVEFORM_BYTE: np.dtype('i1'),
    PayloadType.WAVEFORM_INT: np.dtype('i4'),
    PayloadType.WAVEFORM_DOUBLE: np.dtype('f8'),
    PayloadType.V4_GENERIC_BYTES: np.dtype('O'),
}
