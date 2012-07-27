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

"""ban tracker"""

from datetime import datetime
from itertools import chain
import re
import difflib
import json
from operator import contains
import traceback

from twisted.internet import defer, reactor
from twisted.internet.error import AlreadyCalled as AlreadyCalledError,\
                                    AlreadyCancelled as AlreadyCancelledError
from twisted.python import log
from zope.interface import implements

from pypickupbot.irc import COMMAND, InputError, FetchedList, needOpped
from pypickupbot import db
from pypickupbot import config
from pypickupbot.misc import (
    str_from_timediff,timediff_from_str,InvalidTimeDiffString,
    xgroup, ListOfEverything, itime, in_, is_ipv4, is_ipv6
    )
from pypickupbot.modable import SimpleModuleFactory

class Item:
    """generic class for an item in the tracker"""

    meta_names = {}
    meta_funcs = {}

    def __init__(self, tracker, meta, start=0, length=0,
            deleted=0, applied=True, id=None):
        self.tracker = tracker
        self.id = id
        self.meta = meta
        if start:
            self.start = start
        else:
            self.start = itime()
        self.length = length
        self.applied = applied
        self.deleted = deleted

    def expired(self):
        return bool(self.deleted) or (bool(self.length) and self.start + self.length < itime())

    def expiry(self):
        """Utility function to get a string like "expires in 10 minutes"."""
        if self.deleted:
            return _('lifted %s') % str_from_timediff(int(itime())-self.deleted)
        elif not self.length:
            return _('permanent')
        elif self.length + self.start < itime():
            return _('expired %s') % str_from_timediff(int(itime())-self.length-self.start)
        else:
            return _("expires %s") % str_from_timediff(self.length+self.start-int(itime()), future=True)

    def check_applied(self):
        raise NotImplementedError()

    def sync_with_self(self):
        if self.expired() == self.applied:
            if self.expired():
                d = defer.maybeDeferred(self.unapply)
            else:
                d = defer.maybeDeferred(self.apply)
            def _done(applied):
                self.applied = applied
            d.addCallback(_done)
            return self.update_db()
        else:
            return defer.succeed(self.id)

    def sync_with_real(self):
        if self.expired() == self.applied:
            if not self.expired():
                self.deleted = itime()
                self.update_db()

    def apply(self):
        raise NotImplementedError()

    def unapply(self):
        raise NotImplementedError()

    def update_db(self):
        """Updates this item's DB entry or creates it if
        self.id == None"""

        if self.id == None:
            q = """
                INSERT INTO
                tracker_%ss(meta, start, length, deleted)
                VALUES(:meta, :start, :length, :deleted)
            """
        else:
            q = """
                UPDATE tracker_%ss
                SET
                    meta = :meta,
                    start = :start,
                    length = :length,
                    deleted = :deleted
                WHERE id = :id
            """

        def _itrxn(txn):
            txn.execute(q % self.tracker.name, {
                    'meta': json.dumps(self.meta),
                    'start': self.start,
                    'length': self.length,
                    'deleted': self.deleted,
                    'id': self.id
                })
            if self.id == None:
                txn.execute("SELECT last_insert_rowid() AS id")
                return txn.fetchall()[0][0]

        def _knowId(id=None):
            if self.id == None:
                self.id = id
            return self

        return db.runInteraction(_itrxn).addCallback(_knowId)
   

    def __contains__(self, other):
        return True

    def subject(self):
        """return the subject of this item to be shown in the list"""
        return '???'

    def short_str(self):
        ret = config.getescaped('Tracker', 'list item') % {
            'id': self.id,
            'subject': self.subject(),
            'expiry': self.expiry()
            }
        return ret
    
    def long_str(self):
        ret = [self.short_str()]
        meta_names = {
                'edited_by': 'Edited by',
                'deleted_by': 'Deleted by',
                'author': 'Author'
            }
        meta_funcs = {
                'edited_by': lambda l: ', '.join(l)
            }
        meta_names.update(self.meta_names)
        meta_funcs.update(self.meta_funcs)
        for meta, val in self.meta.iteritems():
            if not val:
                continue
            ret.append(
               config.getescaped('Tracker', 'list meta') %
                    {
                        'name': meta_names.get(meta, meta),
                        'val': meta_funcs.get(meta, str)(val)
                    }
                )
        return config.getescaped('Tracker', 'list separator').join(ret)

    def __str__(self):
        if self.id == None:
            s = "{type} on {subject}(ID unknown yet)"
        else:
            s = "{type} #{id} on {subject}"
        return s.format(
            type=self.tracker.name, id=self.id, subject=self.subject())

    reverse_sort = True

    def get_cmp_key(self, *args):
        return self.id

    @classmethod
    def from_results(cls, results, tracker):
        """Turns a list of DB results into a list of me's.

        The request should look as follows::

            SELECT
            id, meta, start, length, deleted
            FROM tracker_xxxxx

        """
        return (
            cls(
                tracker=tracker,
                id=result[0],
                meta=json.loads(result[1]),
                start=result[2],
                length=result[3],
                deleted=result[4]
                )
            for result in results
        )

    @classmethod
    def from_real(cls, others, tracker):
        """Create me from an element from Tracker.retrieve_real_list"""

    @classmethod
    def from_call(cls, call, args):
        """Create me from the tracker's main command call"""
        raise NotImplementedError()

