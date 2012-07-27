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

"""the help command"""

from pypickupbot.modable import SimpleModuleFactory
from pypickupbot.irc import COMMAND
from pypickupbot import config

class HelpPlugin:

    def help(self, call, args):
        """!help <command>
        
        Gives help on a particular command. Try !commands for a list of
        commands."""

        if len(args) != 1:
            return self.help(call, ['help'])

        cmd = args[0]
        if cmd.startswith(config.get('Bot', 'command prefix')):
            cmd = cmd[len(config.get('Bot', 'command prefix')):]

        if cmd not in self.pypickupbot.commands:
            call.reply(_("Unknown command: %s") % args[0])
            return

        try:
            docstring = getattr(
                self.pypickupbot.commands[cmd][0].im_self,
                self.pypickupbot.commands[cmd][0].__name__ + '_doc'
                )
        except AttributeError:
            docstring = None

        if docstring == None:
            docstring = self.pypickupbot.commands[cmd][0].__doc__

        if docstring == None:
            call.reply(_("No help available for %s") % cmd)
            return

        docstring = '\n'.join([s.lstrip() for s in docstring.split('\n')])

        command, helpstring = docstring.split('\n\n', 1)

        if command[0] == '!':
            command = config.get('Bot', 'command prefix') + command[1:]

        helpstring = helpstring.replace('\n', ' ')

        commandflags = self.pypickupbot.commands[cmd][1]
        commandinfo = []
        if commandflags & COMMAND.NOT_FROM_CHANNEL:
            commandinfo.append(_("not from channel"))
        if commandflags & COMMAND.NOT_FROM_PM:
            commandinfo.append(_("not from PM"))
#        if commandflags & COMMAND.ON_MESSAGE:
#            commandinfo.append(_(""))
        if commandflags & COMMAND.ADMIN:
            commandinfo.append(_("admin command"))

        if len(commandinfo):
            call.reply('\x02'+command+'\x02\x0315'
                     + '('+', '.join(commandinfo)+')\x0f: '
                     + helpstring )
        else:
            call.reply('\x02'+command+'\x02: '
                     + helpstring )

    def commands(self, call, args):
        """!commands
        
        Lists all commands"""
        call.reply(_("All commands:") +' '+ ', '.join(sorted(self.pypickupbot.commands.keys())), ', ')

    commands = {
        'help': (help, 0),
        'commands': (commands, 0),
        }

help = SimpleModuleFactory(HelpPlugin)
