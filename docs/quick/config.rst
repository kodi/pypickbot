.. _quick-configure:

********************
Configuring your bot
********************

PyPickupBot's config is separated into two files: ``init.cfg`` and ``config.cfg``. The former typically includes general bot configuration(nickname, command prefix, ..) connection details such as irc server, channels to join and most importantly modules to load. The latter is where all plugin configuration goes, more or less everything else.

Creating a config dir
=====================

.. highlight:: bash

You should first create a directory to contain the config files::

    mkdir ~/my_shiny_pypickupbot_config/
    cd ~/my_shiny_pypickupbot_config/

Note that it will also host the bot's persistent database where a lot of stuff will be saved, for instance started games logs or channel bans. This makes it convenient because the config directory effectively becomes all the bot's knowledge, making it easy to save or transfer. Always remember however, that you are likely to have a password or two in the config(NickServ/Q authentication).

init.cfg
========

As precised earlier, ``init.cfg`` only contains few items.

.. highlight:: ini

::

    [Bot]
    nickname=ZeroBot

    [Server]
    host=irc.quakenet.org
    port=6667
    channels=#qlpickup.eu
    username=ZeroBot
    password=secret

    [Modules]
    modules+=q_auth

We will describe here the most important ones.

Bot section
-----------

::

    [Bot]
    nickname=JohnBot

The bot's nickname, as it will appear to other people.

Server Section
--------------

::

    [Server]
    host=irc.quakenet.org
    port=6667
    channels=#example

host
    IRC Server address to connect to.

port
    IRC Server port.

channels
    Channels to automatically join once connected.

If you plan on running your bot on a network that allows authenticating via server username/password(like FreeNode), or if you connect to a bouncer, these might be of use::
    
    [Server]
    ...
    username=johnbotaccount
    password=secret

username
    Username given to the server when connecting. It isn't necessarily the
    *nickname* that people will see.

password
    Password given to the server when connecting.

Modules Section
---------------

PyPickupBot's main functionality comes from modules(also known as plug-ins). In fact, without modules, it could only join a channel then sit there and do nothing. Hopefully, several modules are preloaded:

* ban --- manages channel bans
* chanops --- makes channel operators bot admins
* help --- gives command lists and help about specific commands
* info --- gives general information about the bot
* pickup --- used to run pickup games
* pickup_playertracking --- records started games and maintains a top 10 of active participants
* topic --- allows the admins to change parts of the bot-maintained channel topic

Translated into PyPickupBot's config, it would read like this(you don't have to
type it)::
    
    [Modules]
    modules=ban, chanops, help, info, pickup, pickup_playertracking, topic

If you plan on running your bot on a network using UnrealIRCd, such as QuakeNet, you can use the q_auth module to allow your bot to auth with Q before joining channels. You can tell PyPickupBot to load q_auth in addition to the preloaded modules like this::

    [Modules]
    modules+=q_auth

You don't need to repeat the preloaded modules at all in your config, as long as you use the ``modules+=`` syntax.

config.cfg
==========

``config.cfg`` however contains most of the settings::

    [Q Auth]
    username=JohnBot
    password=secret

    [Pickup games]
    tdm= 4v4 TDM
    ctf= 4v4 CTF

    [Pickup: tdm]
    captains=2
    players=8

    [Pickup: ctf]
    captains=2
    players=8

Q Auth
------

If you enabled the q_auth module as described earlier, you need to configure it. Typically, you only need to enter the account's username and password::

    [Q Auth]
    username=JohnBot
    password=secret

.. _quick-pickup:

Pickup
------

First, define in the ``Pickup games`` section the games that can be played::

    [Pickup games]
    ctf= 5v5 CTF    
    tdm= 4v4 TDM

Each config option here is treated as a game. The left-hand value is the short
name for the game, that people will use to join it. The right-hand value is a
title for the game. It can be anything you like, it isn't interpreted anyway.
It is shown in the output of ``!pickups`` and when a game fills up and starts.

For each game, you can have an optional section defining the game's settings::

    [Pickup: ctf]
    captains=2
    players=10

You can omit it if the game's settings matches the defaults, which are as
follows::

    [Pickup: tdm]
    captains=2
    players=8

Your bot is now configured!

Running the bot
===============

To start the bot, run the ``pickupbot`` script from the main folder as follows::

    /path/to/pickupbot -c ~/my_shiny_pypickupbot_config/

It will do it's thing and connect, currently with a lot of output you probably don't care about.

You usually want to run it within GNU screen or a similar application, so the
bot can continue running when you close the terminal or when you disconnect
from the server the bot is hosted on.

