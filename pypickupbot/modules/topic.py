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

"""Topic management commands"""

import re

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot.misc import filter_irc_colors
from pypickupbot import topic
from pypickupbot.irc import COMMAND
from pypickupbot import config
from pypickupbot import db

class TopicMgt:
    motd = []
    motd_str = []

    def joinedHomeChannel(self):
        """when home channel joined, add motd to topic"""
        d = db.runQuery("""
            SELECT val
            FROM meta
            WHERE key="motd" """)
        self.current_topic = None
        self.motd = []
        self.motd_str = []
        def _setTopic(r):
            if len(r):
                self.motd_from_str(r[0][0])
                self.setmotd()
            else:
                db.runOperation("""
                    INSERT INTO
                    meta(key, val)
                    VALUES("motd", "")
                """)
        d.addCallback(_setTopic)

    def setmotd(self):
        if len(self.motd) < len(self.motd_str):
            self.motd.append(self.pypickupbot.topic.add("", topic.Topic.GRAVITY_END))
            self.setmotd()
        elif len(self.motd) > len(self.motd_str):
            self.motd[-1].remove()
            del self.motd[-1]
            self.setmotd()
        else:
            for i in range(len(self.motd)):
                self.motd[i].update(self.motd_str[i])

    def motd_from_str(self, s):
        sep = config.get('Topic', 'separator').decode('string-escape')
        self.motd_str = re.split(
            '%s|%s' % (
                re.escape(sep),
                re.escape(filter_irc_colors(sep))
            ), s)

    def motdCmd(self, call, args):
        """!motd [...|--]]
        
        Sets the message of the day in the channel topic.
        !motd -- will make it empty"""

        if not args:
            call.reply(config.getescaped('Topic', 'separator').join(self.motd_str))
            return

        if len(args) == 1 and args[0] == '--':
            self.motd_str = []
        else:
            self.motd_from_str(' '.join(args))
            db.runOperation("""
                UPDATE meta
                SET val=?
                WHERE key="motd"
            """, (' '.join(args),))
        self.setmotd()

    commands = {
        'motd': (motdCmd, COMMAND.ADMIN),
        }

    eventhandlers = {
        'joinedHomeChannel': joinedHomeChannel
        }

topic_mgt = SimpleModuleFactory(TopicMgt)
