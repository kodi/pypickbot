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

"""Pickup-related commands"""
from time import time
from datetime import datetime
import random
import json
import httplib
import re

from twisted.python import log

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot.irc import COMMAND, InputError, FetchedList
from pypickupbot.topic import Topic
from pypickupbot import db
from pypickupbot import config
from pypickupbot.misc import str_from_timediff, timediff_from_str,\
    InvalidTimeDiffString, StringTypes, itime

class Player:

    def __init__(self, nick, playerid = None, create_dt = None, index = None):
        self.nick           = nick
        self.playerid       = playerid
        self.create_dt      = create_dt
        self.index          = index
        self.player_info    = None

    def __str__(self):
        return "{0} (#{1})".format(self.nick, self.playerid)

    def get_xonstat_url(self):
        """return xontat url for specific player"""
        return config.get("Xonstat Interface", "url").decode('string-escape') + "player/" + str(self.playerid)

    def get_id(self):
        return self.playerid

    def _get_xonstat_json(self, request):
        server = config.get("Xonstat Interface", "server").decode('string-escape')
	data = ""
        try:
            http = httplib.HTTPConnection(server)
            http.connect()
            http.request("GET", request)
            response = http.getresponse()
            data = response.read()
            http.close()
        except:
            return {}
        json_data = json.loads(data)
        return json_data[0]  # dict embedded in a list

    def _get_player_info(self):
        if not self.player_info:
            self.player_info = self._get_xonstat_json("/player/{0}.json".format(self.playerid))
        return self.player_info

    def is_valid(self):
        self._get_player_info()
        if not self.player_info:
            return False
        if len(self.player_info) == 0:
            return False
        return True

    def _irc_colors(self, qstr, bold=False):
        _irc_colors = [ -1, 4, 9, 8, 12, 11, 13, -1, -1, -1 ]
        def _rgb_to_simple(r,g,b):
            # this was basically taken from rcon2irc.pl
            min_ = min(r,g,b)
            max_ = max(r,g,b)
            
            v = max_ / 15.0
            s = (1 - min_/max_) if max_ != min_ else 0
            
            if s < 0.2:
                return 0 if v < 0.5 else 7
                
            if max_ == min_:
                h = 0
            elif max_ == r:
                h = (60 * (g - b) / (max_ - min_)) % 360
            elif max_ == g:
                h = (60 * (b - r) / (max_ - min_)) + 120
            elif max_ == b:
                h = (60 * (r - g) / (max_ - min_)) + 240
            
            if h < 36:  
                return 1
            elif h < 80:
                return 3
            elif h < 150:
                return 2
            elif h < 200:
                return 5
            elif h < 270:
                return 4
            elif h < 330:
                return 6
            else:
                return 1

        _all_colors = re.compile(r'(\^\d|\^x[\dA-Fa-f]{3})')
        #qstr = ''.join([ x if ord(x) < 128 else '' for x in qstr ]).replace('^^', '^').replace(u'\x00', '') # strip weird characters
        parts = _all_colors.split(qstr)
        result = "\002"
        oldcolor = None
        while len(parts) > 0:
            tag = None
            txt = parts[0]
            if _all_colors.match(txt):
                tag = txt[1:]  # strip leading '^'
                if len(parts) < 2:
                    break
                txt = parts[1]
                del parts[1]
            del parts[0]
                
            if not txt or len(txt) == 0:
                # only colorcode and no real text, skip this
                continue
            
            color = 7
            if tag:
                if len(tag) == 4 and tag[0] == 'x':
                    r = int(tag[1], 16)
                    g = int(tag[2], 16)
                    b = int(tag[3], 16)
                    color = _rgb_to_simple(r,g,b)
                elif len(tag) == 1 and int(tag[0]) in range(0,10):
                    color = int(tag[0])
            color = _irc_colors[color]
            if color != oldcolor:
                if color < 0:
                    result += "\017\002"
                else:
                    result += "\003" + str(color)
            result += txt
            oldcolor = color
        result += "\017"
        return result
    
    def get_nick(self):
        try:
            nick = self._get_player_info()['player']['nick']
        except:
            nick = self.nick
        return self._irc_colors(nick, bold=True)
    
    def get_stripped_nick(self):
        return self._get_player_info()['player']['stripped_nick']

    def get_elo_dict(self):
        return self._get_player_info()['elos']

    def get_rank_dict(self):
        return self._get_player_info()['ranks']

    def get_elo(self, gametype):
        gt = self._get_gametype(gametype)
        try:
            elos = self._get_player_info()['elos']
            if elos.has_key(gt):
                return elos[gt]['elo']
        except:
            pass
        return None

    def get_rank(self, gametype):
        gt = self._get_gametype(gametype)
        try:
            ranks = self._get_player_info()['ranks']
            if ranks.has_key(gt):
                return (ranks[gt]['rank'], ranks[gt]['max_rank'])
        except:
            pass
        return (None, None)
    
    def _get_gametype(self, gamenick):
        for target,games in config.items('Xonstat Games'):
            games = [ x.strip() for x in games.decode('string-escape').split(",") ]
            if gamenick.lower() in games:
                return target.lower()
        return None    


