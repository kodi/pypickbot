from docutils import nodes
from sphinx.util import rpartition
from sphinx import addnodes

# HTMLTranslator
def visit_desc_parameterlist(self, node):
    self.body.append('<big>' + node.visit_char + '</big>')
    self.first_param = 1
    self.param_separator = node.child_text_separator

def depart_desc_parameterlist(self, node):
    self.body.append('<big>' + node.depart_char + '</big>')

def visit_desc_optional(self, node):
    if not self.first_param:
        self.body.append(self.param_separator)
    self.body.append('<span class="optional">[</span>')
    self.first_param = 1
    self.param_separator = node.child_text_separator

def depart_desc_optional(self, node):
    self.body.append('<span class="optional">]</span>')
    self.first_param = 0

# sphinx.addnodes
class desc_parameterlist(addnodes.desc_parameterlist):
    """Node for a general parameter list."""
    visit_char = '('
    depart_char = ')'

def visit_desc_parameter(self, node):
    if not self.first_param:
        self.body.append(self.param_separator)
    else:
        self.first_param = 0
    if not node.hasattr('noemph'):
        self.body.append('<em>')

#sphinx.search
def get_objects(self, fn2index):
    rv = {}
    otypes = self._objtypes
    onames = self._objnames
    for domainname, domain in self.env.domains.iteritems():
        for fullname, dispname, type, docname, anchor, prio in \
                domain.get_objects():
            # XXX use dispname?
            if docname not in fn2index:
                continue
            if prio < 0:
                continue
            # XXX splitting at dot is kind of Python specific
            prefix, name = rpartition(fullname, '.')
            pdict = rv.setdefault(prefix, {})
            try:
                i = otypes[domainname, type]
            except KeyError:
                i = len(otypes)
                otypes[domainname, type] = i
                otype = domain.object_types.get(type)
                if otype:
                    # use unicode() to fire translation proxies
                    onames[i] = unicode(domain.get_type_name(otype))
                else:
                    onames[i] = type
            pdict[name] = (fn2index[docname], i, prio, dispname, anchor)
    return rv

