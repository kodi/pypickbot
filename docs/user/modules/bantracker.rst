.. _plugin-bantracker:

*****************************************
``ban``: Enhanced banmask tracking
*****************************************

All commands described here are only available to bot admins. :command:`ban` and :command:`unban` are only enabled once the bot is a channel operator.

Creating bans
=============

.. module:: ban

.. command::
    !ban subject [duration] [reason]

    Creates a ban on subject for the given duration and reason and kicks
    anyone who matches the created ban.
    
    See the :type:`duration` type for the *duration* option. *reason*
    can be anything. It will show in the banlist and in the kick message(s)
    if applicable.

    The bot will do its best to find out the correct
    hostmask to ban:
    
    * If *subject* is a full hostmask and contains wildcards like ``*``,
      the bot will create a ban on that hostmask.
    * If *subject* is a full hostmask and contains no wildcards,
      the bot will apply a wildcard on the username part 
      and another on the ident part if no identd authentified it(``~``),
      leaving just the host part, sometimes with the identd.
    * If *subject* is the nickname of someone present in the channel, 
      the bot will select the user's full hostmask and run the
      transformation above.
    * If not, it creates a ban on the nickname itself (ie. ``nick!*@*``).
    
    Some examples:

    ``!ban paul 5d ragequitter``
        * If paul is present in the channel, it will do a host/ip ban on
          him.
        * If paul is not present in the channel, the bot will create a
          ban on ``paul!*@*``, meaning that nobody with the nickname
          paul can enter the channel. However, an offending user can
          circumvent this ban simply by changing nickname.
        
        In both cases, the ban will stand for 5 days and have *ragequitter*
        as reason.

    ``!ban paul!*@* 5d ragequitter``
        Forces a nickname ban regardless of whether paul is online or not.

    ``!ban roger!~rfeder@1.2.3.4 5d too good for us``
        Creates a ban on ``*!*@1.2.3.4``.

    ``!ban frank!feinst@4.3.2.1 5d aimbotter``
        Creates a ban on ``*!feinst@4.3.2.1``.

    ``!ban *!*@225.70.*``
        Creates a ban on ``*!*@225.70.*``. (IP range ban from
        ``225.70.0.0`` to ``225.70.255.255``)

.. command::
    !ban

    Bans the last kicked person for the :setting:`default duration` with
    the kick message as the reason.

Searching bans
==============

.. command::
    !banlist
    !banlist #id
    !banlist search

    Show active or recently expired bans.

    If search is provided, the bot will search against all data on the
    bans. Also, if you provide a hostmask as search text, it will be
    matched against existing banmasks. Useful if you know someone's
    hostmask and want too know why they are banned.

    If the search returns only one result (for instance if you used the
    *#id* form), all details will be shown, including the ban reason.

.. command::
    !banhistory [search|#id]

    Show expired bans.

Editing bans
============

.. command::
    !unban search|#id

    Lifts a ban. Use a hostmask as search to your advantage here.

.. command::
    !ban search|#id [duration] [reason]

    Edits a ban.


Configuration
=============

.. section:: Ban

.. setting:: default duration = permanent (duration)

    Default duration for bans in case it isn't specified.

.. setting:: keep expired bans for = 1 week (duration)

    Purge the database of bans which expired more than this time ago.

.. setting:: check interval = 2 min (duration)
    
    Interval between two of the bot's periodic checks on bans to lift.
    You don't really need to touch it.