class Team:

    def __init__(self, name, gametype):
        self.players    = []
        self.name       = name
        self.gametype   = ""
        self.elo        = 0
        self.captain    = None
        
        for target,games in config.items('Xonstat Games'):
            games = [ x.strip() for x in games.decode('string-escape').split(",") ]
            if gametype in games:
                self.gametype = target.lower()
                break

    def is_valid(self):
        return (self.gametype != None)

    def __str__(self):
        return self.name + ": " + ", ".join([ str(p) for p in self.players])

    def get_players(self):
        return self.players

    def add_player(self, player):
        self.players.append(player)
        elo = player.get_elo(self.gametype)
        if elo:
            self.elo += elo

    def remove_player(self, player):
        for p in self.players:
            if p == player:
                elo = player.get_elo()
                if elo:
                    self.elo -= elo
                self.players.remove(p)
                return True
        return False

    def mean_elo(self):
        try:
            return float(self.elo) / len(self.players)
        except:
            return 0

    def auto_add_player(self, other, pickpool):
        elo_diff = self.mean_elo() - other.mean_elo()
        elo = None
        player = None
        for p in pickpool:
            p_elo = p.get_elo(self.gametype)
            if not elo or (elo_diff >  0 and p_elo < elo) or (elo_diff <= 0 and p_elo > elo):
                elo = p_elo
                player = p
                
        print self.name + ": auto-adding {0} ({1} elo)".format(player.nick, player.get_elo(self.gametype))
        self.add_player(player)
        return player


