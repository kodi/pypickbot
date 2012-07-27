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

"""Authenticates with Q"""

from twisted.python import log
from twisted.internet import defer

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot import config

class QAuth:
    def signedOn(self):
        user = config.get('Q Auth', 'username')
        password = config.get('Q Auth', 'password')

        self.pypickupbot.sendLine("AUTH %s %s" % (user, password))

        self.deferred = defer.Deferred()

    def noticed(self, user, target, message):
        if target == self.pypickupbot.nickname \
                and user == config.get('Q Auth', 'Q username'):
            if message == \
                "You are now logged in as %s."\
                 % config.get('Q Auth', 'username'):
                self.deferred.callback(True)
            elif message == \
                "Username or password incorrect.":
                self.deferred.callback(True)
            else:
                log.err("Unknown message from Q: %s" % message)
                self.deferred.callback(True)

    eventhandlers = {
        'signedOn': signedOn,
        'noticed': noticed,
        }

q_auth = SimpleModuleFactory(QAuth)
