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

"""generic informational commands"""

import pypickupbot
from pypickupbot.modable import SimpleModuleFactory
from pypickupbot.irc import COMMAND

class InfoPlugin:
    """The plugin"""

    def source(self, call, args):
        """!source
        
        Tells where one can find the source of this bot."""
        call.reply(_("My source can be found at %s .") % pypickupbot.url)

    def version(self, call, args):
        """!version

        Tells the bot's version"""
        call.reply(_("I run %s %s")%(pypickupbot.name, pypickupbot.version))

    commands = {
        'source': (source, 0),
        'version': (version, 0),
    }

info = SimpleModuleFactory(InfoPlugin)