class Game:
    """A game that can be played in the channel"""
    def __init__(self, pickup, nick, name, captains=2, players=8, autopick=True, **kwargs):
        self.pickup = pickup
        self.xonstat = pickup.xonstat
        self.nick = nick
        self.name = name
        self.caps = int(captains)
        self.maxplayers = int(players)
        if type(autopick) == str:
            if autopick.lower() == "no":
                self.autopick = False
            elif autopick.lower() == "yes":
                self.autopick = True
        else:
            self.autopick = bool(autopick)
        self.info = kwargs
        self.players = []
        self.starting = False
        self.abort_start = False
        
        if 'teamnames' in kwargs:
            self.teamnames = config.getlist('Pickup: '+nick, 'teamnames')
        else:
            self.teamnames = []

    def pre_start(self):
        """Initiates a game's start"""
        self.starting = True
        start = self.pickup.pypickupbot.fire('pickup_game_pre_start', self)

        def _knowStart(start):
            if not start:
                self.pickup.pypickupbot.cmsg(
                    _("%s game about to start..")%self.name
                )
            else:
                self.do_start()
        start.addCallback(_knowStart)

    def abort_start(self):
        """Aborts a starting game"""
        if self.starting:
            self.abort_start = True
        return self

    def abort(self):
        """Aborts a starting game"""
        if self.starting:
            self.abort_start = True
        if len(self.players):
            self.players = []
            self.pickup.update_topic()
        self.starting = False
        return self

    def do_start(self):
        """Does the actual starting of the game"""
        if self.abort_start or not self.starting:
            self.abort_start = False
            self.starting = False
            return

        players = self.players[:self.maxplayers]
        for player in players:
            self.pickup.all_games().force_remove(player)

        self.pickup.update_topic()

        self.pickup.pypickupbot.notice(self.pickup.pypickupbot.channel, 
            _("%(gamenick)s game ready to start in %(channel)s")
                % {'gamenick': self.nick, 'channel': self.pickup.pypickupbot.channel})

        # flatten player list ([[a,b],[c,d]] -> [a,b,c,d])
        for p in players:  # flatten list
            if type(p) == list:
                players.remove(p)
                players.extend(p)
        
        # Set up teams
        # TODO - randomly constructed team names ("adjective + verb" scheme) ?
        gametype = self.nick
        teams = []

        while len(self.teamnames) < self.caps:
            self.teamnames.append( "Team {0}".format(len(self.teamnames)+1) )

        for name in self.teamnames:
            teams.append(Team(name, gametype))

        captains = []
        
        if not self.autopick:
            pickpool = []
            for p in players:
                nick = self.xonstat._get_original_nick(p)
                if self.xonstat.players.has_key(nick):
                    player = self.xonstat.players[nick]
                    pickpool.append(player)
                    continue
                pickpool.append(Player(p, None))

            players = sorted(pickpool)
            captains = random.sample(pickpool, self.caps)

            print players, captains

            playerlist  = [ p.nick.encode('utf-8') for p in players ]
            captainlist = [ c.nick.encode('utf-8') for c in captains ]
            self.pickup.pypickupbot.fire('pickup_game_starting', self, playerlist, captainlist)

            if len(captains) > 0:
                cmsg = config.get('Pickup messages', 'game ready').decode('string-escape')%\
                    {
                        'nick': self.nick,
                        'playernum': len(self.players),
                        'playermax': self.maxplayers,
                        'name': self.name,
                        'numcaps': self.caps,
                        'playerlist': ', '.join([
                                config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick(),
                                    'playerid': player.playerid,
                                }
                                for player in players]),
                        'captainlist': ', '.join([
                                config.get('Pickup messages', 'game ready captain').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick(),
                                    'playerid': player.playerid,
                                }
                                for player in captains]),
                    }
                self.pickup.pypickupbot.cmsg(cmsg.encode('utf-8'))
                
                if config.getboolean("Pickup", "PM each player on start"):
                    for player in players:
                        msg = config.get("Pickup messages", "youre needed").decode('string-escape')%\
                            {
                                'channel': self.pickup.pypickupbot.channel,
                                'name': self.name,
                                'nick': self.nick,
                                'numcaps': self.caps,
                                'playerlist': ', '.join([
                                    config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                    {
                                        'nick': player.get_nick(),
                                        'name': player.nick,
                                        'playerid': player.playerid,
                                    }
                                    for player in players]),
                                'captainlist': ', '.join([
                                config.get('Pickup messages', 'game ready captain').decode('string-escape')%
                                    {
                                        'nick': player.get_nick(),
                                        'name': player.nick,
                                        'playerid': player.playerid,
                                    }
                                    for player in captains]),
                            }
                        self.pickup.pypickupbot.msg(player, msg.encode('utf-8'))
                        
            else:
                cmsg = config.get('Pickup messages', 'game ready nocaptains').decode('string-escape')%\
                    {
                        'nick': self.nick,
                        'playernum': len(self.players),
                        'playermax': self.maxplayers,
                        'name': self.name,
                        'numcaps': self.caps,
                        'playerlist': ', '.join([
                                config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick,
                                    'playerid': player.playerid,
                                }
                                for player in players]),
                    }
                self.pickup.pypickupbot.cmsg(cmsg.encode('utf-8'))

                if config.getboolean("Pickup", "PM each player on start"):
                    for player in players:
                        msg  = config.get("Pickup messages", "youre needed nocaptains").decode('string-escape')%\
                            {
                                'channel': self.pickup.pypickupbot.channel,
                                'name': self.name,
                                'nick': self.nick,
                                'numcaps': self.caps,
                                'playerlist': ', '.join([
                                    config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                    {
                                        'nick': player.get_nick(),
                                        'name': player.nick,
                                        'playerid': player.playerid,
                                    }
                                    for player in players]),
                            }
                        self.pickup.pypickupbot.msg(player, msg.encode('utf-8'))

        else:  # if not self.autopick
            # Create a pickpool containing Player instances
            pickpool = []
            pickpool_noelo = []
            for p in players:
                nick = self.xonstat._get_original_nick(p)
                if self.xonstat.players.has_key(nick):
                    player = self.xonstat.players[nick]
                    if player.get_elo(gametype):
                        pickpool.append(player)
                        continue
                pickpool_noelo.append(Player(p, None))

            print "Elo:", pickpool
            print "No Elo:", pickpool_noelo
            
            # Shuffle pickpool for later use
            random.shuffle(pickpool)
            random.shuffle(pickpool_noelo)
            
            # Randomly select one captain, then select other one with similar elo
            # FIXME - only two teams are supported currently - FIXME
            team1, team2 = teams[:2]
            captain_elo_diff = "???"
            if len(pickpool) > 0:
                team1.captain = random.choice(pickpool)
                best_diff = None
                for p in pickpool:
                    if p == team1.captain:
                        continue
                    elo_diff = team1.captain.get_elo(gametype) - p.get_elo(gametype)
                    if not best_diff or elo_diff < best_diff:
                        team2.captain = p
                        best_diff = elo_diff
                if team2.captain:
                    captain_elo_diff = round(abs(best_diff),1)
                else:
                    team2.captain = random.choice(pickpool_noelo)
                print "Autopick captains:", team1.captain, ",", team2.captain, "(elo diff:", captain_elo_diff, ")"
            else:
                team1.captain, team2.captain = random.sample(pickpool_noelo, 2)
                print "Random captains:", team1.captain, ",", team2.captain
                
            players = pickpool + pickpool_noelo
            captains = [ team1.captain, team2.captain ]

            # auto-select players (based on elo)
            while len(pickpool):
                p = team1.auto_add_player(team2, pickpool)
                pickpool.remove(p)
                team1, team2 = team2, team1  # swap
                
            # randomly pick remaining players
            while len(pickpool_noelo):
                p = random.choice(pickpool_noelo)
                team1.add_player(p)
                pickpool_noelo.remove(p)
                team1, team2 = team2, team1  # swap

            if len(team1.players) != len(team2.players):
                print "Teams have different sizes:", team1, team2

            print players, teams

            playerlist  = [p.nick.encode('utf-8') for p in players]
            captainlist = [c.nick.encode('utf-8') for c in captains]
            self.pickup.pypickupbot.fire('pickup_game_starting', self, playerlist, captainlist)

            cmsg = config.get('Pickup messages', 'game ready autopick').decode('string-escape')%\
                {
                    'nick': self.nick,
                    'playernum': len(players),
                    'playermax': self.maxplayers,
                    'name': self.name,
                    'numcaps': self.caps,
                    'teamslist': ', '.join([
                        config.get('Pickup messages', 'game ready autopick team').decode('string-escape')%
                        {
                            'name': team.name,
                            'players': ', '.join([
                                config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick,
                                    'playerid': player.playerid,
                                }
                                for player in team.players]),
                            'mean_elo': round(team.mean_elo(),1),
                        }
                        for team in teams]),
                    'captainlist': ', '.join([
                                config.get('Pickup messages', 'game ready captain').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick,
                                    'playerid': player.playerid,
                                }
                                for player in captains]),
                    'elo_diff': captain_elo_diff,
                }
            self.pickup.pypickupbot.cmsg(cmsg.encode('utf-8'))
                
            if config.getboolean("Pickup", "PM each player on start"):
                for player in players:
                    msg = config.get("Pickup messages", "youre needed").decode('string-escape')%\
                        {
                            'channel': self.pickup.pypickupbot.channel,
                            'name': self.name,
                            'nick': self.nick,
                            'numcaps': self.caps,
                            'playerlist': ', '.join([
                                config.get('Pickup messages', 'game ready player').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick,
                                    'playerid': player.playerid,
                                }
                                for player in players]),
                            'captainlist': ', '.join([
                                config.get('Pickup messages', 'game ready captain').decode('string-escape')%
                                {
                                    'nick': player.get_nick(),
                                    'name': player.nick,
                                    'playerid': player.playerid,
                                }
                                for player in captains]),
                        }
                    self.pickup.pypickupbot.msg(player, msg.encode('utf-8'))

        self.pickup.pypickupbot.fire('pickup_game_started', self, playerlist, captainlist)
        self.starting = False

    def teamname(self, i):
        if len(self.teamnames) > i:
            return self.teamnames[i]
        else:
            return _("Team {0}").format(i+1)

    def add(self, call, user):
        """Add a player to this game"""
        if user not in self.players:
            self.players.append(user)
            self.pickup.update_topic()
        
        if len(self.players) >= self.maxplayers:
            self.pre_start()
            return False

    def who(self):
        """Who is in this game"""
        if len(self.players):
            return config.get('Pickup messages', 'who game').decode('string-escape')%\
                {'nick': self.nick, 'playernum': len(self.players), 'playermax': self.maxplayers,
                'name': self.name, 'numcaps': self.caps, 'playerlist': ', '.join(self.players) }

    def remove(self, call, user):
        """Removes a player from this game"""
        if user in self.players:
            if not self.starting or len(self.players) > self.maxplayers:
                self.players.remove(user)
                self.pickup.update_topic()
            else:
                call.reply(_('Too late to remove from %s') % self.nick)

    def force_remove(self, user):
        try:
            self.players.remove(user)
            self.pickup.update_topic()
        except ValueError:
            pass

    def rename(self, oldnick, newnick):
        """Rename a player"""
        try:
            i = self.players.index(oldnick)
            self.players[i] = newnick
        except ValueError:
            pass

