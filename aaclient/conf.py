# Copyright 2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

import os
from configparser import ConfigParser

__all__ = (
    'loadConfig',
)

def loadConfig(name = 'DEFAULT', paths=None):
    if paths is None:
        paths = [
            '/etc/aaclient.conf',
            os.path.expanduser('~/.config/aaclient.conf'),
            'aaclient.conf'
        ]

    P = ConfigParser()
    P['DEFAULT'] = {
        'url':'http://%(host)s:%(port)s/mgmt/bpl/getApplianceInfo',
        'urltype':'.appl',
        'port':'17665',
        'defaultcount':'1000',
        'maxquery':'30',
        'chunksize':str(256*2**10),
        'starttime':'-1h',
        'endtime':'now',
    }
    P.read(paths)
    return P[name]
