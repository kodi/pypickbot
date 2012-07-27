.. _plugin-pickup:

***************************
``pickup``: Organized games
***************************

``pickup`` is the module that handles games to be signed up for. It lets players add up for each of them until one of them is full, at which point the game is started and the bot announces who is signed up. Rudimentary game recording -- namely the :command:`lastgame` and :command:`top10` commands -- is provided by the ``pickup_playertracking`` module(See :ref:`plugin-pickup_playertracking`).

Quick setup for this plugin is explained in the :ref:`Quick Setup guide <quick-pickup>`.

Usage
=====

.. module:: pickup

.. command:: !pickups [search]

    Lists available games.

.. command:: !add [game [game ...]]

    Lets you sign up for available games. Specify one or more games by their
    short handle(the name outside the parenthesis in :command:`pickups`).
    If no game is specified, signs up for all available games. 

.. command:: !remove [game [game ...]]

    Removes you from one or more games.
    Removes you from all games if no game is specified.
    You are automatically removed from all games when you leave.

.. command:: !who [game [game ...]]

    Lists people who are signed up. If you specify one or more games it will filter
    the result.

.. command:: !promote game

    Promotes the specified game with a message inviting people to join.

By default, the channel topic will be updated each time someone adds/removes to reflect current player counts.

Admin commands
==============

.. command:: !pull player [game [game ...]]

    Same as :command:`remove`, except it lets you specify another player as you.

.. command:: !start game

    Immediately starts a game even if it isn't full yet. However,
    there should at least be enough players for captains to be chosen.

.. command:: !abort [game [game ...]]

    Removes all players from one or more games.

Settings
========

Settings are organized under 3 headings:

* ``[Pickup]``, which contains
* The games list, ``[Pickup games]``
* Individual settings for each game

General Settings
----------------

.. highlight:: ini

::

    [Pickup]
    promote delay=180
    PM each player on start=yes
    implicit all games in add=yes
    topic=1

.. section:: Pickup

.. setting:: promote delay = 3min (duration)

    Minimum delay in seconds between two :command:`!promote` calls, to
    prevent spam.
    Regardless of this setting, players also have to be signed up for a game
    in order to promote it. Channel admins bypass these restrictions.

.. setting:: PM each player on start = yes (bool)

    If set to ``yes``, the bot will private-message signed up players
    when their game starts. While useful, it requires the bot to take the time
    to send each of these PMs with a delay in order not to be killed from
    the chat network for spam, which makes it appear as slow.

.. setting:: implicit all games in add = yes (bool)

    If set to no, the ability for players to use :command:`!add` without
    an argument (to sign up for all available games) is removed.

.. setting:: topic = 1 (int)

    As mentioned previously, the bot regularly updates the channel topic in order
    to reflect player counts for each game. This is the default behavior, with
    ``topic`` set to ``1``.
    Set ``topic`` to ``0`` to entirely disable that feature.
    Set ``topic`` to ``2`` to only show games which have at least one player signed 
    up.

Games List
----------

Each game is to be defined in the games list by a ``Short name=Full name pair``, under the ``[Pickup games]`` section::

    [Pickup games]
    ctf=4v4 Capture The Flag
    tdm=5v5 Team Deathmatch

A player would add up for one of these with ``!add ctf`` or ``!add tdm``.

Additionally, you can set an order for the games to appear by in the channel
topic with the ``order`` setting in the same section as the games. Order is otherwise unpredictable.

.. setting:: [Pickup games] order = (list)

    This setting should be written at the beginning of the section. It should
    list the order you want to give to the games. Name each game by their short
    name::

        [Pickup games]
        order=tdm,ctf
        ctf=4v4 Capture The Flag
        tdm=5v5 Team Deathmatch

    If a game is not mentioned in the order but is defined later, it will be
    appended to the end of it. If a game appears in the ``order`` setting but
    isn't defined, it is ignored. If you place the ``order`` setting at the
    end of the section, games not listed in the setting will never appear in
    the channel topic.

Game-specific settings
----------------------

For each game, you can have a section named ``[Pickup: shortname]`` with
settings specific to it.

For instance, to define the 5v5 TDM game from the previous example, one
would have::

    [Pickup: tdm]
    captains=2
    players=10

If the section is omitted, the bot will assume the game is to be run with
8 players, 2 of which are captains, with no automatic team picking.
This suits the 4v4 CTF example, and therefore you wouldn't have to
define a section with settings for it.

Here are all the settings available in this section:

.. section:: Pickup: shortname

.. setting:: players = 8 (int)

    Amount of players needed for the game to be full.

.. setting:: captains = 2 (int)

    Number of captains to be chosen. If set to ``0``, the game will have no
    captains. If autopick is enabled(see below), this is the number of teams
    to be created.

.. setting:: autopick = no (bool)

    If set to yes, the bot will automatically pick team members when the game
    is full. There are no captains, but the ``captains`` setting is used to
    determine how many teams should be created.

.. setting:: teamnames = Team 1, Team 2, ... (list)

    Set this to a list of team names if you want custom team names in
    autopick mode::

        [Pickup: 4wctf]
        autopick=yes
        teamnames=Team blue, Team gold, Team red, Team green

    If ``autopick`` is enabled and this setting isn't given, generic team
    names will be used, such as *Team 1* and *Team 2*.

.. :
    The pickup plug-in provides the main function of this bot.

    The messages section makes heavy use of the Python formatting operator to
    substitute parts of the said messages, and of mIRC color codes.
    See these links for more information:
    http://docs.python.org/library/stdtypes.html#string-formatting
    http://www.mirc.com/help/color.txt
    Beware that what is documented as ^C is to be written as \x03. \x02 toggles
    bold text on or off.

