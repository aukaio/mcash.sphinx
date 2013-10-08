from sphinx.writers.html import HTMLTranslator


replace_classes = {
}


class McashHTMLTranslator(HTMLTranslator):
    def visit_table(self, node):
        self.context.append(self.compact_p)
        self.compact_p = True
        classes = 'table table-striped'
        self.body.append(
            self.starttag(node, 'table', CLASS=classes, border="0", width="100%", cellspacing="0", cellpadding="0"))

    def visit_section(self, node):
        self.section_level += 1
        if self.section_level > 1:
            c = 'mcash-docs-section'
        else:
            c = 'mcash-sub-section'
        self.body.append(
            self.starttag(node, 'div', CLASS=c))

    def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
        for (name, value) in attributes.items():
            attributes[name.lower()] = value

        classes = attributes.get('class')
        if classes:
            classes = filter(None, map(lambda c: replace_classes.get(c, c), classes.split()))
            attributes['class'] = ' '.join(classes)
        return HTMLTranslator.starttag(self, node, tagname, suffix=suffix, empty=empty, **attributes)

