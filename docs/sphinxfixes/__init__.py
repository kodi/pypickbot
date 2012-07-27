def setup(app):
    import sphinx.writers.html as htmlwriter
    from sphinx import addnodes
    from sphinx import search

    from sphinxfixes.fixes import visit_desc_parameterlist, \
        depart_desc_parameterlist, visit_desc_optional, \
        visit_desc_parameter, desc_parameterlist, get_objects

    htmlwriter.HTMLTranslator.visit_desc_parameterlist = visit_desc_parameterlist
    htmlwriter.HTMLTranslator.depart_desc_parameterlist = \
        depart_desc_parameterlist
    htmlwriter.HTMLTranslator.visit_desc_optional = visit_desc_optional
    htmlwriter.HTMLTranslator.visit_desc_parameter = visit_desc_parameter
    addnodes.desc_parameterlist = desc_parameterlist
    search.IndexBuilder.get_objects = get_objects

