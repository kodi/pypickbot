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

from time import time
from datetime import datetime
import json
import httplib

from twisted.internet import defer
from twisted.python import log

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot import db
from pypickupbot import config
from pypickupbot.irc import COMMAND, InputError
from pypickupbot.misc import str_from_timediff, timediff_from_str,\
    InvalidTimeDiffString, StringTypes, itime

class XonstatInterface:

    def __init__(self, bot):
        self.pickup = bot.load('pickup')
        self.players = {}       # nick : playerid
        self.nickchanges = {}   # newname : originalname

        def _done(args):
            self._load_from_db()
        d = db.runOperation("""
            CREATE TABLE IF NOT EXISTS
            xonstat_players
            (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nick        TEXT,
                playerid    INTEGER,
                create_dt   INTEGER
            )""")
        d.addCallback(_done)
        
    def _load_from_db(self):
        d = db.runQuery("""
            SELECT      nick, playerid, create_dt
            FROM        xonstat_players
            ORDER BY    create_dt
            """)
        self.players = {}
        def _loadPlayers(r):
            for entry in r:
                nick, playerid, create_dt = entry
                self.players[nick] = playerid
            print self.players
        d.addCallback(_loadPlayers)

    def _get_xonstat_url(self, playerid):
        """return xontat url for specific player"""
        url = config.get("Xonstat Interface", "url").decode('string-escape')
        url = url + "player/" + str(playerid)
        return url

    def _get_xonstat_json(self, request):
        server = config.get("Xonstat Interface", "server").decode('string-escape')
        try:
            http = httplib.HTTPConnection(server)
            http.connect()
            http.request("GET", request)
            response = http.getresponse()
            http.close()
        except:
            return None
        try:
            json_data = json.loads(response.read())
        except:
            json_data = {}
        return json_data

    def _get_player_info(self, playerid):
        return self._get_xonstat_json("/player/{0}.json".format(playerid))

    def _purge(self, keep=0):
        """used by clearPlayers and purgePlayers"""
        d = defer.gatherResults(
            db.runOperation("""
                DELETE FROM xonstat_players
                WHERE       create_dt < ?
                """, (itime() - keep,))
            )
        def onErr(failure):
            log.err(failure, "purge players, keep = {0}".format(keep))
            return failure
        d.addErrback(onErr)
        return d

    def clearPlayers(self, call, args):
        """!clearplayers
        
        Clears the registered players list completely.
        Prefer the purgeplayers command to this."""
        d = call.confirm("This will delete all registered players, continue?")
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply(_("Done."))
                return self._purge().addCallback(done)
            else:
                call.reply(_("Cancelled."))
        return d.addCallback(_confirmed)

    def purgePlayers(self, call, args):
        """!purgeplayers <keep>

        Purges the registered players list from entries created later than
        [keep] ago."""
        if not len(args) == 1:
            raise InputError(_("You need to specify a time range."))
        try:
            keep = timediff_from_str(' '.join(args))
        except InvalidTimeDiffString as e:
            raise InputError(e)
        d = call.confirm(
            "This will delete the record of all players registered later than {0}, continue?".format(str_from_timediff(keep))
            )
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply(_("Done."))
                self._purge(keep).addCallback(done)
            else:
                call.reply(_("Cancelled."))
        d.addCallback(_confirmed)

    def _find_player(self, nick):
        if self.players.has_key(nick):
            return self.players[nick]
        return None

    def listplayers(self, call, args):
        if len(self.players) == 0:
            call.reply(_("No players registered yet."))
            return
        reply = config.get("Xonstat Interface", "playerlist").decode('string-escape')%\
                { 'players': " ".join(self.players.keys()), 'num_players': len(self.players), }
        call.reply(reply)

    def playerinfo(self, call, args):
        if not len(args) == 1:
            raise InputError("You need to specify a player nickname.")
        
        nick = self._get_original_nick(args[0])
        playerid = self._find_player(nick)
        if not playerid:
            call.reply(_("No player named <{0}> found!").format(nick))
            return
            
        player_info     = self._get_player_info(playerid)
        game_nick       = player_info['player']['stripped_nick']
        profile_link    = self._get_xonstat_url(playerid)
            
        sep = config.get("Xonstat Interface", "playerinfo_separator").decode('string-escape')
            
        elo_list = []
        for gametype,elo in player_info['elos'].items():
            elo_list.append( _("{0}: {1}").format(gametype.upper(), round(elo,1)) )
        elo_list.sort()
        elo_display = sep.join(elo_list)
        if len(elo_list) == 0:
            elo_display = _("none yet")
        
        rank_list = []
        for gametype,rank in player_info['ranks'].items():
            rank_list.append( _("{0}: {1} of {2}").format(gametype.upper(), rank[0], rank[1]) )
        rank_list.sort()
        rank_display = sep.join(rank_list)
        if len(rank_list) == 0:
            rank_display = _("none yet")
        
        reply = config.get("Xonstat Interface", "playerinfo").decode('string-escape')%\
                { 'nick': nick, 'gamenick': game_nick, }
        if len(elo_list) > 0:
            reply += config.get("Xonstat Interface", "playerinfo_elo").decode('string-escape')%\
                { 'elos': elo_display }
        if len(rank_list) > 0:
            reply += config.get("Xonstat Interface", "playerinfo_rank").decode('string-escape')%\
                { 'ranks': rank_display, }
        reply += config.get("Xonstat Interface", "playerinfo_profile").decode('string-escape')%\
            { 'profile': profile_link, }
        call.reply(reply)

    def player_exists(self, call, args):
        nick = self._get_original_nick(args[0])
        playerid = self._find_player(nick)
        if playerid:
            reply = _("This nick is registered with player id #{0} (as \x02{1}\x02). Use \x02!playerinfo <nick>\x02 to see more details.").format(playerid, nick)
        else:
            reply = _("No player information found for <{0}>.".format(nick))
        call.reply(reply)

    def register(self, call, args):
        if not len(args) == 1:
            raise InputError(_("You must specify your Xonstat profile id to register an account."))
        
        nick = self._get_original_nick(call.nick)
        playerid = self._find_player(nick)
        if playerid:
            raise InputError(_("This nick is already registered with player id #{0} (as <{1}>) - can't continue! If you need to change your player id, please contact one of the channel operators.").format(playerid, nick))
        try:
            playerid = int(args[0])
        except ValueError:
            raise InputError(_("Player id must be an integer."))
        
        player_info     = self._get_player_info(playerid)
        profile_link    = self._get_xonstat_url(playerid)
        game_nick       = player_info['player']['stripped_nick']
        if not player_info:
            raise InputError(_("This doesn't seem to be a valid Xonstat playerid!"))
        
        d = call.confirm(_("You're about to register yourself with player id #{0} (\x02{1}\x02, Xonstat profile {1}), is this correct?").format(playerid, game_nick, profile_link))
        def _confirmed(ret):
            if ret:
                def done(*args):
                    self._load_from_db()
                    call.reply("Done.")
                    msg = config.get('Xonstat Interface', 'registered').decode('string-escape')%\
                        { 'nick': nick, 'playerid': playerid, 'gamenick': game_nick, 'profile': profile_link, }
                    self.pickup.pypickupbot.msg( self.pickup.pypickupbot.channel, msg.encode('ascii') )
                d = db.runOperation("""
                    INSERT INTO xonstat_players(nick, playerid, create_dt)
                    VALUES      (:nick, :playerid, :ctime)
                    """, (nick, playerid, itime() ))
                d.addCallback(done)
            else:
                call.reply(_("Cancelled."))
        d.addCallback(_confirmed)

    def removeplayer(self, call, args):
        if not len(args) == 1:
            raise InputError(_("You need to specify one player name."))
        nick = args[0]
        d = call.confirm(_("This will delete all entries registered to {0}, continue?").format(nick))
        def _confirmed(ret):
            if ret:
                def done(*args):
                    self._load_from_db()
                    call.reply(_("Done."))
                d = db.runOperation("""
                    DELETE FROM xonstat_players
                    WHERE       nick=?
                    """, (nick,))
                return d.addCallback(done)
            else:
                call.reply(_("Cancelled."))
        return d.addCallback(_confirmed)

    def pickup_game_started(self, game, players, captains):
        return

    def user_renamed(self, oldname, newname):
        original = self._get_original_nick(oldname)
        if newname == original:
            if self.nickchanges.has_key(oldname):
                del self.nickchanges.has_key[oldname]
        else:
            self.nickchanges[original] = newname
        print self.nickchanges

    def _get_nick(self, nick):
        if self.nickchanges.has_key(nick):
            return self.nickchanges[nick]
        return nick

    def _get_original_nick(self, nick):
        for old,new in self.nickchanges.items():
            if new == nick:
                return old
        return nick

    commands = {
        'register':         (register,      COMMAND.NOT_FROM_PM),
        'playerinfo':       (playerinfo,    0),
        'player':           (player_exists, 0),
        'listplayers':      (listplayers,   0),
        'removeplayer':     (removeplayer,  COMMAND.ADMIN),
        'clearplayers':     (clearPlayers,  COMMAND.ADMIN),
        'purgeplayers':     (purgePlayers,  COMMAND.ADMIN),
        }
    eventhandlers = {
        'pickup_game_starting':     pickup_game_started,
        'userRenamed':              user_renamed,
        }

xonstat_interface = SimpleModuleFactory(XonstatInterface)

