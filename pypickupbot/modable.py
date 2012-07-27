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
"""module management commands"""

import os.path
import sys
from types import ListType, TupleType, DictType, FunctionType
import inspect

from twisted.python import log
from twisted.plugin import getPlugins, IPlugin
from zope.interface import Interface, implements

from pypickupbot import config

import pypickupbot.modules

class IModuleFactory(Interface):
    """A module that extends a modable"""

    def __call__(bot):
        """returns an instance of the module"""

    def getConfigFile():
        """returns the filename of a possible config file"""

    def getExtensions(module):
        """returns a dict listing all extensions to the modable object"""

class SimpleModuleFactory:
    implements(IModuleFactory, IPlugin)

    def __init__(self, Module):
        self.file = inspect.stack()[1][1]
        self.Module = Module
        self.name = os.path.basename(self.file)[:os.path.basename(self.file).rfind('.')]
        self.post_init()

    def post_init(self):
        """Called at the end of __init__ for subclasses to subclass"""
        pass

    def __call__(self, bot):
        self.pre_inst(self.Module)
        try:
            try:
                getattr(self.Module, '__init__')
            except AttributeError:
                m = self.Module()
            else:
                m = self.Module(bot)
            m.pypickupbot = bot
            self.post_inst(m)
            return m
        except Exception as e:
            log.err()

    def pre_inst(self, M):
        """Called at the beginning of __call__ for subclasses to subclass
        
        :param M: The module class"""
        pass

    def post_inst(self, m):
        """Called at the end of __call__ for subclasses to subclass
        
        :param m: The instancied module"""
        pass
    
    def getConfigFile(self):
        if self.file.endswith('.py'):
            return self.file[:-3] + '.cfg'
        elif self.file.endswith('.pyc'):
            return self.file[:-4] + '.cfg'
        return self.file + '.cfg'

    def getExtensions(self, module):
        for attr in ['commands', 'eventhandlers']:
            try:
                getattr(module, attr)
            except AttributeError:
                setattr(module, attr, {})

        return {
            'commands': module.commands,
            'eventhandlers': module.eventhandlers,
        }

class Modable:
    """Class that can manage modules"""

    EXTEND_DICT = 0
    EXTEND_DICT_LIST = 1

    def load_module_config(self, module):
        if isinstance(module, ListType):
            for module_ in module:
                self.load_module_config(module_)
            return

        if module in self.available_modules:
            if config.debug:
                log.msg('Loading module config %s' % module)
            config._parser.read([self.available_modules[module].getConfigFile()])

    def load(self, module):
        """Load a module or a list of modules"""
        if isinstance(module, ListType):
            success = True
            for module_ in module:
                success = self.load(module_) and success
            return success

        if module not in self.modules:
            if module in self.available_modules:
                if config.debug:
                    log.msg('Loading module %s' % module)
                m = self.available_modules[module](self)
                self.modules[module] = m
                self.module_postload(self.available_modules[module], m)
            else:
                self.preload_modules()
                if module not in self.available_modules:
                    raise ValueError(_("No such module: %s") % module)
                else:
                    self.load(module)

        return self.modules[module]

    def module_postload(self, factory, module):
        """calls loading hooks, imports commands"""

        for extendable in self.__class__._extend:
            try:
                extender = factory.getExtensions(module)[extendable]
            except KeyError:
                pass
            else:
                self.extend(module, extendable, extender)

    def extend(self, module, extendablename, extender):
        """Extends extendablename with extender from module"""
        if extendablename not in self._extend:
            raise ValueError("Unknown extendable: %s" % (extendable,))

        extendable = getattr(self,extendablename)
        extendable_type = self._extend[extendablename]

        for key, val in extender.iteritems():
            try:
                iter(val)
            except TypeError:
                if isinstance(val, classmethod):
                    val = val.__get__(None, module)
                elif type(val) == FunctionType:
                    val = val.__get__(module, module.__class__)
            else:
                is_tuple = False
                is_dict = True
                if TupleType == type(val):
                    is_tuple = True
                    val = list(val)
                if DictType != type(val):
                    is_dict = False
                    val = dict(zip(range(len(val)), val))
                for i, v in val.iteritems():
                    if isinstance(v, classmethod):
                        val[i] = v.__get__(None, module)
                    elif type(v) == FunctionType:
                        val[i] = v.__get__(module, module.__class__)
                if not is_dict:
                    val = val.values()
                if is_tuple:
                    val = tuple(val)
            if extendable_type == self.__class__.EXTEND_DICT:
                extendable[key] = val
            elif extendable_type == self.__class__.EXTEND_DICT_LIST:
                if key in extendable:
                    extendable[key].append(val)
                else:
                    extendable[key] = [val]
        

    def preload_modules(self):
        self.available_modules = {}
        log.msg("Looking for modules...")
        for module in getPlugins(IModuleFactory, pypickupbot.modules):
            self.available_modules[module.name] = module
    def load_modules_config(self):
        """Load modules' defaults"""
        log.msg(_("Loading default module configs..."))
        self.load_module_config(config.getlist('Modules', 'modules'))
    def load_modules(self):
        """Loads modules set in the config"""
        log.msg(_("Loading enabled modules..."))
        self.load(config.getlist('Modules', 'modules'))

