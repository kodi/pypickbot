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

"""Command-line launcher"""

import sys

from twisted.internet import reactor
from twisted.internet.ssl import ClientContextFactory
from twisted.python import log
from twisted.python import usage

from pypickupbot import config
from pypickupbot.irc import IrcBotFactory
from pypickupbot import db

class Options(usage.Options):
    
    optFlags = [
        ['debug', 'd', 'Enable debug output'],
    ]
    optParameters = [
        ['config', 'c', None, "What config directory to use."],
        ['db', 'D', None, "What sqlite3 database to use."],
    ]

    def opt_version(self):
        from pypickupbot import name, version, url
        print("{0} {1} {2}".format(name, version, url))
        sys.exit(0)

def from_commandline():
    """launches the bot
    
    called by the launch script in top directory"""

    options = Options()

    try:
        options.parseOptions()
    except usage.UsageError as errortext:
        print '%s: %s' % (sys.argv[0], errortext)
        print '%s: Try --help for usage details.' % (sys.argv[0])
        sys.exit(1)
    
    log.startLogging(sys.stdout)

    config.parse_init_configs(options['config'])

    if options['debug']:
        log.msg("Forced debugging output on")
        config.debug = True
    if config.debug:
        log.msg("Debugging...")

    db.DBs.load_db(options['config'], options['db'])

    factory = IrcBotFactory()
    host = config.get('Server', 'host')
    port = config.getint('Server', 'port')

    if config.getboolean('Server', 'ssl'):
        through = "SSL"
        reactor.connectSSL(host, port, IrcBotFactory(), ClientContextFactory())
    else:
        through = "TCP"
        reactor.connectTCP(host, port, IrcBotFactory())
    log.msg(_("Connecting to {host}:{port} through {through}").format(
        host=host, port=port, through=through
        ))

    reactor.run()