class Tracker:
    """generic class for a tracker, for instance a banlist"""

    name = NotImplemented
    version = "0.0.1"
    ItemClass = NotImplemented

    search_keys = None
    cmp_funcs = None

    def __init__(self, bot):
        if self.name == NotImplemented:
            raise NotImplementedError(__class__)

        self.pre_init(bot)

        self.last_check = 0
        self.listed = []

        def _itrxn(txn):
            txn.execute("""
                CREATE TABLE IF NOT EXISTS
                tracker_%ss
                (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    meta        TEXT,
                    start       INT,
                    length      INT,
                    deleted     INT
                )            
            """ % self.name )
            txn.execute("""
                SELECT
                id, meta, start, length, deleted
                FROM tracker_%ss
            """% self.name)
            return txn.fetchall()
        d = db.runInteraction(_itrxn)

        def _fillItems(items):
            self.listed.extend(items)
            return True

        self.dbready = d.addCallback(self.ItemClass.from_results, self).addCallback(_fillItems)

    def pre_init(self, bot):
        pass

    def joinedHomeChannel_(self):
        dl = [self.dbready]

        if callable(self.joinedHomeChannel):
            dl.append(self.joinedHomeChannel())
        
        d = defer.DeferredList(dl)

        def _refreshAppliesAndResync(l):
            self.periodic_check()
            return True
        self.ready = d.addCallback(_refreshAppliesAndResync)

    def sync(self, reallist_):
        reallist = reallist_[:]
        dl = []
        for item in sorted(self.listed,
                key=self.ItemClass.get_cmp_key,
                reverse=self.ItemClass.reverse_sort):
            d = item.check_applied(reallist)

            d0 = defer.Deferred()

            def _do_sync(applied, d0):
                for el in reallist:
                    if el in item:
                        reallist.remove(el)

                item.sync_with_real()
                item.sync_with_self()

                d0.callback(True)

            d.addCallback(_do_sync, d0)
            dl.append(d0)

        def _doneSyncing(l):
            for item in self.ItemClass.from_real(reallist, self):
                item.update_db()
                self.listed.append(item)

        return defer.DeferredList(dl).addCallback(_doneSyncing)

    def periodic_check(self):
        self.retrieve_real_list().addCallback(self.sync)
        
        try:
            self.next_check.cancel()
        except (AttributeError, AlreadyCalledError, AlreadyCancelledError):
            pass

        self.next_check = reactor.callLater(
                config.getduration(self.name.capitalize(), 'check interval'),
                self.periodic_check
            )

    def default_cmp(self, a, b):
        try:
            return a.lower() in b.lower()
        except AttributeError: # not a string
            pass

        try:
            return a in b
        except TypeError: # b not iterable
            return a == b

    def search(self, needle, keys=None, cmp_funcs=None,
            check=lambda x: True):
        listed = sorted(self.listed,
            key=self.ItemClass.get_cmp_key,
            reverse=self.ItemClass.reverse_sort)

        keys_ = None

        if keys:
            keys_ = keys

        if cmp_funcs == None:
            cmp_funcs == {}

        if 'id' not in cmp_funcs:
            cmp_funcs['id'] = lambda s, i: re.sub('^#?([0-9]+)$', r'\1', s) == str(i)

        if (not keys or 'id' in keys) and needle.startswith('#'):
            # Only search on id
            keys = keys_ = ['id']

        ret = []

        for item in listed:
            if not check(item):
                continue
            if not needle:
                ret.append(item)
                continue
            if keys == None:
                keys_ = item.meta
            for key in keys_:
                if key in item.meta or key == 'id':
                    if key == 'id':
                        if cmp_funcs['id'](needle, item.id):
                            return [item] # there is only one item with
                                          # the same id
                    else:
                        if cmp_funcs.get(key, self.default_cmp)(needle, item.meta[key]):
                            ret.append(item)
                            break
        
        return ret

    def retrieve_real_list(self):
        return defer.succeed([])

    def get_cmp_funcs(self):
        return {}

    @needOpped
    def mainCmd(self, call, args):
        """!%(name)s [#id|hostmask|user [length [reason]]]
        
        Sets a new %(name)s or edits an existing one."""
        length = None
        needle = None

        if args:
            needle = args.pop(0)
            r = self.search( needle, self.search_keys,
                self.get_cmp_funcs(),
                lambda item: not self.ItemClass.expired(item) )
        else:
            r = []

        if r:
            new = False
            if len(r) > 1:
                call.reply(
                    _("More than one match: please specify the id of the item to edit"))
                return
            else:
                item_ = r[0]

                if 'edited_by' not in item_.meta:
                    item_.meta['edited_by'] = []
                item_.meta['edited_by'].append(call.user)

                try:
                    newlen = timediff_from_str(args[0])
                except IndexError:
                    raise InputError(_("Please specify a new {type} length or reason.").format(type=self.name))
                except InvalidTimeDiffString:
                    length = item_.length
                    # assume it's a new reason for the ban
                else:
                    # apply the new length as if the ban started now without changing start time
                    length = itime() - item_.start + newlen
                    args.pop(0)

                item = defer.succeed(item_)
        else:
            new = True
            if args or needle:
                args.insert(0, needle)
                try:
                    length = timediff_from_str(args[1])
                except (InvalidTimeDiffString, IndexError):
                    # Ignore error and let subclass decide the default value for this
                    pass
                else:
                    del args[1]

            def _newItem(item):
                item.meta['author'] = call.user
                return item
            item = self.ItemClass.from_call(self, call, args)
            item.addCallback(_newItem)

        def _gotItem(item, length):
            if args and length == None:
                try:
                    length = timediff_from_str(args.pop(0))
                except InvalidTimeDiffString as e:
                    raise InputError(str(e))
            elif length == None:
                length = config.getduration(
                    self.name.capitalize(), 'default duration')
            item.length = length

            if args:
                item.meta['reason'] = ' '.join(args)

            applied = self.retrieve_real_list().addCallback(item.check_applied)
            def _applied(applied):
                if new:
                    self.listed.append(item)
                    synced = item.sync_with_self()
                else:
                    synced = item.update_db()
                def _reply(self):
                    if new:
                        call.reply(_("{item} created.").format(item=item).capitalize())
                    else:
                        call.reply(_("{item} edited.").format(item=item).capitalize())
                synced.addCallback(_reply)
            applied.addCallback(_applied)

            return item
 
        return item.addCallback(_gotItem, length)

    @needOpped
    def undoCmd(self, call, args):
        """!un%(name)s [#id|search]

        Removes the %(name)s specified by #id or search."""
        r = self.search( ' '.join(args), self.search_keys, self.get_cmp_funcs(),
            lambda item: not item.expired())

        if not r:
            raise InputError(_("No matches."))

        if len(r) > 1:
            confirm = call.confirm(
                _("%s items are going to be affected, proceed?")
                    % len(r) )
        else:
            confirm = defer.succeed(True)

        def _confirmed(confirmed):
            if not confirmed:
                call.reply(_("Cancelled."))
            else:
                for item in r:
                    item.meta['deleted_by'] = call.user
                    item.deleted = itime()
                    call.reply(_("{item} lifted.").format(item=item).capitalize())
                self.periodic_check()
        confirm.addCallback(_confirmed)

    def listCmd(self, call, args):
        """!%(name)slist [#id|search]
        
        Shows/searches the active %(name)ss list, or give detailled info
        about one %(name)s."""
        r = self.search( ' '.join(args), self.search_keys, self.get_cmp_funcs(),
            lambda item: not item.expired() or (item.deleted and item.deleted + 86400 > itime() )\
                or not item.deleted and item.start + item.length + 86400 > itime())

        if not r:
            raise InputError(_("No matches."))

        if len(r) == 1:
            call.reply(r[0].long_str(), config.getescaped('Tracker', 'list separator'))
        else:
            call.reply(
                config.getescaped('Tracker', 'list separator')\
                    .join((item.short_str() for item in r)),
                config.getescaped('Tracker', 'list separator')
                )

    def historyCmd(self, call, args):
        """!%(name)shistory [#id|search]
        
        Shows/searches the unactive %(name)ss list, or give detailled info
        about one %(name)s."""
        r = self.search( ' '.join(args), self.search_keys, self.get_cmp_funcs(),
            lambda item: item.expired() )

        if not r:
            raise InputError(_("No matches."))

        if len(r) == 1:
            call.reply(r[0].long_str(), config.getescaped('Tracker', 'list separator'))
        else:
            call.reply(
                config.getescaped('Tracker', 'list separator')\
                    .join((item.short_str() for item in r)),
                config.getescaped('Tracker', 'list separator')
                )
   

    eventhandlers = {
        'joinedHomeChannel': joinedHomeChannel_
    }

