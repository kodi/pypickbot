.. _plugin-q_auth:

****************************
``q_auth``: Q authentication
****************************

When this module is enabled, the bot will do QuakeNet-style Q auth
before joining channels.

Configuration
=============

.. section:: Q Auth

.. setting:: username = #REQUIRED (string)

    Your Q username, like in

    ``/msg Q@CServe.quakenet.org AUTH username password``

.. setting:: password = #REQUIRED (string)

    Your Q password.

.. setting:: Q username = Q!TheQBot@CServe.quakenet.org (string)

    The username to message the auth command to. The default suits
    QuakeNet, if you are on another network that uses Q, change this.

