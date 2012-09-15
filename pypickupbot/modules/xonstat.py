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
        db.runOperation("""
            CREATE TABLE IF NOT EXISTS
            xonstat_players
            (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nick        TEXT,
                playerid    INTEGER,
                create_dt   INTEGER,
                edit_dt     INTEGER
            )""")
        
        self.pickup = bot.load('pickup')

    def _get_xonstat_url(self, playerid):
        """return xontat url for specific player"""
        server = config.get("Xonstat Interface", "server").decode('string-escape')
        url = "http://" + server + "/player/" + str(playerid)
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
        player_info = self._get_xonstat_json("/player/{0}.json".format(playerid))
        #print player_info
        return player_info

    def _purge(self, keep=0):
        """used by clearPlayers and purgePlayers"""
        res = defer.gatherResults(
            db.runOperation("""
                DELETE FROM xonstat_players
                WHERE time > ?
                """, (itime() - keep,))
            )
        def onErr(failure):
            log.err(failure, "purge players, keep = {0}".format(keep))
            return failure
        res.addErrback(onErr)
        return res

    def clearPlayers(self, call, args):
        """!clearplayers
        
        Clears the registered players list completely.
        Prefer the purgeplayers command to this."""
        d = call.confirm("This will delete all registered players, continue?")
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply("Done.")
                return self._purge().addCallback(done)
            else:
                call.reply("Cancelled.")
        return d.addCallback(_confirmed)

    def purgePlayers(self, call, args):
        """!purgeplayers <keep>

        Purges the registered players list from entries recorded earlier than
        [keep] ago."""
        if len(args):
            try:
                keep = timediff_from_str(' '.join(args))
            except InvalidTimeDiffString as e:
                raise InputError(e)
        else:
            raise InputError("You need to specify a time range")
        d = call.confirm(
            "This will delete the record of all players registered later than {0}, continue?".format(str_from_timediff(keep))
            )
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply("Done.")
                self._purge(keep).addCallback(done)
            else:
                call.reply("Cancelled.")
        d.addCallback(_confirmed)

    def listplayers(self, call, args):
        d = db.runQuery("""
            SELECT nick, playerid
            FROM xonstat_players
            ORDER BY nick
            """)
        def _printResult(r):
            if len(r) < 1:
                call.reply(_("No players registered yet"))
            else:
                nick, playerid = r[0]
                call.reply(nick)
        d.addCallback(_printResult)

    def playerinfo(self, call, args):
        print args
        if len(args):
            nick = args[0]
            d = db.runQuery("""
                SELECT nick, playerid, edit_dt
                FROM xonstat_players
                WHERE nick=?
                LIMIT 1
                """, (nick,))
            def _printResult(r):
                if len(r) < 1:
                    call.reply(_("No player found")	)
                nick, playerid, edit_dt = r[0]
                
                player_info     = self._get_player_info(playerid)
                game_nick       = player_info['player']['stripped_nick']
                profile_link    = self._get_xonstat_url(playerid)
                
                elo_list = []
                for gametype,elo in player_info['elos'].items():
                    elo_list.append( _("{0}: {1}").format(gametype.upper(), round(elo,1)) )
                elo_list.sort()
                elo_display = " | ".join(elo_list)
                if len(elo_list) == 0:
                    elo_display = _("none yet")
                
                rank_list = []
                for gametype,rank in player_info['ranks'].items():
                    rank_list.append( _("{0}: {1} of {2}").format(gametype.upper(), rank[0], rank[1]) )
                rank_list.sort()
                rank_display = " | ".join(rank_list)
                if len(rank_list) == 0:
                    rank_display = _("none yet")
                
                if len(elo_list) == 0:
                    reply = config.get("Xonstat Interface", "playerinfo_noelo").decode('string-escape')%\
                        { 'nick': nick, 'gamenick': game_nick, 'profile': profile_link, }
                elif len(rank_list) == 0:
                    reply = config.get("Xonstat Interface", "playerinfo_norank").decode('string-escape')%\
                        { 'nick': nick, 'gamenick': game_nick, 'elos': elo_display, 'profile': profile_link, }
                else:
                    reply = config.get("Xonstat Interface", "playerinfo").decode('string-escape')%\
                        { 'nick': nick, 'gamenick': game_nick, 'elos': elo_display, 'ranks': rank_display, 'profile': profile_link, }
                call.reply(reply)
            d.addCallback(_printResult)

    def register(self, call, args):
        nick = call.nick
        # TODO - check if already registered
        if len(args) == 1:
            try:
                playerid = int(args[0])
            except ValueError:
                raise InputError("Player id must be an integer")
            d = db.runOperation("""
                INSERT INTO
                    xonstat_players(nick, playerid, create_dt, edit_dt)
                VALUES (:nick, :playerid, :ctime, :mtime)
                """, (nick, playerid, itime(), itime() ))
            player_info     = self._get_player_info(playerid)
            game_nick       = player_info['player']['stripped_nick']
            profile_link    = self._get_xonstat_url(playerid)
            msg = config.get('Xonstat Interface', 'registered').decode('string-escape')%\
                { 'nick': nick, 'playerid': playerid, 'gamenick': game_nick, 'profile': profile_link, }
            self.pickup.pypickupbot.msg( self.pickup.pypickupbot.channel, msg.encode('ascii') )

    def removeplayer(self, call, args):
        if len(args) == 1:
            nick = args[0]
            d = db.runOperation("""
                DELTE FROM xonstat_players
                WHERE nick=?
                """, (nick,))
        else:
           raise InputError("You need to specify one player name")

    def pickup_game_started(self, game, players, captains):
        return

    def user_renamed(self, oldname, newname):
        return

    commands = {
        'register':         (register, COMMAND.NOT_FROM_PM),
        'playerinfo':       (playerinfo, 0),
        'listplayers':      (listplayers, 0),
        'removeplayer':     (removeplayer, COMMAND.ADMIN),
        'clearplayers':     (clearPlayers, COMMAND.ADMIN),
        'purgeplayers':     (purgePlayers, COMMAND.ADMIN),
        }
    eventhandlers = {
        'pickup_game_starting':     pickup_game_started,
        'userRenamed':              user_renamed,
        }

xonstat_interface = SimpleModuleFactory(XonstatInterface)

