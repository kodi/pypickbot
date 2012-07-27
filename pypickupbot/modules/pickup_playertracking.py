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

from twisted.internet import defer
from twisted.python import log

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot import db
from pypickupbot import config
from pypickupbot.irc import COMMAND, InputError
from pypickupbot.misc import str_from_timediff, timediff_from_str,\
    InvalidTimeDiffString, StringTypes, itime

class PlayerTracking:

    def __init__(self, bot):
        db.runOperation("""
            CREATE TABLE IF NOT EXISTS
            pickup_games
            (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                game    TEXT,
                time    INTEGER,
                players TEXT,
                captains TEXT
            )""")
        db.runOperation("""
            CREATE TABLE IF NOT EXISTS
            pickup_players_games
            (
                game_id INTEGER,
                name    TEXT,
                game    TEXT,
                time    INTEGER
            )
            """)

        self.pickup = bot.load('pickup')

    def top10(self, call, args):
        """!top10 [game [game ..]]
        
        Shows who participated most in said game(s)."""
        games_ = self.pickup.get_games(call, args)
        games = [game.nick for game in games_.games]

        def _doTransaction(txn):
            params = dict(zip([str(i) for i in range(len(games))], games))
            params.update({'time': itime()-config.getduration("Pickup player tracking", "top10 spread")})
            txn.execute("""
                SELECT name FROM pickup_players_games
                WHERE
                    (""" + \
                    ' OR '.join(['game=:%d' % i for i in range(len(games))]) \
                    + """)
                    AND time>:time""", params )

            players = {}

            for (player,) in txn.fetchall():
                try:
                    players[player] += 1
                except KeyError:
                    players[player] = 1

            ordered = players.items()
            ordered.sort(None, lambda x: x[1], True)

            return ordered[:10]

        d = db.runInteraction(_doTransaction)

        def _cback(playerlist):
            o = [config.get('Pickup player tracking', 'top10 player').decode('string-escape') % {
                    'player': player,
                    'count': count,
                    }
                for player, count in playerlist]
            call.reply(
                config.get('Pickup player tracking', 'top10').decode('string-escape') % {
                    'playerlist': ', '.join(o),
                    'games': ' '.join(games)
                }, ', ')
        d.addCallback(_cback)

    def _purge(self, keep=0):
        """used by clearGames and purgeGames"""
        res = defer.gatherResults([
            db.runOperation("""
                DELETE FROM """ + table + """
                WHERE time < ?
                """, (itime() - keep,))
            for table in ['pickup_games', 'pickup_players_games']
            ])
        def onErr(failure):
            log.err(failure, "purge games, keep = {0}".format(keep))
            return failure
        res.addErrback(onErr)
        return res
                
    def clearGames(self, call, args):
        """!cleargames
        
        Clears the played games list. This does empty the top10 list.
        Prefer the purgegames command to this."""
        d = call.confirm("This will delete all recorded games, continue?")
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply("Done.")
                return self._purge().addCallback(done)
            else:
                call.reply("Cancelled.")
        return d.addCallback(_confirmed)

    def purgeGames(self, call, args):
        """!purgegames [keep]

        Purges the played games list from entries recorded earlier than
        [keep] ago. Uses !top10 spread otherwise if [keep] isn't
        provided."""
        if len(args):
            try:
                keep = timediff_from_str(' '.join(args))
            except InvalidTimeDiffString as e:
                raise InputError(e)
        else:
            keep = config.getduration("Pickup player tracking", "top10 spread")
        d = call.confirm(
            "This will delete the record of every game started earlier than {0}, continue?".format(str_from_timediff(keep))
            )
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply("Done.")
                self._purge(keep).addCallback(done)
            else:
                call.reply("Cancelled.")
        d.addCallback(_confirmed)

    def lastgame(self, call, args):
        """!lastgame [#id|game [game ..]]
        
        Shows when the last game or game given by id started and which players were in it"""
        if len(args) == 1 and args[0].startswith('#'):
            try:
                id = int(args[0][1:])
            except ValueError:
                raise InputError("Game id must be an integer")
            d = db.runQuery("""
                SELECT game, time, players, captains, id
                FROM pickup_games
                WHERE id=?
                LIMIT 1""", (id,))
        else:
            games_ = self.pickup.get_games(call, args)
            games = [game.nick for game in games_.games]
            params = dict(zip([str(i) for i in range(len(games))], games)) 
            d = db.runQuery("""
                SELECT game, time, players, captains, id
                FROM pickup_games
                WHERE """+ ' OR '.join(['game=:%d' % i for i in range(len(games))]) +"""
                ORDER BY time DESC
                LIMIT 1""", params)
        def _printResult(r):
            if len(r) < 1:
                if args and args[0].startswith('#'):
                    call.reply(_("No record for game #{0}").format(id))
                else:
                    call.reply(_("No game played yet in mode(s): {0}").format(' '.join(games)))
                return
            gamenick, gtime, players_, captains_, id_ = r[0]
            if ',' in players_:
                players = json.loads(players_)
                captains = json.loads(captains_)
            else:
                players = players_.split()
                captains = captains_.split()
            try:
                game = self.pickup.get_game(call, [gamenick])
                gamename = game.name
                teamnameFactory = game.teamname
            except InputError:
                gamename = _("Unknown(%s)") % gamenick
                teamnameFactory = lambda i: _("Team {0}").format(i + 1)

            timestr = str_from_timediff(itime()-gtime)

            if captains:
                call.reply(config.get('Pickup player tracking', 'lastgame').decode('string-escape') % \
                    {
                        'name': gamename,
                        'nick': gamenick,
                        'id': id_,
                        'when': timestr,
                        'playerlist': ', '.join(players),
                        'captainlist': ', '.join(captains)
                    })
            elif not isinstance(players[0], StringTypes):
                call.reply(config.get('Pickup player tracking', 'lastgame autopick').decode('string-escape') % \
                    {
                        'name': gamename,
                        'nick': gamenick,
                        'id': id_,
                        'when': timestr,
                        'teamslist': ', '.join([
                            config.get('Pickup messages', 'game ready autopick team').decode('string-escape')%
                            {
                                'name': teamnameFactory(i),
                                'players': ', '.join(team)
                            }
                            for i, team in enumerate(players)])
                    })
            else:
                call.reply(config.get('Pickup player tracking', 'lastgame nocaptains').decode('string-escape') % \
                    {
                        'name': gamename,
                        'nick': gamenick,
                        'id': id_,
                        'when': timestr,
                        'playerlist': ', '.join(players),
                    })
        d.addCallback(_printResult)

    def lastgames(self, call, args):
        """!lastgames [game [game ..]]

        List last games played in given modes."""
        games_ = self.pickup.get_games(call, args)
        games = [game.nick for game in games_.games]
        params = dict(zip([str(i) for i in range(len(games))], games)) 

        d = db.runQuery("""
            SELECT game, time, id
            FROM pickup_games
            WHERE """+ ' OR '.join(['game=:%d' % i for i in range(len(games))]) +"""
            ORDER BY time DESC
            LIMIT 10
        """, params)
        def _printResult(r):
            o = []
            for nick, ts, id in r:
                date = datetime.fromtimestamp(ts)
                o.append(config.get('Pickup player tracking', 'lastgames game').decode('string-escape') % {
                    'year': date.year,
                    'month': date.month,
                    'day': date.day,
                    'hour': date.hour,
                    'minutes': date.minute,
                    'nick': nick,
                    'id': id,
                })
            o.reverse()
            call.reply(config.get('Pickup player tracking', 'lastgames').decode('string-escape')%{
                'games': ', '.join(games),
                'lastgames': config.get('Pickup player tracking', 'lastgames separator').decode('string-escape').join(o)
                }, config.get('Pickup player tracking', 'lastgames separator').decode('string-escape'))
        d.addCallback(_printResult)

    def pickup_game_started(self, game, players, captains):
        def _insertGame(txn):
            txn.execute("""
                INSERT INTO
                pickup_games(game, time, players, captains)
                VALUES(:game, :time, :players, :captains)
            """,
            {
                'game': game.nick,
                'time': itime(),
                'players': json.dumps(players, separators=(',',':')),
                'captains': json.dumps(captains, separators=(',',':')),
            })

            txn.execute("SELECT last_insert_rowid() AS id")
            result = txn.fetchall()

            id_ = result[0][0]

            def _insertPlayers(playerlist):
                for player in playerlist:
                    if isinstance(player, StringTypes):
                        db.runOperation("""INSERT INTO
                            pickup_players_games(game_id, name, game, time)
                            VALUES(?, ?, ?, ?)
                        """, (id_, player, game.nick, itime()))
                    else:
                        _insertPlayers(player)
            _insertPlayers(players)
            return id_
        def _gotId(id_):
            self.pypickupbot.cmsg("Lastgame id: {0}".format(id_))
            self.pypickupbot.fire('pickup_lastgame_id', id_, game, players, captains)
        return db.runInteraction(_insertGame).addCallback(_gotId)

    commands = {
        'top10': (top10, 0),
        'lastgame': (lastgame, 0),
        'lastgames': (lastgames, 0),
        'cleargames': (clearGames, COMMAND.ADMIN),
        'purgegames': (purgeGames, COMMAND.ADMIN),
        }
    eventhandlers = {
        'pickup_game_starting': pickup_game_started,
        }

player_tracking = SimpleModuleFactory(PlayerTracking)

