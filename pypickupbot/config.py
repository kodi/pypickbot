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

import os.path
import re

from ConfigParser import SafeConfigParser as CfgParser, NoSectionError, NoOptionError

from pypickupbot.misc import timediff_from_str

defaults = {
    }

dir = []

init_configs = [
    'init.cfg',
    'saved.cfg',
    ]

configs = [
    'config.cfg',
    'saved.cfg',
    ]

_parser = CfgParser(defaults)

debug = False

def parse_init_configs(dir_=None):
    _parser.readfp(open(os.path.join(os.path.dirname(__file__), 'defaults.cfg')))
    if dir_ != None:
        dir.append(dir_)
    if dir == []:
        _parser.read(init_configs)
    else:
        _parser.readfp((open(os.path.join(dir[0], 'init.cfg'))))

    debug = getboolean('Bot', 'debug')

def parse_configs():
    if dir == []:
        _parser.read(configs)
    else:
        _parser.readfp((open(os.path.join(dir[0], 'config.cfg'))))


defaults = _parser.defaults
sections = _parser.sections
add_section = _parser.add_section
has_section = _parser.has_section
options = _parser.options
has_option = _parser.has_option
get = _parser.get
getint = _parser.getint
getfloat = _parser.getfloat
getboolean = _parser.getboolean
items = _parser.items
set = _parser.set
remove_option = _parser.remove_option

def getescaped(section, option):
    return get(section, option).decode('string-escape')

def getlist(section, option):
    o = []
    if _parser.has_option(section, option+'[]'):
        count = _parser.getint(section, option+'[]')

        for i in range(count):
            o.append(_parser.get(section, option+'['+str(i)+']'))
    else:
        s = get(section, option)
        if ',' in s:
            o = re.split('(?:, *)', s)
        else:
            o = re.split(' +', s)
        if not o:
            raise ValueError
        if len(o) == 1 and o[0] == '':
            o = []

    try:
        plus = getlist(section, option+'+')
        for item in plus:
            if item not in o:
                o.append(item)
    except (NoSectionError, NoOptionError):
        pass

    try:
        minus = getlist(section, option+'-')
        for item in minus:
            if item in o:
                o.remove(item)
    except (NoSectionError, NoOptionError):
        pass

    return o

def getdict(section, option):
    return dict((
        i.split(':', 1)
        for i in getlist(section,option)
        ))

def getduration(section, option):
    s = _parser.get(section, option)
    return timediff_from_str(s)

