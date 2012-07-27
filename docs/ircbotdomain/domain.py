"""Domain for IRC bot commands and ini config"""

import re

from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.domains import Domain, ObjType, Index
from sphinx.directives import ObjectDescription
from sphinx.roles import XRefRole, xfileref_role
from sphinx import addnodes
from sphinx.util.nodes import make_refnode

commandRegExp = re.compile("!(?P<name>[^ ]+)(?: (?P<args>.*))?")

class IrcBotDescription(ObjectDescription):
    def needs_arglist(self):
        return False

    def add_target_and_index(self, name_cls, sig, signode):
        tgtid = tgtid_ = self.typename.lower()+"-"+name_cls[2].replace(' ', '-')
        n = 0
        while tgtid in self.env.domaindata['ircbot'][self.typename]:
            n += 1
            tgtid = tgtid_ + '-' + str(n)
        signode['ids'].append(tgtid)
        self.env.domaindata['ircbot'][self.typename][tgtid] = \
            (name_cls[1], self.env.docname, signode)

        """indextext = self.get_index_text(signode)
        if indextext:
            self.indexnode['entries'].append(
                (u'single', unicode(indextext), 
                    unicode(name_cls[2]), unicode('!' + name_cls[2])))"""

    def get_index_text(self, signode):
        return signode['name']

class IrcBotCommand(IrcBotDescription):
    typename = "command"

    def handle_signature(self, sig, signode):
        try:
            command, args = commandRegExp.match(sig).groups()
        except AttributeError:
            # Well shit, that wasn't a valid signature
            self.error("Invalid command signature.")
        signode += addnodes.desc_name(command, '!' + command)
        if args and args.strip():
            self.parse_arglist(signode, args)
        signode['typename'] = self.typename
        signode['text'] = sig
        signode['name'] = command
        signode['shortname'] = '!' + command
        signode['arglist'] = args
        try:
            signode['module'] = self.env.temp_data['command_module']
        except KeyError:
            signode['module'] = ''
        signode['index'] = 'noindex' not in self.options
        return (self.typename, sig, command)

    def _fix_paramlist(self, paramlist, do_visit_depart=True):
        """apply custom params to sphinx.addnodes.desc_parameterlists
        
        applies changes on the original but return anyway for ease
        of writing"""
        paramlist.child_text_separator = ' '
        if do_visit_depart:
            paramlist.visit_char = ' '
            paramlist.depart_char = ' '
        return paramlist

    def parse_arglist(self, signode, arglist):
        """parses argument lists
        
        largely imported from sphinx.domains.python,
        changes are mainly to make it work with space-separated
        argument lists and to make it look so"""
        paramlist = self._fix_paramlist(addnodes.desc_parameterlist())
        stack = [paramlist]
        try:
            for argument in arglist.split(' '):
                argument = argument.strip()
                ends_open = ends_close = 0
                while argument.startswith('['):
                    stack.append(
                        self._fix_paramlist(addnodes.desc_optional(), False))
                    stack[-2] += stack[-1]
                    argument = argument[1:].strip()
                while argument.startswith(']'):
                    stack.pop()
                    argument = argument[1:].strip()
                while argument.endswith(']'):
                    ends_close += 1
                    argument = argument[:-1].strip()
                while argument.endswith('['):
                    ends_open += 1
                    argument = argument[:-1].strip()
                if argument:
                    stack[-1] += addnodes.desc_parameter(argument, argument)
                while ends_open:
                    stack.append(
                        self._fix_paramlist(addnodes.desc_optional(), False))
                    stack[-2] += stack[-1]
                    ends_open -= 1
                while ends_close:
                    stack.pop()
                    ends_close -= 1
            if len(stack) != 1:
                raise IndexError
        except IndexError:
            # if there are too few or too many elements on the stack, just give up
            # and treat the whole argument list as one argument, discarding the
            # already partially populated paramlist node
            signode += self._fix_paramlist(addnodes.desc_parameterlist())
            signode[-1] += addnodes.desc_parameter(arglist, arglist)
        else:
            signode += paramlist

settingRe = re.compile(r"^(?:\[([^\]]+)\])?\s*([^=[\]]+)\s*=\s*(.*)\s*\(([^()]+)\)$")

class IrcBotSetting(IrcBotDescription):
    typename = "setting"

    option_spec = {
        'noindex': directives.flag,
        'init': directives.flag,
        }

    def handle_signature(self, sig, signode):
        try:
            section, name, default, typename = settingRe.match(sig).groups()
        except AttributeError: #no match
            self.error("Setting signature doesn't look right.")
        if not section:
            try:
                section = self.env.temp_data['setting_section']
            except KeyError:
                raise self.error("Please specify a section for the setting, either by "
                    +"prefixing the setting with the sections within square brackets([]) "
                    +"or by using the \"section\" directive."
                    )
        name, default, typename = (v.strip() for v in (name, default, typename))
        signode += addnodes.desc_addname(section, '['+section+']')
        signode += addnodes.desc_name(name, name)
        if default == "#REQUIRED":
            signode += addnodes.desc_annotation('', ' (Required)')
        else:
            signode += addnodes.desc_annotation(default, ' = '+default)
        if 'init' in self.options:
            signode += addnodes.desc_annotation('', ' (Must be set in init.cfg)')
        typenode = addnodes.desc_type(typename, '')
        typenode += nodes.Text(' (', ' (')
        typerefnode = self.env.domains[self.domain].roles['type'](
            'type', typename, typename, self.lineno, self.state_machine
            )[0]
        typerefnode[0]['refdomain'] = 'ircbot'
        typenode += typerefnode
        typenode += nodes.Text(')', ')')
        signode += typenode
        signode['index'] = 'noindex' not in self.options
        signode['name'] = name
        signode['shortname'] = name
        signode['section'] = section
        signode['type'] = typename
        signode['default'] = default
        signode['text'] = '[{0}]{1} = {2} ({3})'.format(section, name, default, typename)
        return (self.typename, signode['text'], name)

