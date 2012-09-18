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

"""the ircbot itself, with understanding of commands etc"""

import re
from time import time

from twisted.internet import protocol, defer
from twisted.words.protocols import irc
from twisted.internet import reactor
from twisted.python import log
from twisted.python.failure import Failure
import ConfigParser

from pypickupbot import i18n
from pypickupbot import config
from pypickupbot.modable import Modable
from pypickupbot.topic import Topic
from pypickupbot.misc import itime

class COMMAND:
    def __init__(self): raise NotImplementedError

    NOT_FROM_CHANNEL = 1 << 0
    NOT_FROM_PM = 1 << 1
    ON_MESSAGE = 1 << 2
    ADMIN = 1 << 3

class InputError(Exception):
    pass

class IrcBot(irc.IRCClient, Modable):
    """The bot itself.
    
    @ivar commands: the bot's commands
    @type commands: {'command_name': ( func(L{LineProcessor}, list(args)), flags ) }
    """
    modable_name = 'pypickupbot'
    _extend = {
        'commands': Modable.EXTEND_DICT,
        'eventhandlers': Modable.EXTEND_DICT_LIST
        }

    lineRate = 1

    def _get_nickname(self):
        return self.factory.nickname
    nickname = property(_get_nickname)

    def __init__(self):
        self.modules = {}
        self.commands = {}
        self.eventhandlers = {
            'privmsg': [self.privmsg_],
            'joined': [self.joined_],
            'joinedHomeChannel':  [self.joinedHomeChannel],
            'irc_JOIN': [self.irc_JOIN_],
            'irc_PART': [self.irc_PART_],
            'irc_QUIT': [self.irc_QUIT_],
            'irc_KICK': [self.irc_KICK_],
            'irc_RPL_WELCOME': [self.welcome_],
        }
        self.fetching_lists={}
        self.channel = None
        self.setTopic = self.topic
        self.topic = None
        try:
            self.password = config.get('Server', 'password')
        except ConfigParser.NoOptionError:
            self.password = None
        try:
            self.username = config.get('Server', 'username')
        except ConfigParser.NoOptionError:
            self.username = None
        try:
            self.realname = config.get('Server', 'realname')
        except ConfigParser.NoOptionError:
            self.realname = None

        self.channelpws = config.getdict('Server', 'channel passwords')

    def signedOn(self):
        """called when the bot connects: joins channels"""
        self.prompts = {'PM':{}}
        self.more_buffer = {}
        self.channel = self.factory.channels[0]

        self.preload_modules()
        self.load_modules_config()
        config.parse_configs()
        self.load_modules()

        d = self.fire('signedOn')
        def _joinChannels(*args, **kwargs):
            self.joinChannels()
        d.addCallback(_joinChannels)

    def joinChannels(self):
        """called when all is good to join channels"""
        log.msg("Joining channels {0}".format(self.factory.channels))
        for channel in self.factory.channels:
            key = self.channelpws.get(channel, None)
            self.join(channel, key)

    def joinedHomeChannel(self):
        self.topic = Topic(self)

    def joined_(self, channel):
        FetchedList.get_users(self, channel).get()
        self.prompts[channel] = {}
        if channel == self.channel:
            self.fire('joinedHomeChannel')

    def privmsg_(self, user, channel, message):
        """when we receive a message"""
        log.callWithContext(
            {'system': user},
            LineProcessor, self, user, channel, message)

    def irc_JOIN_(self, prefix, params):
        nick = prefix.split('!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.fire('joined', channel)
        else:
            self.fire('userJoined', prefix, channel)

    def irc_PART_(self, prefix, params):
        nick = prefix.split('!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.fire('left', channel)
        else:
            self.fire('userLeft', prefix, channel)

    def irc_QUIT_(self, prefix, params):
        message = params[-1]
        self.fire('userQuit', prefix, message)

    def irc_KICK_(self, prefix, params):
        kicker = prefix
        channel = params[0]
        kicked = params[1]
        message = params[-1]

        if kicked == self.nickname:
            self.fire('kickedFrom', channel, kicker, message)
        else:
            d = FetchedList.get_users(self, channel).get()
            def _fireEvent(userlist):
                for nick, ident, host, flags in userlist:
                    if nick == kicked:
                        self.fire('userKicked', 
                            '%s!%s@%s' % (nick, ident, host),
                            channel, kicker, message)
            d.addCallback(_fireEvent)

    def fire(self, event, *args, **kwargs):
        func = kwargs.pop('fire_event_func', all)
        if config.debug:
            log.msg("Event %s fired with args %s, kwargs %s" % (event, args, kwargs))

        dl = []

        if event in self.eventhandlers:
            for callback in self.eventhandlers[event]:
                dl.append(defer.maybeDeferred(callback, *args, **kwargs))

        d = defer.DeferredList(dl)

        def _gotResults(l):
            if l:
                l_ = zip(*l)[1]
            else:
                l_ = []
            return func(l_)

        return d.addCallback(_gotResults)

    def is_admin(self, user, nick):
        return self.fire('is_admin', user, nick, fire_event_func=any)

    def welcome_(self, prefix, params):
        """As twisted's version of this is broken and completely ignores the
        CORRECT nickname given by the server, here's a proper version"""
        self._registered = True
        self.nickname = params[0]
        log.msg(_("Connected as {0}").format(self.nickname))
        self.signedOn()

    def cmsg(self, message):
        """shorthand for sending channel messages"""
        return self.msg(self.channel, message)

    def fetch_list(self, cmd, *args, **kwargs):
        if cmd not in self.fetching_lists:
            self.fetching_lists[cmd] = \
                FetchedList(self, cmd, *args, **kwargs)
        return self.fetching_lists[cmd]

    import_events = ['created', 'yourHost', 'myInfo', 'luserClient',
        'bounce', 'isupport', 'luserChannels', 'luserOp', 'luserMe',
        'privmsg', 'joined', 'left', 'noticed', 'modeChanged', 'pong',
        'kickedFrom', 'nickChanged', 'action', 'topicUpdated', 'userRenamed',
        'receivedMOTD',
        'irc_JOIN', 'irc_KICK', 'irc_PART', 'irc_QUIT',
        'irc_RPL_WHOREPLY', 'irc_RPL_ENDOFWHO',
        'irc_unknown', 'irc_RPL_NAMREPLY', 'irc_RPL_ENDOFNAMES',
        'irc_RPL_BANLIST', 'irc_RPL_ENDOFBANLIST',
        'irc_RPL_WELCOME']
    @classmethod
    def do_import_events(cls):
        def make_func(eventname):
            def func(self, *args, **kwargs):
                self.fire(eventname, *args, **kwargs)
            return func
        for evt in cls.import_events:
            setattr(cls, evt, make_func(evt))
IrcBot.do_import_events()

class IrcBotFactory(protocol.ClientFactory):
    protocol = IrcBot

    def __init__(self):
        self.channels = config.getlist('Server', 'channels')
        self.nickname = config.get('Bot', 'nickname')

    def clientConnectionLost(self, connector, reason):
        delay = config.getint('Bot', 'reconnect delay')
        log.err("Connection lost (%s), reconnecting in %d seconds." %(reason, delay))
        reactor.callLater(delay, connector.connect)

    def clientConnectionFailed(self, connector, reason):
        delay = config.getint('Bot', 'connect retry delay')
        log.err("Could not connect (%s), trying again in %d seconds." %(reason, delay))
        reactor.callLater(delay, connector.connect)

class FetchedList:
    """utility class to read lists like banlists or userlist"""

    def __init__(
            self, bot, cmd, line, end, update=None, other=None,
            check_line=lambda prefix, x, contents: [x],
            check_end=lambda prefix, x, contents: True,
            check_update=lambda prefix, x, contents: [x],
            check_other=lambda name, prefix, x, contents: ([x], [])
            ):
        if other == None:
            other = []

        self.bot = bot

        self.cmd = cmd
        self.line = line
        self.end = end
        self.update = update
        self.check_line = check_line
        self.check_end = check_end
        self.check_update = check_update
        self.check_other = check_other

        self.fetching = False
        self.contents = None
        self.deferred = None

        for func, event in \
                [
                    (self._line, line),
                    (self._end, end),
                    (self._update, update),
                ] + [
                    (self._make_other_wrapper(event), event)
                    for event in other
                ]:
            if not event:
                continue
            if event not in bot.eventhandlers:
                bot.eventhandlers[event] = []
            bot.eventhandlers[event].append(func)

    def get(self, refresh=False):
        if not self.fetching and (refresh or self.contents == None):
            return self._refetch()
        elif self.fetching:
            return self._give_current_deferred()
        else:
            return defer.succeed(self.contents)
    
    def _give_current_deferred(self):
        d = defer.Deferred()
        def _cb(result):
            d.callback(result)
            return result
        self.deferred.addCallback(_cb)
        return d

    def _refetch(self):
        self.fetching = True
        self.contents = []
        self.deferred = defer.Deferred()

        self.bot.sendLine(self.cmd)

        return self._give_current_deferred()

    def _line(self, *args):
        if not self.fetching:
            return

        items = self.check_line(args, self.contents)

        if items:
            self.contents.extend(items)

    def _end(self, *args):
        if not self.fetching:
            return

        end = self.check_end(args, self.contents)

        if not end:
            return

        if end != True:
            self.contents.extend(end)

        self.fetching = False

        self.deferred.callback(self.contents)
        
        self._fire_update()

    def _update(self, *args):
        if self.fetching:
            return
        r = self.check_update(args, self.contents)

        if not r:
            return

        add, remove = r

        self.contents.extend(add)
        for to_remove in remove:
            self.contents.remove(to_remove)

        if add or remove:
            self._fire_update()

    def _make_other_wrapper(self, event):
        def _wrapper(*args, **kwargs):
            if self.fetching:
                return
            self._other(event, *args, **kwargs)
        return _wrapper

    def _other(self, event, *args):
        r = self.check_other(event, args, self.contents)
        if not r:
            return
        add, remove = r


        self.contents.extend(add)
        for to_remove in remove:
            self.contents.remove(to_remove)

        self._fire_update()

    def _fire_update(self):
        self.bot.fire('FetchedList %s updated' % self.cmd)

    @classmethod
    def get_users(cls, bot, channel):

        def _check_line(args, contents):
            me, channel_, ident, host, server, nick, flags_, hops = \
                tuple(args[1])

            flags = []

            if '@' in flags_:
                flags.append('o')

            if '+' in flags_:
                flags.append('v')

            if channel_.lower() == channel.lower():
                return [(nick, ident, host, flags)]

        def _check_end(args, contents):
            me, channel_, message = tuple(args[1])
            if channel_.lower() == channel.lower():
                return True

        def _check_other(event, args, contents):
            if event == 'modeChanged':
                author, channel_, set, modes, args = args

                if channel_ != channel:
                    return

                for mode, arg in zip(modes, args):
                    if mode in 'ov':
                        for nick, ident, host, flags in contents:
                            if nick == arg:
                                flags_ = flags[:]
                                if set:
                                    flags_.append(mode)
                                else:
                                    if mode in flags:
                                        flags_.remove(mode)
                                return (
                                        [(nick, ident, host, flags_)],
                                        [(nick, ident, host, flags)]
                                    )

            elif event == 'userRenamed':
                oldnick, newnick = args

                for nick, ident, host, flags in contents:
                    if nick == oldnick:
                        return (
                                [(newnick, ident, host, flags)],
                                [(oldnick, ident, host, flags)]
                            )

            elif event in ('userLeft', 'userKicked', 'userQuit', 'userJoined'):
                user = args[0]

                channel_ = args[1]

                nick = user.split('!')[0]
                ident = user.split('!')[1].split('@')[0]
                host = user.split('@')[1]

                if event != 'userQuit' and channel_ != channel:
                    return

                if event == 'userJoined':
                    return ([(nick, ident, host, [])], [])
                else:
                    for nick_, ident_, host_, flags in contents:
                        if nick_ == nick:
                            return ([], [(nick, ident, host, flags)])

        return bot.fetch_list(
            cmd='WHO %s' % channel,
            line='irc_RPL_WHOREPLY', check_line=_check_line,
            end='irc_RPL_ENDOFWHO', check_end=_check_end,
            other=['userJoined', 'userLeft', 'userKicked',
                'userQuit', 'userRenamed', 'modeChanged'],
            check_other=_check_other)

    @classmethod
    def get_bans(cls, bot, channel):

        def _check_line(args, contents):
            me, channel_, mask, author, start = args[1]
            
            if channel_ != channel:
                return

            return [(mask, author, start)]

        def _check_end(args, contents):
            me, channel_, message = args[1]

            if channel_ != channel:
                return

            return True

        def _check_update(args, contents):
            author, channel_, set, modes, args = args

            if channel_ != channel:
                return

            admin = author.split('!')[0]

            changes = []
            for mode, arg in zip(modes, args):
                if mode == 'b':
                    if set:
                        t = itime()
                    else:
                        t = None
                        for mask_, admin_, t_ in contents:
                            if mask_ == arg:
                                t = t_
                                admin = admin_
                        if t == None:
                            continue
                    changes.append((arg, admin, t))

            if set:
                return (changes, [])
            else:
                return ([], changes)

        return bot.fetch_list(
            cmd='MODE %s +b' %channel,
            line='irc_RPL_BANLIST', check_line=_check_line,
            end='irc_RPL_ENDOFBANLIST', check_end=_check_end,
            update='modeChanged', check_update=_check_update
            )

    @classmethod
    def has_flag(cls, bot, channel, user, flag):
        nick = user.split('!')[0]

        def _gotList(l):
            for nick_, ident, host, flags in l:
                if nick_ == nick:
                    if flag in flags:
                        return True
                    else:
                        return False

        return cls.get_users(bot, channel).get().addCallback(_gotList)

    @classmethod
    def bot_has_op(cls, bot):
        return cls.has_flag(bot, bot.channel, bot.nickname, 'o')

class LineProcessor:
    CONTEXT_PRIVATE = 0
    CONTEXT_COMMAND = 1
    CONTEXT_MENTION = 2
    CONTEXT_NORMAL = 3
    def __init__(self, bot, user, channel, message):
        self.bot = bot
        self.user = user
        self.nick = user.split('!',1)[0]
        self.channel = channel
        command = str()

        if channel[0]=='#':
            if message.startswith(config.get('Bot', 'command prefix')):
                command = message[len(config.get('Bot', 'command prefix')):]
                self.context = self.CONTEXT_COMMAND
            else:
                m = re.match( '^'+re.escape(self.bot.nickname)+'[^A-Za-z0-9 ]\W*(.*)', message )
                if m and config.getboolean('Bot', 'allow mentions'):
                    command = m.group(1)
                    self.context = self.CONTEXT_MENTION
                else:
                    # chanmsg
                    return
        elif channel == self.bot.nickname:
            command = message
            self.context = self.CONTEXT_PRIVATE
            self.channel = 'PM'
        else:
            return

        self.args = command.split()
        self.cmd = self.args.pop(0).lower()

        if self.cmd in ['yes', 'no']:
            self._handle_confirm_reply()
            return

        if self.cmd == 'more':
            log.msg(_("{0} asked for more"))
            self._handleMore()
            return

        if self.cmd not in self.bot.commands:
            log.msg(_("{0} attempted to use unknown command {1}.").format(self.nick, self.cmd))
            if config.getboolean('Bot', 'warn on unknown command'):
                self.reply(_("Unknown command %s.") % self.cmd)
            return

        flags = self.bot.commands[self.cmd][1]
        can_run = []
        if flags & COMMAND.ADMIN:
            def _knowIs_admin(is_admin):
                if not is_admin:
                    log.msg(_("{0} attempted to use admin command {1}.").format(self.nick, self.cmd))
                    raise InputError(_("Command %s is only available to admins.") % self.cmd)
                else:
                    return True
            can_run.append(
                self.bot.is_admin(self.user, self.nick)\
                    .addCallback(_knowIs_admin)
                )

        if self.context == self.CONTEXT_PRIVATE and flags & COMMAND.NOT_FROM_PM:
            log.msg(_("{0} attempted to use command {1} in a PM.").format(self.nick, self.cmd))
            can_run.append(defer.fail(InputError(
                _("Command %s cannot be used in private.") % self.cmd)))
        else:
            can_run.append(defer.succeed(True))

        if self.context == self.CONTEXT_COMMAND and flags & COMMAND.NOT_FROM_CHANNEL:
            log.msg(_("{0} attempted to use command {1} in a channel.").format(self.nick, self.cmd))
            can_run.append(defer.fail(InputError(
                _("Command {0} cannot be used in public.").format(self.cmd))))
        else:
            can_run.append(defer.succeed(True))

        def _canRun(true):
            log.msg(message)
            try:
                d = log.callWithContext({'system': 'pypickupbot %s %s'%(self.channel,self.cmd)}, self.bot.commands[self.cmd][0], self, self.args)
                if isinstance(d, defer.Deferred):
                    d.addErrback(_catchInputError).addErrback(_catchInternalError)
            except InputError as e:
                self.reply(str(e))
            except Exception as e:
                self.reply(_("Internal error."))
                log.err()

        def _catchInputError(f):
            t = f.trap(InputError)
            self.reply(str(f.value))
        
        def _catchInternalError(f):
            f.trap(Exception)
            self.reply(_("Internal error."))
            f.printTraceback()

        defer.DeferredList(can_run, fireOnOneErrback=True, consumeErrors=True)\
            .addCallbacks(_canRun, _catchInputError).addErrback(_catchInternalError)

    def printError(self, f):
        print('in printerror')
        e = f.trap(Exception)
        if e == InputError:
            self.reply(str(f.getErrorMessage()))
        else:
            self.reply(_("Internal error."))
        

    def reply(self, msg, split=" "):
        """Reply to whoever sent this"""
        if len("PRIVMSG %s %s\n"%(self.nick, msg)) > 255:
            self._split_reply(msg, split, 0)
            return
        log.msg('Replying to %s: %s'%(self.nick, msg))
        self.bot.notice(self.nick, str(msg))

    def _split_reply(self, msg, split, times):
        """Splits a reply into multiple messages.
        
        @arg splitpoint: what pattern is it best to split at?"""
        times += 1
        added_len = len("PRIVMSG %s \n"%self.nick)
        if len(msg) + added_len <= 255:
            self.reply(msg)
        else:
            more_suffix = ""
            if times == config.getint("Bot", "max reply splits before waiting"):
                more_suffix = split \
                    + _("Reply is too long, use \x02%(prefix)smore\x02 to continue reading.")\
                    % {'prefix':config.get('Bot', 'command prefix')}
            added_len += len(more_suffix)
            m = re.match("^(?P<send>.{0,%d})%s(?P<rest>.*?)$"\
                % (255-added_len, re.escape(split)), msg)
            if not m:
                # If we can't split conveniently, cut straight in
                self.reply(msg[:255-added_len]+more_suffix)
                rest = msg[255-added_len:]
            else:
                self.reply(m.group('send')+more_suffix)
                rest = m.group('rest')
            if len(more_suffix):
                t = time()
                self.bot.more_buffer[self.nick] = (rest, t)
                reactor.callLater(60, self._dropMoreBuffer, t)
            else:
                self._split_reply(rest, split, times)

    def _dropMoreBuffer(self, t):
        if self.nick in self.bot.more_buffer and self.bot.more_buffer[self.nick][1] == t:
            del self.bot.more_buffer[self.nick]

    def _handleMore(self):
        if self.nick in self.bot.more_buffer:
            if self.bot.more_buffer[self.nick][1] + 5 > time():
                self.reply(_("Please wait between \x02%(prefix)smore\x02 calls.") \
                    % {'prefix':config.get('Bot', 'command prefix')})
            else:
                self.reply(self.bot.more_buffer[self.nick][0])
        else:
            self.reply(_("There's nothing more."))

    def _removePrompt(self, t):
        if self.nick in self.bot.prompts[self.channel] and self.bot.prompts[self.channel][self.nick][1] == t:
            self.bot.prompts[self.channel][self.nick][0].callback(
                self.bot.prompts[self.channel][self.nick][2]
                )
            del self.bot.prompts[self.channel][self.nick]

    def confirm(self, msg, wait=60, split=" ", assume=False):
        """Prompts caller for confirmation.

        @arg wait: time in seconds to wait for confirmation until it is assumed to be dismissed.
        
        @returns deferred fired with True/False"""
        if self.nick in self.bot.prompts[self.channel]:
            self._removePrompt(self.bot.prompts[self.channel][self.nick][1])
        self.reply(
            msg + " " + _("Reply with \x02%(prefix)syes\x02 or \x02%(prefix)sno\x02.")
            % {'prefix':config.get('Bot', 'command prefix')}, split)
        t = time()
        d = defer.Deferred()
        self.bot.prompts[self.channel][self.nick] = (d, t, assume)
        reactor.callLater(60, self._removePrompt, t)
        return d

    def _handle_confirm_reply(self):
        if self.nick in self.bot.prompts[self.channel]:
            if self.cmd == 'yes':
                ret = True
                log.msg(_("Got confirmation from {0}").format(self.nick))
            else:
                ret = False
                log.msg(_("Got deny from {0}").format(self.nick))
            self.bot.prompts[self.channel][self.nick][0].callback(ret)
            del self.bot.prompts[self.channel][self.nick]
        else:
            raise InputError(_("No confirmation was expected from you."))

def needOpped(f):
    """Denies the use of a command if the bot isn't opped"""
    def wrapper(self, call, args):
        def do_call(is_op):
            if is_op:
                return f(self, call, args)
            else:
                call.reply(_("I need to be opped to run this command."))
        FetchedList.bot_has_op(self.pypickupbot).addCallback(do_call)
    return wrapper
