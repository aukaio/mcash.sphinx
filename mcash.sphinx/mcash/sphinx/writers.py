from sphinx.writers.html import HTMLTranslator


replace_classes = {
    'section': 'mcash-docs-section',
    'sub-section': 'mcash-sub-section',
}


class StrippedHTMLTranslator(HTMLTranslator):
    def visit_table(self, node):
        self.context.append(self.compact_p)
        self.compact_p = True
        classes = 'table table-striped'
        self.body.append(
            self.starttag(node, 'table', CLASS=classes, border="0", width="100%", cellspacing="0", cellpadding="0"))

    def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
        for (name, value) in attributes.items():
            attributes[name.lower()] = value

        classes = attributes.get('class')
        if classes:
            classes = filter(None, map(lambda c: replace_classes.get(c, c), classes.split()))
            attributes['class'] = ' '.join(classes)
        return HTMLTranslator.starttag(self, node, tagname, suffix=suffix, empty=empty, **attributes)

