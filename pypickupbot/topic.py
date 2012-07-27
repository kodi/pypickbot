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

"""channel topic management"""

from twisted.internet import reactor
from pypickupbot import config

class Topic:
    """the channel's topic"""

    GRAVITY_BEGINNING = 0
    GRAVITY_NONE = 1
    GRAVITY_END = 2

    def __init__(self, bot):
        self.parts = {}
        self.num = 0
        self.update_call = None
        self.bot = bot

    def add(self, text, gravity=GRAVITY_NONE):
        """Adds something to the topic
        
        @param id: the id you will reference this as, later
        @type id: any hashable type
        @param text: the text to add
        @type text: str
        @param gravity: gravity of the added message in the topic
        @type gravity: One of GRAVITY_BEGINNING, GRAVITY_NONE or GRAVITY_END
        """
        part = TopicPart(self.num, text, gravity, self)
        self.parts[self.num] = part
        self.num += 1
        self.update()
        return part

    def _remove(self, num):
        """Removes something from the topic
        
        see L{add} for arg reference"""
        del self.parts[num]
        self.update()

    def update(self):
        """updates the channel topic"""
        if self.update_call != None and self.update_call.active():
            self.update_call.cancel()
        self.update_call = reactor.callLater(2, self._update)

    def _update(self):
        """actually updates the channel topic

        use L{update} instead"""
        self.bot.setTopic(self.bot.channel, str(self))

    def __str__(self):
        sorted_topic = {
                self.__class__.GRAVITY_BEGINNING : {},
                self.__class__.GRAVITY_NONE : {},
                self.__class__.GRAVITY_END : {},
            }
        as_list = []
        for num, part in self.parts.iteritems():
            s = str(part)
            if len(s) > 0:
                sorted_topic[part.gravity][num] = s
        for i in [self.GRAVITY_BEGINNING, self.GRAVITY_NONE, self.GRAVITY_END]:
            as_list.extend(sorted_topic[i].values())

        return config.get('Topic', 'prefix').decode('string-escape') + config.get('Topic', 'separator').decode('string-escape').join(as_list) + config.get('Topic', 'suffix').decode('string-escape')

class TopicPart:
    """part of the channel's topic"""
    def __init__(self, num, text, gravity, topic):
        self.num = num
        self.text = text
        self.gravity = gravity
        self.topic = topic

    def update(self, text, gravity=None):
        self.text = text
        if gravity != None:
            self.gravity = gravity
        self.topic.update()
        return self

    def remove(self):
        self.topic._remove(self.num)
        return self

    def __str__(self):
        return self.text

