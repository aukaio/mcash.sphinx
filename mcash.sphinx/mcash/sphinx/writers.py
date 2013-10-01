from sphinx.writers.html import HTMLTranslator


class StrippedHTMLTranslator(HTMLTranslator):
    def visit_table(self, node):
        self.context.append(self.compact_p)
        self.compact_p = True
        classes = 'table table-striped'
        self.body.append(
            self.starttag(node, 'table', CLASS=classes, border="0", width="100%", cellspacing="0", cellpadding="0"))
