# pypickupbot - An ircbot that helps game players to play organized games
#               with captain-picked teams.
#     Copyright (C) 2010 pypickupbot authors
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""various stuff that should have been in another lib"""

import re
from math import ceil
from UserList import UserList
from time import time
from operator import contains
from socket import inet_pton, error as AddrError, AF_INET, AF_INET6

def waitfordeferred(func, d):
    def wrapper(*args, **kwargs):
        if d.called:
            func(*args, **kwargs)
        else:
            def argument_eater(*x,**y):
                func(*args, **kwargs)
            d.addCallback(argument_eater)
    return wrapper

out_lengths = [
    (365*24*60*60, lambda n: _n("one year", "{0} years", n).format(n)),
    (30*24*60*60, lambda n: _n("one month", "{0} months", n).format(n)),
    (7*24*60*60, lambda n: _n("one week", "{0} weeks", n).format(n)),
    (24*60*60, lambda n: _n("one day", "{0} days", n).format(n)),
    (60*60, lambda n: _n("one hour", "{0} hours", n).format(n)),
    (60, lambda n: _n("one minute", "{0} minutes", n).format(n)),
    (1, lambda n: _n("one second", "{0} seconds", n).format(n)),
    ]

def str_from_timediff(seconds, nowrap=False, future=False, ignore=59,
        minFrac=.1):
    """Turns a timestamp into something like
    1 day, 2 hours and 15 minutes"""


    left = age = int(seconds)

    timestr = ""

    for length, strFactory in out_lengths:
        if left <= ignore or left < age * minFrac:
            break
        n, left = divmod(left, length)
        if n > 0:
            if timestr and (left <= ignore or left < age * minFrac):
                timestr += _(" and ")
            elif timestr:
                timestr += ", "
            timestr += strFactory(n)

    if nowrap:
        return timestr

    if len(timestr) < 1:
        if future:
            timestr = _("very soon")
        else:
            timestr = _("about right now")
    else:
        if future:
            timestr = _("in %s") % timestr
        else:
            timestr = _("%s ago") % timestr

    return timestr

class InvalidTimeDiffString(Exception):
    pass

in_lengths = {
    'years': 60*60*24*365,
    'yrs': 60*60*24*365,
    'months': 60*60*24*30,
    'weeks': 60*60*24*7,
    'days': 60*60*24,
    'hours': 60*60,
    'hrs': 60*60,
    'minutes': 60,
    'mins': 60,
    'secs': 1,
    'seconds': 1
    }

def timediff_from_str(s):
    """Turns something like 1d2h into a timestamp
    
    Supported keywords:
     * p[ermanent]
     * y[ears] (365 days)
     * mo[nths] (30 days)
     * w[eeks]
     * d[ays]
     * h[ours]
     * m[inutes]
     * s[econds]

    @returns: A number of seconds or None for a permanent timespan
    """

    seconds = 0

    s = list(s.lower().replace(' ', '').replace(',', ''))

    def _readNumber():
        n = s[0]
        del s[0]
        if s[0] in '0123456789':
            return int(n+str(_readNumber()))
        else:
            return int(n)

    def _readLength():
        c = s[0]
        for length in in_lengths:
            if length[0] == c:
                if length == 'months' and (len(s) < 2 or s[1] != 'o'):
                    continue
                elif _eatRest(length):
                    return in_lengths[length]
        raise InvalidTimeDiffString(_("""Time length string is invalid at "%s".""") % ''.join(s))

    def _eatRest(rest):
        if not len(s) or s[0] in '0123456789':
            return True
        c = s[0]
        if rest[0] == c:
            del s[0]
            if len(rest[1:]):
                if _eatRest(rest[1:]):
                    return True
                else:
                    s.insert(0, c)
                    return False
            else:
                return True
        else:
            return False

    # Best here is to use character by character processing
    while len(s):
        c = s[0]
        if c in '0123456789':
            n = _readNumber()
            if not len(s):
                raise InvalidTimeDiffString(_("""Time length string is invalid: Number "%s" ends the string.""") % n)
            c = s[0]
        else:
            n = 1
        if c == 'p':
            # permanent ban, stop processing now
            if _eatRest('permanent'):
                return 0
            else:
                raise InvalidTimeDiffString(_(
                    """Time length string is invalid: Invalid length name."""
                ))
        elif c in 'ymwdhs':
            l = _readLength()
            seconds += n*l
        else:
            raise InvalidTimeDiffString(_("""Time length string is invalid at "%s".""") % ''.join(s))

    return seconds

irc_color = re.compile('\x03[0-9]{1,2}|\x02|\x0f')

def filter_irc_colors(s):
    return irc_color.sub('', s)

def xgroup(iter_, n):
    """Yields the contents of an iterator into groups of up to n length"""
    for i in xrange(int(ceil(len(iter_)/float(n)))):
        yield iter_[i*n:(i+1)*n]

class ListOfEverything(UserList):
    """A list that always returns True on membership testing"""

    def __contains__(self, item):
        return True

    def __eq__(self, other):
        if isinstance(other, ListOfEverything):
            return True
        return False

def itime():
    """returns time in an integer"""
    return int(time())

def in_(a, b):
    return b in a


try:
    from types import StringTypes
except ImportError:
    StringTypes = str


def is_ipv4(ipstring, family=AF_INET):
    try:
        inet_pton(family, ipstring)
        return True
    except AddrError:
        return False

def is_ipv6(ipstring):
    return is_ipv4(ipstring, AF_INET6)

