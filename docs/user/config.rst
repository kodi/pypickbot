.. _user-config:

******************************
Configuration files and syntax
******************************

.. highlight:: ini

Configuration files
===================

PyPickupBot's configuration is done via a pair of configuration files,
``init.cfg`` and ``config.cfg``. They follow INI syntax: Each setting is defined
by a line such as ``name=value``. Settings have to be grouped under sections, which
are defined by a line with the section's name in square brackets. Here's an example::

    [First section]
    setting 1=1st value

    [Second section]
    setting 2=2nd value
    setting 3=3rd value

.. index:: single: init.cfg

init.cfg
""""""""

``init.cfg`` is read right the moment PyPickupBot is started. It contains start-critical
information such as connection details and the list of modules to load.

.. index:: single: config.cfg

config.cfg
""""""""""

``config.cfg`` is read right before modules are loaded, but after each module's
default settings. This is where you should keep your module settings.

Settings in this manual
=======================

In this manual, for the sake of concise-ness, settings appear with their appropriate
section on the same line. (Normally the section would appear on it's own line and only
once.) If a setting is optional, the default value will be shown after the ``=`` sign:

.. setting:: [Example Section]Example setting = no (bool)
    :noindex:

    ``Example setting``'s default value is ``no``, you are not forced to have it in
    your config unless that value doesn't suit your needs.

For settings that are required, no default value is provided and *Required* appears
next to it.

.. setting:: [Example Section]Required setting = #REQUIRED (int)
    :noindex:

    This setting is required.

If a setting is needed at start and needs to be put in ``init.cfg``, it will appear
like this:

.. setting:: [Server]host = #REQUIRED (string)
    :noindex:
    :init:

    This setting must appear in ``init.cfg``.

For non-required settings:

.. setting:: [Server]port = 6667 (int)
    :noindex:
    :init:

    This setting must appear in ``init.cfg`` if you need to change it.

In parenthesis is the type of value the setting requires. The next section will
describe each of them briefly, and you can access each type's description by clicking
it in the setting's signature.

For a quick reference of all settings, you can visit the :ref:`setting index<settings>`,
which is also accessible from every page of this manual in the top and bottom
right-hand corners.

Setting types
=============

.. type:: bool

    Can be ``yes`` or ``no``, or any equivalent.

.. type:: int

    An integer, like ``0``, ``3`` or ``140``.

.. type:: float

    A floating point number, like ``0.5`` or ``5.3``

.. type:: string

    Text.

.. type:: list

    A space or comma-separated list.

    ::

        modules=pickup help
        teamnames=Team 1, Team 2, Team 3

    You can also extend a list *once* by defining a ``+`` setting.
    For instance::

        modules=pickup help
        modules+=ban pickup_playertracking

    is equivalent to::

        modules=pickup help ban pickup_playertracking

    You can also remove items with ``-``::

        modules=pickup help q_auth ban
        modules-=q_auth ban

    Alternatively, you can use the one-item-per-line style::

        modules[]=5
        modules[0]=pickup
        modules[1]=help
        modules[2]=q_auth
        modules[3]=ban
        modules[4]=pickup_playertracking

    The ``[]`` entry tells the number of items in the list, each ``[n]``
    line defines one item.

.. type:: dict

    Same as a :type:`list`, except that each entry is in the form of
    ``key:value``::

        channel passwords=#priv1:secret,#worldgov:topsecret

    Each key must be unique.

.. type:: duration

    A duration, expressed in a format like ``1 day 2 hours`` or ``1d2h``.

    Each duration string is composed of one or more number/unit pairs.
    Units are, along with their short name:

    * ``years`` (``y``, 365 days)
    * ``months`` (``mo``, 30 days)
    * ``weeks`` (``w``)
    * ``days`` (``d``)
    * ``hours`` (``h``)
    * ``minutes`` (``m``)
    * ``seconds`` (``s``)

    One pair could be something like ``5 days``. Different pairs can be separated by
    a comma and/or a space. All spaces and commas can be safely removed. Most commands
    which use the same format as this will require you to use the compact format
    (no spaces, no commas).

    Some examples and their short forms:

    * ``1 year``: ``1y``
    * ``3 months``: ``3mo``
    * ``10 minutes``: ``10m``
    * ``2 hours, 30 minutes``: ``2h30m``

