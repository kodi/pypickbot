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

"""Makes main channel operators bot admins"""

from pypickupbot.modable import SimpleModuleFactory

class ChanOps:
    def __init__(self, bot):
        self.chanops = set()

    def is_admin(self, user, nick):
        """Checks if the user is an op in the bot's main channel"""
        return nick in self.chanops

    def modeChanged(self, user, channel, set, modes, args):
        if channel == self.pypickupbot.channel:
            if set and 'o' in modes:
                self.chanops.add(args[0])
            elif not set and 'o' in modes:
                self.chanops.discard(args[0])

    def irc_RPL_NAMREPLY(self, prefix, params):
        if params[2] == self.pypickupbot.channel:
            for user in params[3].split():
                if user[0] == '@':
                    self.chanops.add(user[1:])

    def userLeft(self, user, channel):
        if channel == self.pypickupbot.channel:
            self.chanops.discard(user)

    def userQuit(self, user, message):
        self.chanops.discard(user)

    def userRenamed(self, oldname, newname):
        if oldname in self.chanops:
            self.chanops.remove(oldname)
            self.chanops.add(newname)

    eventhandlers = {
        'is_admin': is_admin,
        'modeChanged': modeChanged,
        'irc_RPL_NAMREPLY': irc_RPL_NAMREPLY,
        'userLeft': userLeft,
        'userQuit': userQuit,
        'userRenamed': userRenamed,
        }

chanops = SimpleModuleFactory(ChanOps)

