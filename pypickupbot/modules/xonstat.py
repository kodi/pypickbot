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
        print response.status, json_data
        return json_data

    def _get_player_info(self, playerid):
        player_info = self._get_xonstat_json("/player/{0}.json".format(playerid))
        print player_info
        return player_info

    def _get_game_info(self, gameid):
        game_info = self._get_xonstat_json("/game/{0}.json".format(gameid))
        return game_info

    def _purge(self, keep=0):
        """used by clearPlayers and purgePlayers"""
        res = defer.gatherResults([
            db.runOperation("""
                DELETE FROM """ + table + """
                WHERE time < ?
                """, (itime() - keep,))
            for table in ['xonstat_players']
            ])
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
                
                call.reply(_("{0} is player {1} : {2}").format(nick, game_nick, profile_link))
            d.addCallback(_printResult)

    def register(self, call, args):
        if len(args) == 2:
            nick = args[0]
            try:
                playerid = int(args[1])
            except ValueError:
                raise InputError("Player id must be an integer")
            d = db.runOperation("""
                INSERT INTO
                    xonstat_players(nick, playerid, create_dt, edit_dt)
                VALUES (:nick, :playerid, :time, :time)
                """, (nick, playerid, itime()))

    def pickup_game_started(self, game, players, captains):
        return

    commands = {
        'register':         (register, 0),
        'playerinfo':       (playerinfo, 0),
        'listplayers':      (listplayers, 0),
        'clearplayers':     (clearPlayers, COMMAND.ADMIN),
        'purgeplayers':     (purgePlayers, COMMAND.ADMIN),
        }
    eventhandlers = {
        'pickup_game_starting': pickup_game_started,
        }

xonstat_interface = SimpleModuleFactory(XonstatInterface)

