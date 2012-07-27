.. _plugin-pickup_playertracking:

************************************************
``pickup_playertracking``: Simple game recording
************************************************

Usage
=====

.. module:: pickup_playertracking

.. command:: !lastgame [game [game ...]]
             !lastgame #id

    Tells you what the last started game was, and who played in it.
    Specify one or more games to filter the search.

    The *#id* form lets you lookup a started game by it's ID. Everytime
    a game is started, the bot will print publicly the game's ID number.
    You can also find game IDs with the :command:`lastgames` command.

.. command:: !lastgames [game [game ...]]
    
    Lists recently started games.

.. command:: !top10

    Lists most participating players over the course of one week
    (or :setting:`top10 spread`).

Admin commands
==============

.. command:: !purgegames [keep]

    Clears the bot's database of all games recorded longer than *keep*
    ago. (Defaults to :setting:`top10 spread`)

.. command:: !cleargames

    Clears the database of all recorded games.

Settings
========

.. setting:: [Pickup player tracking]top10 spread = 1week (duration)
    
    Duration :command:`top10` goes back to.

