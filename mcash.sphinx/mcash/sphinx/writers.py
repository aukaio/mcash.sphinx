from sphinx.writers.html import HTMLTranslator


class StrippedHTMLTranslator(HTMLTranslator):
    def visit_table(self, node):
        self.context.append(self.compact_p)
        self.compact_p = True
        classes = ' '.join(['docutils', self.settings.table_style]).strip()
        self.body.append(
            self.starttag(node, 'table', CLASS=classes, border="0", width="100%", cellspacing="0", cellpadding="0"))

    def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
        attributes = {name.lower(): value for name, value in attributes.items()}
        attributes.pop('class', None)
        return HTMLTranslator.starttag(self, node, tagname, suffix, empty, **attributes)