class Games(Game):
    """Groups multiple games to dispatch calls"""
    def __init__(self, games):
        self.games = games

    def remove(self, *args):
        for game in self.games: game.remove(*args)
    def pre_start(self, *args):
        for game in self.games: game.pre_start(*args)
    def force_remove(self, *args):
        for game in self.games: game.force_remove(*args)
    def rename(self, *args):
        for game in self.games: game.rename(*args)

    def add(self, *args):
        for game in self.games:
            if game.add(*args) == False:
                break

    def who(self, *args):
        return [game.who(*args) for game in self.games]

    def abort(self, *args):
        for game in self.games:
            game.abort()
        return self

    def abort_start(self, *args):
        for game in self.games:
            game.abort_start()
        return self


class XonstatInterface:

    def __init__(self):
        self.players = {}       # nick : playerid

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
            SELECT      id, nick, playerid, create_dt
            FROM        xonstat_players
            ORDER BY    create_dt
            """)
        self.players = {}
        def _loadPlayers(r):
            for entry in r:
                index, nick, playerid, create_dt = entry
                self.players[nick] = Player(nick, playerid, create_dt, index)
        return d.addCallback(_loadPlayers)

    def _find_player(self, nick):
        if self.players.has_key(nick):
            return self.players[nick]
        return None

    def _find_playerid(self, playerid):
        result = {}
        for k,p in self.players.items():
            if int(p.playerid) == int(playerid):
                result[k] = p
        return result

    def _search(self, string):
        result = {}
        for k,p in self.players.items():
            if string.lower() in p.get_stripped_nick().lower():
                result[k] = p
        return result

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

    def _delete(self, nick):
        if nick.startswith("#"):
            index = int(nick[1:])
            return db.runOperation("""
                DELETE FROM xonstat_players
                WHERE       id=?
                """, (index,))
        else:
            return db.runOperation("""
                DELETE FROM xonstat_players
                WHERE       nick=?
                """, (nick,))

    def _insert(self, nick, playerid):
        return db.runOperation("""
            INSERT INTO xonstat_players(nick, playerid, create_dt)
            VALUES      (:nick, :playerid, :ctime)
            """, (nick, playerid, itime(),))

    def _get_nick(self, nick):
        return nick

    def _get_original_nick(self, nick):
        return nick

    def _rename_user(self, oldname, newname):
        try:
            self.players[newname] = self.players[oldname]
            del self.players[oldname]
        except:
            pass
    

class XonstatPickupBot:
    """Allows the bot to run games with captain-picked teams"""

    def all_games(self):
        """Gets a wrapper for all games"""
        return Games(self.games.values())

    def get_games(self, call, args, implicit_all=True):
        """Gets all or some games"""
        if len(args):
            games = []
            for arg in args:
                arg = arg.lower()
                if arg in self.games:
                    games.append(self.games[arg])
                else:
                    raise InputError(_("Game %s doesn't exist. Available games are: %s") % (arg, ', '.join(self.games.keys())))
            return Games(games)
        elif implicit_all:
            return Games(self.games.values())
        else:
            raise InputError(_("You need to specify a game."))

    def get_game(self, call, args):
        """Get one game"""
        if len(args) == 1:
            game = args[0].lower()
            if game in self.games:
                return self.games[game]
            else:
                raise InputError(_("Game %s doesn't exist. Available games are: %s") % (args[0], ', '.join(self.games.keys())))
        else:
            if len(args) > 1:
                raise InputError(_("This command only allows one game to be selected."))
            else:
                raise InputError(_("This command needs one game to be selected."))

    def update_topic(self):
        """Update the pickup part of the channel topic"""
        config_topic = config.getint('Pickup', 'topic')

        if not config_topic:
            return

        out = []
        for gamenick in self.order:
            game = self.games[gamenick]
            if config_topic == 1 or game.players:
                out.append(
                    config.get('Pickup messages', 'topic game').decode('string-escape')
                    % {
                        'nick': game.nick, 'playernum': len(game.players),
                        'playermax': game.maxplayers, 'name': game.name,
                        'numcaps': game.caps
                    })

        self.topic.update(
            config.get('Pickup messages', 'topic game separator')\
                .decode('string-escape')\
            .join(out)
            )

    def add(self, call, args):
        """!add [game [game ..]]

        Signs you up for one or more games.
	"""
        self.get_games(call, args,
            config.getboolean("Pickup", "implicit all games in add"))\
            .add(call, call.nick)

    def remove(self, call, args):
        """!remove [game [game ..]]

        Removes you from one or more games.
	"""
        self.get_games(call, args).remove(call, call.nick)

    def renew(self, call, args):
        """!renew
        
        """
        # TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO TODO

	# The !renew command is to be used together with the timout feature,
	# where a player is removed automatically if there was no activity 
	# in the channel for some time. Players are required to !renew their
	# games to stay added.

    def who(self, call, args):
        """!who [game [game ..]]
        
        Shows who has signed up.
	"""
        games = [i for i in self.get_games(call, args).who() if i != None]
        all = False
        if len(args) < 1 or len(args) == len(self.games):
            all = True
        if len(games):
            if all:
                call.reply(_("All games:")+" "+config.get('Pickup messages', 'who game separator').decode('string-escape').join(games),


                    config.get('Pickup messages', 'who game separator').decode('string-escape'))
            else:
                call.reply(config.get('Pickup messages', 'who game separator').decode('string-escape').join(games),
                    config.get('Pickup messages', 'who game separator').decode('string-escape'))
        else:
            if all:
                call.reply(_("No game going on!"))
            else:
                call.reply(_n("No game in mode %s", "No game in modes %s", len(args)) % ' '.join(args) )
        
    def promote(self, call, args):
        """!promote <game>

        Shows a notice encouraging players to sign up for the specified game.
	"""
        admin = self.pypickupbot.is_admin(call.user, call.nick)

        def _knowAdmin(admin):
            if self.last_promote + config.getint('Pickup', 'promote delay') > time() \
                    and not admin:
                raise InputError(_("Can't promote so often."))

            game = self.get_game(call, args)

            if call.nick not in game.players \
                    and not admin:
                raise InputError(_("Join the game yourself before promoting it."))

            self.last_promote = time()
            cmsg = config.get('Pickup messages', 'promote').decode('string-escape')%\
                {
                    'bold': '\x02', 'prefix': config.get('Bot', 'command prefix'),
                    'name': game.name, 'nick': game.nick,
                    'command': config.get('Bot', 'command prefix')+'add '+game.nick,
                    'channel': self.pypickupbot.channel,
                    'playersneeded': game.maxplayers-len(game.players),
                    'maxplayers': game.maxplayers, 'numplayers': len(game.players),
                }
            self.pypickupbot.cmsg(cmsg.encode('utf-8'))
        return admin.addCallbacks(_knowAdmin)

    def pull(self, call, args):
        """!pull <player> [game [game ..]]

        Removes someone else from one or more games.
	"""
        player = args.pop(0)
        games = self.get_games(call, args).force_remove(player)

    def force_start(self, call, args):
        """!start <game>

        Forces the game to start, even if not enough players signed up"""
        game = self.get_game(call, args)
        if len(game.players) >= game.caps:
            game.pre_start()
        else:
            call.reply(_("Not enough players to choose captains from."))

    def abort(self, call, args):
        """!abort [game [game ..]]
        
        Aborts a game.
	"""
        self.get_games(call, args).abort()

    def pickups(self, call, args):
        """!pickups [search]

        Lists games available for pickups.
        """
        call.reply( ', '.join(
                ["%s (%s)" % (nick, game.name)
                for nick, game in self.games.iteritems()
                if not args or args[0] in nick or args[0] in game.name.lower()]
            ), ', ')

    def clearPlayers(self, call, args):
        """!clearplayers
        
        Clears the registered players list completely. Prefer the purgeplayers command to this."""
        d = call.confirm("This will delete all registered players, continue?")
        def _confirmed(ret):
            if ret:
                def done(*args):
                    call.reply(_("Done."))
                return self.xonstat._purge().addCallback(done)
            else:
                call.reply(_("Cancelled."))
        return d.addCallback(_confirmed)

    def purgePlayers(self, call, args):
        """!purgeplayers <keep>

        Purges the registered players list from entries created later than [keep] ago."""
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
                self.xonstat._purge(keep).addCallback(done)
            else:
                call.reply(_("Cancelled."))
        d.addCallback(_confirmed)

    def whois(self, call, args):
        """!whois <playerid>
        
        Shows all nicks that have registered to a given playerid. This is useful to find out who has registered to a specific Xonstat account."""
        if not len(args) == 1:
            raise InputError("You need to specify a playerid to lookup.")
            
        players = self.xonstat._find_playerid(args[0])
        if len(players) == 0:
            call.reply(_("No players found."))
            return
    
        def do_call(is_op):
            keys = sorted(players.keys())
            if is_op:
                reply = config.get("Xonstat Interface", "player whois").decode('string-escape')%\
                        { 'players': ", ".join(["{0} ({1})".format(k, players[k].index) for k in keys]),
                          'num_players': len(players), 'gamenick': players.values()[0].get_stripped_nick(), }
            else:        
                reply = config.get("Xonstat Interface", "player whois").decode('string-escape')%\
                        { 'players': ", ".join(["{0}".format(k) for k in keys]),
                          'num_players': len(players), 'gamenick': players.values()[0].get_stripped_nick(), }
            call.reply(reply)
        FetchedList.has_flag(self.pypickupbot, self.pypickupbot.channel, call.nick, 'o').addCallback(do_call)        

    def listPlayers(self, call, args):
        """!listplayers

        Lists all players that have registered with the bot's Xonstat interface.
        """
        players = self.xonstat.players
        if len(players) == 0:
            call.reply(_("No players registered yet."))
            return
        
        def do_call(is_op):
            keys = sorted(players.keys())
            if is_op:
                reply = config.get("Xonstat Interface", "player list").decode('string-escape')%\
                        { 'players': ", ".join(["{0} ({1})".format(k, players[k].index) for k in keys]),
                          'num_players': len(players), }
            else:        
                reply = config.get("Xonstat Interface", "player list").decode('string-escape')%\
                        { 'players': ", ".join(["{0}".format(k) for k in keys]),
                          'num_players': len(players), }
            call.reply(reply)
        FetchedList.has_flag(self.pypickupbot, self.pypickupbot.channel, call.nick, 'o').addCallback(do_call)        

    def searchPlayers(self, call, args):
        """!searchplayers <text>

        Finds all players that have registered with the bot's Xonstat interface and whose nicks contain the given text. Ops will get the database indices in addition to the registered names (e.g. to remove players).
        """
        if not len(args) == 1:
            raise InputError("You need to specify a text to search for.")

        players = self.xonstat._search(args[0])
        if len(players) == 0:
            call.reply(_("No players found."))
            return
        
        reply = config.get("Xonstat Interface", "player search").decode('string-escape')%\
                { 'players': ", ".join([ "({1}) {0}".format(k, players[k].index) for k in players.keys() ]),
                  'num_players': len(players), }
        call.reply(reply)

    def playerInfo(self, call, args):
        """!playerinfo <nick>

        Shows details about a registered player (information from Xonstat). You need to specify the player's IRC nick to look up.
        """
        if not len(args) == 1:
            raise InputError("You need to specify a player nickname.")
        
        nick = self.xonstat._get_original_nick(args[0].lower())
        player = self.xonstat._find_player(nick)
        if not player:
            call.reply(_("No player named <{0}> found!").format(nick))
            return
        
        sep = config.get("Xonstat Interface", "playerinfo separator").decode('string-escape')
            
        elo_list = []
        for gametype,elo in player.get_elo_dict().items():
            if gametype == 'overall':
                continue
            eloscore, games = round(elo['elo'], 1), elo['games']
            entry = config.get("Xonstat Interface", "playerinfo elo entry").decode('string-escape')%\
                { 'gametype':gametype, 'elo':eloscore, }
            if games < 8:
                # don't show elos with little number of games
                continue
            if games < 32:
                entry += "*"
            elo_list.append(entry)
        elo_list.sort()
        elo_display = sep.join(elo_list)
        if len(elo_list) == 0:
            elo_display = _("none yet")
        
        rank_list = []
        for gametype,rank in player.get_rank_dict().items():
            if gametype == 'overall':
                continue
            rank, max_rank = rank['rank'], rank['max_rank']
            entry = config.get("Xonstat Interface", "playerinfo rank entry").decode('string-escape')%\
                { 'gametype':gametype, 'rank':rank, 'max_rank':max_rank, }
            rank_list.append(entry)
        rank_list.sort()
        rank_display = sep.join(rank_list)
        if len(rank_list) == 0:
            rank_display = _("none yet")
        
        reply = config.get("Xonstat Interface", "playerinfo").decode('string-escape')%\
                { 'nick': nick, 'gamenick': player.get_nick(), }
        if len(elo_list) > 0:
            reply += config.get("Xonstat Interface", "playerinfo elos").decode('string-escape')%\
                { 'elos': elo_display }
        if len(rank_list) > 0:
            reply += config.get("Xonstat Interface", "playerinfo ranks").decode('string-escape')%\
                { 'ranks': rank_display, }
        reply += config.get("Xonstat Interface", "playerinfo profile").decode('string-escape')%\
            { 'profile': player.get_xonstat_url(), }
        call.reply(reply)

    def playerExists(self, call, args):
        """!playerexists <nick>

        Checks if a player has registered with the bot's Xonstat interface.
        """
        if not len(args) == 1:
            raise InputError(_("You must name a player to look up."))

        nick = self.xonstat._get_original_nick(args[0].lower())
        player = self.xonstat._find_player(nick)
        if player:
            reply = _("This nick is registered with player id #%(playerid)s (as \x02%(originalnick)s\x02). " + \
                    "Use \x02%(prefix)splayerinfo %(nick)s\x02 to see more details.")%\
                    {'prefix':config.get('Bot', 'command prefix'), 'playerid':player.playerid,
                     'nick':args[0], 'originalnick':nick }
        else:
            reply = _("No player information found for <{0}>.".format(nick))
        call.reply(reply)

    def register(self, call, args):
        """!register <xonstat #id>

        Registers your nick with the given Xonstat account id. If successful, a public message will be shown on the channel.
        Note that you can register more than one nick to a Xonstat account (e.g. if you use multiple nicks on IRC).
        """
        
        # TODO - only allow if user is authed
        # FetchedList.has_flag(self.bot, self.bot.channel, nick, <flag>) == True
        
        if not len(args) == 1:
            raise InputError(_("You must specify your Xonstat profile id to register an account."))
        
        nick = self.xonstat._get_original_nick(call.nick).lower()
        player = self.xonstat._find_player(nick)
        if player:
            raise InputError(_("This nick is already registered with player id #{0} (as <{1}>) - can't continue! " + \
                    "If you need to change your player id, please contact one of the channel operators.").\
                    format(player.get_id(), player.nick))
        try:
            playerid = int(args[0])
        except ValueError:
            raise InputError(_("Player id must be an integer."))
                   
        player = self.xonstat._find_playerid(playerid)
        if player:
            # SAFETY FEATURE DROPPED 
            #raise InputError(_("This player id is already registered to {0} (as <{1}>) - can't continue! " + \
            #        "If you need to change your nick, please contact one of the channel operators.").\
            #        format(player.get_stripped_nick(), player.nick))
            self.pypickupbot.msg(self.pypickupbot.channel,
                    _("This player id is already registered! Plese check if your input is correct before you continue. Use !whois {0} to look up who registered to this player id").\
                    format(playerid))

        player = Player(nick, playerid)
        if not player.is_valid():
            raise InputError(_("This doesn't seem to be a valid Xonstat playerid!"))

        d = call.confirm(_("You're about to register yourself with player id #{0} ({1}, " + \
                "Xonstat profile {2}), is this correct?").\
                format(player.get_id(), player.get_stripped_nick(), player.get_xonstat_url()))
        def _confirmed(ret):
            if ret:
                def done(*args):
                    def done(*args):
                        player = self.xonstat._find_player(nick)
                        call.reply("Done.")
                        msg = config.get('Xonstat Interface', 'player registered').decode('string-escape')%\
                            { 'nick': nick, 'playerid': playerid, 'gamenick': player.get_nick(), 'profile': player.get_xonstat_url(), }
                        self.pypickupbot.msg( self.pypickupbot.channel, msg.encode("utf-8") )
                    self.xonstat._load_from_db().addCallback(done)
                self.xonstat._insert(nick, playerid).addCallback(done)
            else:
                call.reply(_("Cancelled."))
        d.addCallback(_confirmed)

    def removePlayer(self, call, args):
        """!removeplayer <nick|index>

        Removes a specific player from the bot's Xonstat database.

	Using the index allows to delete a specific from the database. Ops can use !listplayers to find out the index.
        """
        if not len(args) == 1:
            raise InputError(_("You need to specify one player name."))
        nick = args[0]
        d = call.confirm(_("This will delete all entries registered to {0}, continue?").format(nick))
        def _confirmed(ret):
            if ret:
                def done(*args):
                   def done(*args):
                        call.reply(_("Done."))
                   d = self.xonstat._load_from_db()
                   d.addCallback(done)
                return self.xonstat._delete(nick).addCallback(done)
            else:
                call.reply(_("Cancelled."))
        return d.addCallback(_confirmed)

    def __init__(self, bot):
        """Plugin init

        Reads games from config"""
        self.xonstat = XonstatInterface()
        self.bot = bot
        
        self.games = {}
        self.order = []
        self.last_promote = 0
        if not config.has_section('Pickup games'):
            log.err('Could not find section "Pickup games" of the config!')
            return
        games = config.items('Pickup games')
#        log.msg(games)

        for (gamenick, gamename) in games:
            if gamenick == 'order':
                self.order = config.getlist('Pickup games', 'order')
            else:
                if config.has_section('Pickup: '+gamenick):
                    gamesettings = dict(config.items('Pickup: '+gamenick))
                else:
                    gamesettings = {}
                self.games[gamenick] = Game(
                    self,
                    gamenick, gamename,
                    **gamesettings)
                if gamenick not in self.order:
                    self.order.append(gamenick)

        self.order = filter(lambda x: x in self.games, self.order)

    def joinedHomeChannel(self):
        """when home channel joined, set topic"""
        if config.get('Pickup', 'topic'):
            self.topic = self.pypickupbot.topic.add('', Topic.GRAVITY_BEGINNING)
            self.update_topic()

    def userRenamed(self, oldname, newname):
        """track user renames"""
        self.xonstat._rename_user(oldname, newname)
        self.all_games().rename(oldname, newname)

    def userLeft(self, user, channel, *args):
        """track quitters"""
        if channel == self.pypickupbot.channel:
            self.all_games().force_remove(user.split('!')[0])
    
    def userQuit(self, user, quitMessage):
        """track quitters"""
        self.all_games().force_remove(user.split('!')[0])

    commands = {
        'add':              (add,           COMMAND.NOT_FROM_PM),
            'addup':        (add,           COMMAND.NOT_FROM_PM),
        'remove':           (remove,        COMMAND.NOT_FROM_PM),
            'leave':        (remove,        COMMAND.NOT_FROM_PM),
            'logout':       (remove,        COMMAND.NOT_FROM_PM),
        #'renew':            (renew,         COMMAND.NOT_FROM_PM),
        'who':              (who,           0),
        'promote':          (promote,       COMMAND.NOT_FROM_PM),
        'pull':             (pull,          COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'start':            (force_start,   COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'abort':            (abort,         COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'pickups':          (pickups,       0),
        
        'register':         (register,      COMMAND.NOT_FROM_PM),
        'whois':            (whois,         0),
        'playerinfo':       (playerInfo,    0),
            'info':         (playerInfo,    0),
        'player':           (playerExists,  0),
        'listplayers':      (listPlayers,   0),
            'list':         (listPlayers,   0),
        'searchplayers':    (searchPlayers, 0),
            'search':       (searchPlayers, 0),
        'removeplayer':     (removePlayer,  COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'clearplayers':     (clearPlayers,  COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'purgeplayers':     (purgePlayers,  COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        }

    eventhandlers = {
        'joinedHomeChannel':    joinedHomeChannel,
        'userRenamed':          userRenamed,
        'userLeft':             userLeft,
        'userKicked':           userLeft,
        'userQuit':             userQuit,
    }

xonstat_pickup = SimpleModuleFactory(XonstatPickupBot)

