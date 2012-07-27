.. _user-server:

*******************
Connection settings
*******************

Defining a server
=================

.. section:: Server

.. setting:: host = #REQUIRED (string)
    :init:

    The IRC host to connect to.

.. setting:: port = 6667 (int)
    :init:

    The port to connect to.

.. setting:: ssl = no (bool)
    :init:

    Use SSL? Don't forget to adjust the port if you do.

.. setting:: username = (string)
    :init:

    Username when connecting. (**Not** the nickname.)

.. setting:: password = (string)
    :init:

    Password when connecting.

.. setting:: realname = (string)
    :init:

    ``ircname``/``realname`` to appear when people ``/whois`` the bot.

.. setting:: channels = #REQUIRED (list)
    :init:

    What channels to join? (Currently limited to one)

.. setting:: channel passwords = (dict)
    :init:

    Channel passwords in ``channel: password`` format, if needed.

The bot's nickname is defined :setting:`in the Bot section<nickname>`

Howto
=====

Username/Password authentication
--------------------------------

.. highlight:: ini

Some servers allow you to authenticate using user/password at connect time.
This is the case of most bouncer software and of FreeNode's NickServ::

    [Server]

    username=username
    password=secret

Q Authentication
----------------

See :ref:`plugin-q_auth` after adding ``q_auth`` to your :setting:`module
list<modules>`.