class IrcBotType(IrcBotDescription):
    typename = "type"

    def handle_signature(self, sig, signode):
        signode += addnodes.desc_name(sig, sig)
        signode['name'] = sig
        signode['shortname'] = sig
        return (self. typename, sig, sig)

class IrcBotValueSetter(Directive):
    has_content = False
    required_arguments = 1
    optional_arguments = 0
    final_argument_whitespace = True
    option_spec = {}

    value = NotImplemented

    def run(self):
        self.state.document.settings.env.\
            temp_data[self.value] = self.arguments[0]
        return []

class IrcBotSectionSetter(IrcBotValueSetter):
    value = 'setting_section'

class IrcBotModuleSetter(IrcBotValueSetter):
    value = 'command_module'

class IrcBotXRefRole(XRefRole):
    
    def __init__(self, typename, titleFactory, **kwargs):
        XRefRole.__init__(self, **kwargs)
        self.typename = typename
        self.titleFactory = titleFactory

    def process_link(self, env, refnode, has_explicit_title, title, target):
        if not has_explicit_title:
            title = self.titleFactory(self, title)
        return title, target

class IrcBotIndex(Index):
    groupduplicates = True

    def generate(self, docnames=None):
        content = {}
        items = self.domain.data[self.domaindata].items()
        items.sort(key=lambda (k, v): k)
        for i, (target, (sig, docname, signode)) in enumerate(items):
            if not signode['index']: continue
            letter = signode['name'][0].upper()
            entries = content.setdefault(letter, [])
            sub = 0
            if self.groupduplicates and \
                    len(items) > 1 and\
                    items[i-1][1][2]['name'] == signode['name']:
                sub = 2
                if entries[-1][1] != 2:
                    prev = entries.pop()
                    entries.append((
                        prev[0],
                        1,
                        prev[2],
                        prev[3],
                        prev[4],
                        prev[5],
                        prev[6]
                        ))
                    entries.append((
                        prev[0],
                        2,
                        prev[2],
                        prev[3],
                        prev[4],
                        prev[5],
                        prev[6]
                        ))

            entries.append(self.entryFactory(sub, target, sig, docname, signode))
        content_ = content.items()
        content_.sort(key=lambda (k, v): k)
        # Take this minute to add a ref to ourselves
        if self.name not in self.domain.env.domaindata['std']['labels']:
            self.domain.env.domaindata['std']['labels'][self.name] = \
                (self.domain.name + '-' + self.name, '', self.localname)
        if self.name not in self.domain.env.domaindata['std']['anonlabels']:
            self.domain.env.domaindata['std']['anonlabels'][self.name] = \
                (self.domain.name + '-' + self.name, '')
        return (content_, True)


class CommandIndex(IrcBotIndex):
    name = "commands"
    localname = "Command Index"
    shortname = "commands"
    domaindata = "command"

    def entryFactory(self, sub, target, sig, docname, signode):
        if signode['arglist']:
            entryname = '!'+signode['name'] \
                + ' ' + signode['arglist']
        else:
            entryname = '!'+signode['name']

        return (
            entryname,
            sub,
            docname,
            target,
            None,
            None,
            signode['module'])

class SettingIndex(IrcBotIndex):
    name = "settings"
    localname = "Settings Index"
    shortname = "settings"
    domaindata = "setting"
    groupduplicates = False

    def entryFactory(self, sub, target, sig, docname, signode):
        entryname = signode['name']
        return (
            signode['name'],
            sub,
            docname,
            target,
            signode['section'],
            signode['type'],
            signode['default'])

class IrcBotDomain(Domain):
    """IRC Bot commands and ini file domain"""

    name="ircbot"
    label="IRC Bot"

    object_types = {
        'setting': ObjType('setting', 'setting', 'obj'),
        'command': ObjType('command', 'command', 'obj'),
        'type': ObjType('setting type', 'type', 'obj'),
        }

    directives = {
        'setting': IrcBotSetting,
        'command': IrcBotCommand,
        'type': IrcBotType,
        'module': IrcBotModuleSetter,
        'section': IrcBotSectionSetter,
        }

    roles = {
        'setting': IrcBotXRefRole('setting', lambda s, t:t),
        'command': IrcBotXRefRole('command', lambda s, t:'!' + t),
        'type': IrcBotXRefRole('type', lambda s, t:t.capitalize()),
        }

    initial_data = {
        'setting': {},
        'command': {},
        'type': {},
        'module': '',
        'section': '',
        }

    indices = [CommandIndex, SettingIndex]

    def clear_doc(self, docname):
        for typ in ('setting', 'command', 'type'):
            delete = []
            for k, v in self.data[typ].iteritems():
                if v[1] == docname:
                    delete.append(k) # can't delete while iterating
            for k in delete:
                del self.data[typ][k]

    def resolve_xref(self, env, fromdocname, builder, typ, target, node, contnode):
        if typ in ('setting', 'command', 'type'):
            target = target.replace(' ', '-')
            if typ + '-' + target in self.data[typ]:
                tgtnode = self.data[typ][typ + '-' + target]
                return make_refnode(builder, fromdocname, tgtnode[1],
                    typ + '-' + target, contnode, tgtnode[0])
        return None

    def get_objects(self):
        return list((
            (
                signode['shortname'],
                disp,
                typename,
                docname,
                anchor,
                1
            )
            for typename in ('command', 'setting', 'type')
            for anchor, (disp, docname, signode) in self.data[typename].iteritems()))