class TrackerModuleFactory(SimpleModuleFactory):
    def post_inst(self, m):
        if m.name == NotImplemented:
            raise NotImplementedError("%s lacks a name" % m.__class__)

        for cmd in 'main', 'undo', 'list', 'history':
            docstring = getattr(m, '%sCmd' % cmd).__doc__
            if docstring:
                setattr(m, '%sCmd_doc' % cmd, docstring % {'name': m.name})

        try:
            getattr(m, 'commands')
        except AttributeError:
            setattr(m, 'commands', {})

        m.commands.update(
            {
                '%s' % m.name: (m.mainCmd, COMMAND.ADMIN),
                'un%s' % m.name: (m.undoCmd, COMMAND.ADMIN),
                '%slist' % m.name: (m.listCmd, COMMAND.ADMIN),
                '%shistory' % m.name: (m.historyCmd, COMMAND.ADMIN),
            }
        )

        m.eventhandlers.update(
            {
                'joinedHomeChannel': m.joinedHomeChannel_
            }
        )

class Mask(Item):
    @staticmethod
    def find_banmask(mask):
        """Finds a new sequence of banmasks"""
        m = re.match("^(.*)!(~?)(.*)@(.*)$", mask)
        assert m
        nick, identd, ident, host = m.groups()

        if identd == '~':
            identd = ''
            ident = '*'
        nick = '*'
        return ['%s!%s%s@%s' % (nick, identd, ident, host)]

