# pypickupbot - An ircbot that helps game players to play organized games
#               with captain-picked teams.
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

"""Persistent data access."""

import os.path

from twisted.enterprise import adbapi

class DBs:
    db = None

    @classmethod
    def load_db(cls, configdir=None, dbfile=None):
        if dbfile != None:
            cls.db = adbapi.ConnectionPool("sqlite3", dbfile, check_same_thread=False)
        else:
            if configdir != None:
                cls.db = adbapi.ConnectionPool("sqlite3",
                    os.path.join(configdir, "db.sqlite"), check_same_thread=False)
            else:
                cls.db = adbapi.ConnectionPool("sqlite3", "db.sqlite", check_same_thread=False)

        cls._db_postload()
    
    @classmethod
    def _db_postload(cls):
        cls.db.runOperation("""
            CREATE TABLE IF NOT EXISTS
            meta
            (
                key     TEXT UNIQUE,
                val     TEXT
            )
            """)
    

def runInteraction(*args, **kwargs):
    return DBs.db.runInteraction(*args, **kwargs)

def runQuery(*args, **kwargs):
    return DBs.db.runQuery(*args, **kwargs)

def runOperation(*args, **kwargs):
    return DBs.db.runOperation(*args, **kwargs)

