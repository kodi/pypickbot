# pypickupbot - An ircbot that helps game players to play organized games
# with captain-picked teams.
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
import random

from twisted.python import log

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot.irc import COMMAND, InputError
from pypickupbot.topic import Topic
from pypickupbot import config


class Game:
    """A game that can be played in the channel"""

    def __init__(self, pickup, nick, name, captains=2, players=8, autopick=False, **kwargs):
        self.pickup = pickup
        self.nick = nick
        self.name = name
        self.caps = int(captains)
        self.maxplayers = int(players)
        self.autopick = bool(autopick)
        self.info = kwargs
        self.players = []
        self.starting = False
        self.abort_start = False

        if 'teamnames' in kwargs:
            self.teamnames = config.getlist('Pickup: ' + nick, 'teamnames')
        else:
            self.teamnames = []

    def pre_start(self):
        """Initiates a game's start"""
        self.starting = True
        start = self.pickup.pypickupbot.fire('pickup_game_pre_start', self)

        def _knowStart(start):
            if not start:
                self.pickup.pypickupbot.cmsg(
                    _("%s game about to start..") % self.name
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

        captains = []

        if not self.autopick:
            pickpool = sorted(players)
            captains = random.sample(pickpool, 2)

            self.pickup.pypickupbot.fire('pickup_game_starting', self, players, captains)
            if len(captains) > 0:
                self.pickup.pypickupbot.msg(self.pickup.pypickupbot.channel,
                                            config.get('Pickup messages', 'game ready').decode('string-escape') %
                                            {
                                                'nick': self.nick,
                                                'playernum': len(self.players),
                                                'playermax': self.maxplayers,
                                                'name': self.name,
                                                'numcaps': self.caps,
                                                'playerlist': ', '.join(players),
                                                'captainlist': ', '.join(captains)
                                            })
                if config.getboolean("Pickup", "PM each player on start"):
                    for player in players:
                        self.pickup.pypickupbot.msg(player,
                                                    config.get("Pickup messages", "youre needed").decode('string-escape') %
                                                    {
                                                        'channel': self.pickup.pypickupbot.channel,
                                                        'name': self.name,
                                                        'nick': self.nick,
                                                        'numcaps': self.caps,
                                                        'playerlist': ', '.join(players),
                                                        'captainlist': ', '.join(captains)
                                                    })
            else:
                self.pickup.pypickupbot.msg(self.pickup.pypickupbot.channel,
                                            config.get('Pickup messages', 'game ready nocaptains').decode('string-escape') %
                                            {
                                                'nick': self.nick,
                                                'playernum': len(self.players),
                                                'playermax': self.maxplayers,
                                                'name': self.name,
                                                'numcaps': self.caps,
                                                'playerlist': ', '.join(players)
                                            })
                if config.getboolean("Pickup", "PM each player on start"):
                    for player in players:
                        self.pickup.pypickupbot.msg(player,
                                                    config.get("Pickup messages", "youre needed nocaptains").decode('string-escape') %
                                                    {
                                                        'channel': self.pickup.pypickupbot.channel,
                                                        'name': self.name,
                                                        'nick': self.nick,
                                                        'numcaps': self.caps,
                                                        'playerlist': ', '.join(players),
                                                    })
        else:
            teams = [[] for i in range(self.caps)]
            players_ = sorted(players)
            for i in range(len(players)):
                player = random.choice(players_)
                players_.remove(player)
                teams[i % self.caps].append(player)

            self.pickup.pypickupbot.fire('pickup_game_starting', self, teams, captains)
            self.pickup.pypickupbot.cmsg(
                config.get('Pickup messages', 'game ready autopick').decode('string-escape') %
                {
                    'nick': self.nick,
                    'playernum': len(players),
                    'playermax': self.maxplayers,
                    'name': self.name,
                    'numcaps': self.caps,
                    'teamslist': ', '.join([
                        config.get('Pickup messages', 'game ready autopick team').decode('string-escape') %
                        {
                            'name': self.teamname(i),
                            'players': ', '.join(team)
                        }
                        for i, team in enumerate(teams)])
                })

        self.pickup.pypickupbot.fire('pickup_game_started', self, players, captains)

        self.starting = False

    def teamname(self, i):
        if len(self.teamnames) > i:
            return self.teamnames[i]
        else:
            return _("Team {0}").format(i + 1)

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
            return config.get('Pickup messages', 'who game').decode('string-escape') % {'nick': self.nick, 'playernum': len(self.players),
                                                                                        'playermax': self.maxplayers, 'name': self.name,
                                                                                        'numcaps': self.caps, 'playerlist': ', '.join(self.players)}

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


class PickupBot:
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
            config.get('Pickup messages', 'topic game separator') \
            .decode('string-escape') \
            .join(out)
        )

    def add(self, call, args):
        """!add [game [game ..]]

        Signs you up for one or more games"""
        self.get_games(call, args,
                       config.getboolean("Pickup", "implicit all games in add")) \
            .add(call, call.nick)

    def remove(self, call, args):
        """!remove [game [game ..]]

        Removes you from one or more games"""
        self.get_games(call, args).remove(call, call.nick)

    def who(self, call, args):
        """!who [game [game ..]]
        
        Shows who has signed up"""
        games = [i for i in self.get_games(call, args).who() if i != None]
        all = False
        if len(args) < 1 or len(args) == len(self.games):
            all = True
        if len(games):
            if all:
                call.reply(_("All games:") + " " + config.get('Pickup messages', 'who game separator').decode('string-escape').join(games),


                           config.get('Pickup messages', 'who game separator').decode('string-escape'))
            else:
                call.reply(config.get('Pickup messages', 'who game separator').decode('string-escape').join(games),
                           config.get('Pickup messages', 'who game separator').decode('string-escape'))
        else:
            if all:
                call.reply(_("No game going on!"))
            else:
                call.reply(_n("No game in mode %s", "No game in modes %s", len(args)) % ' '.join(args))

    def maps(self, call, args):

        call.reply(self.maps)

    def set_maps(self, call, args):

        self.maps = ' '.join(args)
        call.reply('Maps set to : ' + ' '.join(args))



    def promote(self, call, args):
        """!promote <game>

        Shows a notice encouraging players to sign up for the specified game"""
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
            self.pypickupbot.cmsg(
                config.get('Pickup messages', 'promote').decode('string-escape') % {
                    'bold': '\x02', 'prefix': config.get('Bot', 'command prefix'),
                    'name': game.name, 'nick': game.nick,
                    'command': config.get('Bot', 'command prefix') + 'add ' + game.nick,
                    'channel': self.pypickupbot.channel,
                    'playersneeded': game.maxplayers - len(game.players),
                    'maxplayers': game.maxplayers, 'numplayers': len(game.players),
                })

        return admin.addCallbacks(_knowAdmin)

    def pull(self, call, args):
        """!pull <player> [game [game ..]]

        Removes someone else from one or more games"""
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
        
        Aborts a game"""
        self.get_games(call, args).abort()

    def pickups(self, call, args):
        """!pickups [search]

        Lists games available for pickups.
        """
        call.reply(', '.join(
            ["%s (%s)" % (nick, game.name)
             for nick, game in self.games.iteritems()
             if not args or args[0] in nick or args[0] in game.name.lower()]
        ), ', ')


    def __init__(self, bot):
        """Plugin init

        Reads games from config"""
        self.games = {}
        self.order = []
        self.last_promote = 0
        self.maps = ''
        if not config.has_section('Pickup games'):
            log.err('Could not find section "Pickup games" of the config!')
            return
        games = config.items('Pickup games')
        #        log.msg(games)

        for (gamenick, gamename) in games:
            if gamenick == 'order':
                self.order = config.getlist('Pickup games', 'order')
            else:
                if config.has_section('Pickup: ' + gamenick):
                    gamesettings = dict(config.items('Pickup: ' + gamenick))
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
        self.all_games().rename(oldname, newname)

    def userLeft(self, user, channel, *args):
        """track quitters"""
        if channel == self.pypickupbot.channel:
            self.all_games().force_remove(user.split('!')[0])

    def userQuit(self, user, quitMessage):
        """track quitters"""
        self.all_games().force_remove(user.split('!')[0])

    commands = {
        'add': (add, COMMAND.NOT_FROM_PM),
        'a': (add, COMMAND.NOT_FROM_PM),
        'addup': (add, COMMAND.NOT_FROM_PM),
        'remove': (remove, COMMAND.NOT_FROM_PM),
        'r': (remove, COMMAND.NOT_FROM_PM),
        'leave': (remove, COMMAND.NOT_FROM_PM),
        'logout': (remove, COMMAND.NOT_FROM_PM),
        'who': (who, 0),
        'w': (who, 0),
        'promote': (promote, COMMAND.NOT_FROM_PM),
        'pull': (pull, COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'start': (force_start, COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'abort': (abort, COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
        'pickups': (pickups, 0),
        'maps': (maps, 0),
        'set_maps': (set_maps, COMMAND.NOT_FROM_PM | COMMAND.ADMIN),
    }

    eventhandlers = {
        'joinedHomeChannel': joinedHomeChannel,
        'userRenamed': userRenamed,
        'userLeft': userLeft,
        'userKicked': userLeft,
        'userQuit': userQuit,
    }


pickup = SimpleModuleFactory(PickupBot)