class MaskTracker(Tracker):
    """generic class for a tracker that handles IRC masks"""

    @classmethod
    def mask_to_regexp(cls, mask):
        def _recurse(s):
            try:
                if s.index('*') < s.index('?'):
                    sep = '*'
                else:
                    sep = '?'
            except ValueError:
                if '*' in s:
                    sep = '*'
                elif '?' in s:
                    sep = '?'
                else:
                    return re.escape(s)

            before, sep, after = s.partition(sep)

            if sep == '*':
                token = '.*'
            elif sep == '?':
                token = '.?'
            return re.escape(before) + token + _recurse(after)
        return _recurse(mask)
    
    @classmethod
    def cmp_masks(cls, needle, masks):
        needle_re = cls.mask_to_regexp(needle)
        for mask in masks:
            if re.search(needle_re, mask):
                return True
            if re.search(cls.mask_to_regexp(mask), needle):
                return True
        return False

banmaskRe = re.compile(r'''
    ^
    (?:
        [^@!]+
        !
        [^@!]+
        @
        [^@!]+
    |
        \$      # FreeNode-style $field:mask type of masks
        [^:]+
        :
        .*
    )
    $
    ''', re.VERBOSE)
hostmaskRe = re.compile(r'''
    ^
    (?P<nick> [^*!@]+ )
    !
    (?P<noidentd> ~? )
    (?P<ident> [^*!@]+ )
    @
    (?P<host> [^*!@]+ )
    $
    ''', re.VERBOSE)

