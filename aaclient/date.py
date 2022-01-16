# -*- coding: utf-8 -*-
# Copyright
#   2015 Brookhaven Science Assoc. as operator of Brookhaven National Lab.
#   2022 Michael Davidsaver
# SPDX-License-Identifier: BSD
# See LICENSE file

"""
Date string format

Parsing of absolute and relative dates and times
into datetime.datetime or datetime.timedelta instances

Supported string syntax:

  Absolute:
    "[year/]month/day hour:min[:sec[.fraction]][Z]"
    "[year-]month-day hour:min[:sec[.fraction]][Z]"
    "hour:min[:sec[.fraction]][Z]"

    When year or date is omitted, the current year or date is used.
    Zero is used when seconds or fractional sections are omitted.

  Relative:
    "now"
    "### UUU [### UUU ...]"

  where ### is a signed floating point number,
  and UUU is a unit string.

  Supported unit strings

  us
  ms
  s, sec, secs
  m, min, mins
  h, hrs, hours
  d, days
  w, week, weeks

  eg: "-1.4 week 2 hours"
"""

import re
from datetime import datetime, timedelta, timezone

__all__ = (
    "makeTime",
    "makeTimeInterval",
    "isoString",
)

_tupats = (
    # Match [[Y/]M.D ]H:M[:S[.F]][Z]
    re.compile(r'''
        \s*
        (?:
            (?: (?P<year>\d+) / )? (?P<month>\d+) / (?P<day>\d+)
            [\sT]+
        )?
        (?P<hour>\d+) : (?P<minute>\d+) (?: : (?P<second>\d+) (?P<frac>\.\d+)? )?
        \s*
        (?P<tz>[zZ])?
    ''', re.VERBOSE),
    # Match [[Y-]M-D ]H:M[:S[.F]][Z]
    re.compile(r'''
        \s*
        (?:
            (?: (?P<year>\d+) - )? (?P<month>\d+) - (?P<day>\d+)
            [\sT]+
        )?
        (?P<hour>\d+) : (?P<minute>\d+) (?: : (?P<second>\d+) (?P<frac>\.\d+)? )?
        \s*
        (?P<tz>[zZ])?
    ''', re.VERBOSE),
)

# short hand and conversions for interval specifications
_units={
    # map human unit to timedelta ctor argument and multiplier
    'us':('microseconds',1),
    'ms':('microseconds',1000),
    's':('seconds',1),
    'sec':('seconds',1),
    'secs':('seconds',1),
    'm':('minutes',1),
    'min':('minutes',1),
    'mins':('minutes',1),
    'h':('hours',1),
    'hrs':('hours',1),
    'hours':('hours',1),
    'd':('days',1),
    'days':('days',1),
    'w':('days',7),
    'week':('days',7),
    'weeks':('days',7),
}

_tznames = {
    '': None, # implied local tz
    'z': timezone.utc,
}

class LazyNow:
    def __init__(self, now):
        assert now is None or now.tzinfo is timezone.utc, now
        self._now = now
    def __call__(self):
        now = self._now
        if self._now is None:
            self._now = now = datetime.now(timezone.utc)
        return now

def makeTime(intime, now=None):
    '''Attempt to translate 'intime' into a UTC datetime or timedelta.
    Input may be one of:

    - datetime
    - int, float - POSIX seconds
    - tuple of POSIX seconds and nanoseconds
    - string formatted as
     - "YYYY-MM-DD HH:MM:SS.FFFFFFF"
     - "YYYY/MM/DD HH:MM:SS.FFFFFFF"
     - "SSSSS.FFFF"
     - "## day ## sec"

    Date/time strings may be abbreviated by omission of the year,
    month+day, seconds and fractional.  Omissions for the date are
    filled in with the current day.  Omitted seconds and fraction are
    treated as zeros.
    '''
    now = LazyNow(now)

    try:
        if isinstance(intime, datetime):
            if intime.tzinfo is None:
                intime = intime.astimezone(timezone.utc)

            elif intime.tzinfo is not timezone.utc:
                raise NotImplementedError("Only naive (implied local) or UTC zones are currently recongnized")

            return intime

        elif isinstance(intime, tuple):
            intime = intime[0] + 1e-9*intime[1]
            return datetime.fromtimestamp(intime, timezone.utc)

        elif isinstance(intime, (int, float)):
            return datetime.fromtimestamp(float(intime), timezone.utc)

        # parse as string(-like)
        intime = str(intime).strip().lower()

        if intime=='now':
            return now()

        # try as absolute human friendly
        for pat in _tupats:
            M = pat.match(intime)
            if M is not None:
                M = M.groupdict()
                tz = _tznames[M.pop('tz') or '']
                tnow = now().astimezone(tz)

                frac = float('0'+(M.pop('frac') or '.0'))

                # remaining components are integers
                M = {k:None if v is None else int(v) for k,v in M.items()}

                # fill in some missing pieces from current day
                for attr in ('year', 'month', 'day'):
                    if M[attr] is None:
                        M[attr] = getattr(tnow, attr)
                # fill in others with zero
                if M['second'] is None:
                    M['second'] = 0

                M['microsecond'] = int(round(frac*1e6, 6))
                M['tzinfo'] = tz

                ret = datetime(**M).astimezone(timezone.utc)

                return ret

        # try as relative
        # split on space, and boundary between number and letter.
        # so "4d" and "4 d" both result in ["4", "d"]
        parts = re.split(r'\s+|(?<=[0-9.])(?=[a-z])', intime)
        if len(parts)>1: # there is at least one space
            if len(parts)%2!=0:
                raise ValueError(f"Relative date/time {intime!r} missing unit")

            M = {}
            for V, U in zip(parts[0::2], parts[1::2]):
                arg, mult = _units[U.lower()]
                M[arg] = M.get(arg, 0) + float(V)*mult

            return timedelta(**M)

        # fall back to absolute seconds
        return datetime.fromtimestamp(float(intime), timezone.utc)

    except:
        raise ValueError(f"Unable to process {intime!r} into time")

def isoString(dt):
    """Convert a (local) datetime object to a ISO 8601 UTC string representation
    as understood by AA

    eg. 2014-04-10T16:27:37.767454Z
    """
    assert dt.tzinfo is timezone.utc, dt
    return dt.strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def makeTimeInterval(start=None, end=None, now=None):
    """Take two (possibly relative) times and return two absolute
    times.

    *start* and *end* may be in any format accepted by makeTime().
    """
    assert now is None or now.tzinfo is timezone.utc, now
    if now is None:
        now=datetime.now(timezone.utc)
    if end is None:
        end=now
    if start is None:
        start=now

    start, end = makeTime(start, now), makeTime(end, now)

    rstart=isinstance(start, timedelta)
    rend=isinstance(end, timedelta)

    if rstart and rend:
        # -2 hours : -1 hours
        # both referenced to current time
        start=now+start
        end=now+end

    elif rstart:
        # -2 hours : 12:01
        # start relative to end
        start=end+start

    elif rend:
        if end >= timedelta(0):
            # 12:01 : 15 min
            # end relative to start
            end=start+end

        else:
            # 12:01 : -5 hours
            # end relative to current time
            end=now+end

    if start>end:
        start, end = end, start

    return (start, end)
