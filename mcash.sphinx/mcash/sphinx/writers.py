from sphinx.writers.html import HTMLTranslator
from docutils import nodes


replace_classes = {
    'current': 'active',
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
            node['classes'].append('mcash-sub-section')
        else:
            node['classes'].append('mcash-docs-section')
        self.body.append(
            self.starttag(node, 'div'))

    def visit_field_list(self, node):
        self._fieldlist_row_index = 0
        self.context.append((self.compact_field_list, self.compact_p))
        self.compact_p = None
        if 'compact' in node['classes']:
            self.compact_field_list = True
        elif (self.settings.compact_field_lists
              and 'open' not in node['classes']):
            self.compact_field_list = True
        if self.compact_field_list:
            for field in node:
                field_body = field[-1]
                assert isinstance(field_body, nodes.field_body)
                children = [n for n in field_body
                            if not isinstance(n, nodes.Invisible)]
                if not (len(children) == 0 or
                                    len(children) == 1 and
                                isinstance(children[0],
                                           (nodes.paragraph, nodes.line_block))):
                    self.compact_field_list = False
                    break
        self.body.append(self.starttag(node, 'table', frame='void',
                                       CLASS='docutils field-list', border="0", width="100%", cellspacing="0",
                                       cellpadding="0", rules='none',))
        self.body.append('<col class="field-name" />\n'
                         '<col class="field-body" />\n'
                         '<tbody valign="top">\n')

    def starttag(self, node, tagname, suffix='\n', empty=False, **attributes):
        for (name, value) in attributes.items():
            attributes[name.lower()] = value

        classes = attributes.get('class')
        if classes:
            classes = filter(None, map(lambda c: replace_classes.get(c, c), classes.split()))
            attributes['class'] = ' '.join(classes)
        node['classes'] = filter(None, map(lambda c: replace_classes.get(c, c), node['classes']))
        return HTMLTranslator.starttag(self, node, tagname, suffix=suffix, empty=empty, **attributes)