class Ban(Mask):
    """a ban"""

    join=lambda l: ', '.join(l)

    meta_names = {
        'ban_masks': 'Ban masks',
        'seen_masks': 'Seen masks',
        'seen_nicks': 'Seen nicknames',
        'deleted_by': 'Lifted by',
        }

    meta_funcs = {
        'ban_masks': join,
        'seen_masks': join,
        'seen_nicks': join,
        }

    def subject(self):
        if 'seen_nicks' in self.meta and self.meta['seen_nicks']:
            return self.meta['seen_nicks'][0]
        elif len(self.meta['ban_masks']):
            if len(self.meta['ban_masks'][0]) < 15:
                return self.meta['ban_masks'][0]
            else:
                return "..." + self.meta['ban_masks'][0][-12:]
        else:
            return "???"

    def check_applied(self, banlist):
        if banlist:
            masklist = zip(*banlist)[0]
        else:
            masklist = []

        for mask in self.meta['ban_masks']:
            if mask not in masklist:
                self.applied = False
                break
            else:
                # Don't check this mask anymore
                del banlist[masklist.index(mask)]
        else:
            self.applied = True
        return defer.succeed(self.applied)
    
    def apply(self):
        log.msg("Applying {0}".format(self))
        def _knowOp(l):
            has_op, users = zip(*l)[1]
            if not has_op:
                log.err("Bot doesn't have operator status")
                return False

            for masks in xgroup(self.meta['ban_masks'], 3): #arbitrary number
                self.tracker.pypickupbot.sendLine("MODE %s +%s %s" % (
                    self.tracker.pypickupbot.channel,
                    'b' * len(masks),
                    str(' '.join(masks))
                    ))

            kickreason = ''
            if 'reason' in self.meta:
                kickreason += self.meta['reason']
            kickreason += '[' + self.expiry() + ']'
            for nick, ident, host, flags in users:
                if self.tracker.cmp_masks(
                    '%s!%s@%s' % (nick, ident, host),
                    self.meta['ban_masks']
                    ):
                    self.tracker.pypickupbot.sendLine(
                        "KICK %s %s :%s" % 
                        (
                            self.tracker.pypickupbot.channel,
                            nick,
                            kickreason
                        )
                        )
            return True
        return defer.DeferredList(
            [
                FetchedList.bot_has_op(self.tracker.pypickupbot),
                FetchedList.get_users(self.tracker.pypickupbot,
                                      self.tracker.pypickupbot.channel).get()
            ]
            ).addCallback(_knowOp)

    def unapply(self):
        log.msg("Unapplying {0}".format(self))
        def _knowOp(has_op):
            if not has_op:
                log.err("Bot doesn't have operator status")
                return True
            traceback.print_stack()
            for masks in xgroup(self.meta['ban_masks'], 3):
                self.tracker.pypickupbot.sendLine("MODE %s -%s %s" % (
                    self.tracker.pypickupbot.channel,
                    'b' * len(masks),
                    str(' '.join(masks))
                    ))
            return False
        return FetchedList.bot_has_op(self.tracker.pypickupbot) \
            .addCallback(_knowOp)

    def __contains__(self, other):
        return other[0] in self.meta['ban_masks']

    @classmethod
    def from_real(cls, results, tracker):
        return (
            cls(
                tracker=tracker,
                meta=
                    {
                        'ban_masks':[other[0]],
                        'author': other[1]
                    },
                start=other[2],
                length=0,
            )
            for other in results
            if other[1] != tracker.pypickupbot.nickname
        )

    @classmethod
    def from_call(cls, tracker, call, args):
        nick = None
        user = None

        if not args:
            if tracker.lastKicked and tracker.lastKickedTime + 120 > itime():
                user = tracker.lastKicked
                reason = tracker.lastKickedReason
            else:
                raise InputError(
                    _("No kick issued recently, so please specify a user or mask to ban."))
        else:
            if '$' == args[0][0]: # that's a server-custom mask
                                  # the user surely knows what they're
                                  # doing there
                user = args.pop(0)
            elif '@' not in args[0] \
            and  '!' not in args[0] \
            and  '*' not in args[0] \
            and  '?' not in args[0]:
                if is_ipv4(args[0]) or is_ipv6(args[0]):
                    user = '*!*@' + args.pop(0) # TODO ban a subnet for
                                                # ivp6 addresses
                else:
                    nick = args.pop(0)
            else:
                if  '@' not in args[0] \
                and '!' not in args[0]:
                    user = args.pop(0)+'!*@*'
                else:
                    if not banmaskRe.match(args[0]):
                        raise InputError(_("Invalid hostmask '%s'")%args[0])
                    elif hostmaskRe.match(args[0]): # full hostmask
                        user = cls.find_banmask(args.pop(0))
                    else: # already a banmask
                        user = args.pop(0)

        if user:
            user_d = defer.succeed([user])
        else:
            def _gotUserList(l):
                for nick_, ident, host, flags in l:
                    if nick == nick_:
                        user = "%s!%s@%s" % (nick_, ident, host)
                        return cls.find_banmask(user)
                else:
                    return ['%s!*@*' % nick]

            user_d = FetchedList.get_users(
                tracker.pypickupbot,
                tracker.pypickupbot.channel
                ).get().addCallback(_gotUserList)

        def _gotMasks(masks):
            def _gotUserList(userlist):
                meta = {
                        'ban_masks': masks,
                        'seen_masks': [],
                        'seen_nicks': [],
                    }

                if user:
                    meta['seen_masks'].append(user)
                if nick:
                    meta['seen_nicks'].append(nick)

                to_kick = []
                for nick_, ident, host, flags in userlist:
                    mask_ = '%s!%s@%s' % (nick_, ident, host)
                    if tracker.cmp_masks(
                        mask_,
                        masks
                        ):
                        to_kick.append(nick_)
                        if nick_ not in meta['seen_nicks']:
                            meta['seen_nicks'].append(nick_)
                        if mask_ not in meta['seen_masks']:
                            meta['seen_masks'].append(mask_)


                if tracker.pypickupbot.nickname in to_kick:
                    raise InputError(_("Ain't gonna ban myself."))
                if len(to_kick) > 1:
                    confirm = call.confirm(_("More than 1 client(%s) is affected with this ban, proceed?") % ' '.join(to_kick))
                else:
                    confirm = defer.succeed(True)
                def _confirmed(confirmed):
                    if not confirmed:
                        raise InputError(_("Cancelled."))

                    return cls(
                        tracker,
                        meta
                        )
                return confirm.addCallback(_confirmed)
            return FetchedList.get_users(
                tracker.pypickupbot,
                tracker.pypickupbot.channel
                ).get(_gotUserList).addCallback(_gotUserList)
        return user_d.addCallback(_gotMasks)


    def get_cmp_key(self, *args):
        return (not self.expired(), self.start)

class BanTracker(MaskTracker):
    """manages the channel's banlist"""
    
    name = 'ban'
    ItemClass = Ban

    def pre_init(self, bot):
        bot.extend(self, 'eventhandlers', {
                'FetchedList MODE %s +b updated' % bot.channel:
                    self.banListUpdated
            })
        self.lastKicked = None

    def joinedHomeChannel(self):
        d = FetchedList.get_bans(self.pypickupbot, self.pypickupbot.channel).get()
        return d

    def banListUpdated(self):
        self.periodic_check()

    def retrieve_real_list(self):
        return FetchedList.get_bans(
            self.pypickupbot,
            self.pypickupbot.channel).get()

    def get_cmp_funcs(self):
        return {
            'ban_masks': self.cmp_masks,
            'seen_masks': self.cmp_masks,
        }


ban = TrackerModuleFactory(BanTracker)

