.. _quick-usage:

*************
Using the bot
*************

Players interested in playing a game say ``!add <game>`` in the bot's main
channel, replacing ``<game>`` with the short name of the game they want to
play, for instance ``!add ctf``. You can list or search game types with the
``!pickups`` command.

Once the maximum number of players for a game is reached, players are removed
from all the queues (for instance if they added up for two different games at
once), and the bot announces the upcoming game with it's players and it's
randomly-selected captains.

Players then proceed to the game server, captains each go on one team and they
start picking players turn by turn. Once that step is done, they are ready to
start their game.

Common commands
===============

.. command:: !add [game [game ...]]
    :noindex:

    Signs you up for one or more games. If no game is provided, you are signed
    up for all games.

.. command:: !remove [game [game ...]]
    :noindex:

    Removes you from one or more games. Same as with ``!add`` for when no
    games are provided.

.. command:: !who [game [game ...]]
    :noindex:

    Lists who is currently signed up for a game.

.. command:: !lastgame
    :noindex:

    Shows information about the last played game, such as time elapsed since it started and participating players.

.. command:: !motd [message]
    :noindex:

    Sets a message to appear at the end of the channel topic. If no message is
    provided, it shows the current one. If you type ``!motd --`` is provided
    as message, the current message is removed.

Note that ``!motd`` is only available for channel admins. By default, channel
admins are the channel's operators. There are many more commands listed in the
user manual.

