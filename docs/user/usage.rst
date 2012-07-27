.. _user-usage:

*****
Usage
*****

Using commands
==============

Commands in this manual
=======================

Bot Settings
============

.. section:: Bot

.. setting:: nickname = pypickupbot (string)
    :init:

    The bot's nickname when connecting to IRC

.. setting:: command prefix = ! (string)
    :init:

    Short prefix to address commands to the bot.

.. setting:: allow mentions = no (bool)
    :init:

    Allow the bot to be addressed by mentionning its nickname.

.. setting:: warn on unknown command = yes (bool)
    :init:

    Warn users when they address the bot with an unknown command.

.. setting:: max reply splits before waiting = 2 (int)
    :init:

    When messages are too long to fit in one IRC message, the bot splits
    it into multiple messages. This is how many messages the bot will
    send before asking the user to use the :command:`more` command.

.. setting:: debug = no (bool)
    :init:

    Wether to enable debug mode. Mainly consists of printing every message
    received from IRC to standard output. Can be forced on at runtime with
    the ``-d`` switch.


