"""
This Sphinx extension displays WTForms with fields
"""
from docutils import nodes
from sphinx.util.compat import Directive

from mcash.utils import import_obj
from mcash.core.forms.form import Form


validator_processors = {
    'wtforms.validators.AnyOf': lambda v: 'Value in %s' % v.values_formatter(v.values),
    'wtforms.validators.DataRequired': lambda v: 'Data required (new or existing on update)',
    'wtforms.validators.Email': lambda v: 'Email (regexp: %s)' % v.regex.pattern,
    'wtforms.validators.EqualTo': lambda v: 'value == value of %s' % v.fieldname,
    'wtforms.validators.InputRequired': lambda v: 'Input required',
    'wtforms.validators.IPAddress': lambda v: 'IP address v4:%s v6:%s' % (v.ipv4, v.ipv6),
    'wtforms.validators.MacAddress': lambda v: 'Valid MAC address',
    'wtforms.validators.NoneOf': lambda v: 'Value not in %s' % v.values_formatter(v.values),
    'wtforms.validators.NumberRange': lambda v: '%s <= value <= %s' % (v.min, v.max),
    'wtforms.validators.Length': lambda v: '%s < len(value) < %s' % (v.min, v.max),
    'wtforms.validators.Optional': lambda v: 'Optional (stops validation if missing)',
    'wtforms.validators.Regexp': lambda v: 'Regexp: %s' % v.regex.pattern,
    'wtforms.validators.Required': lambda v: 'Data required (new or existing on update)',
    'wtforms.validators.URL': lambda v: 'URL (regexp: %s)' % v.regex.pattern,
    'wtforms.validators.UUID': lambda v: 'UUID (regexp: %s)' % v.regex.pattern,
}


class WTFormsDirective(Directive):
    # This should be written as a walker that emits events which in turn
    # create corresponding docutils nodes, as the form tree and doc tree are
    # equivalent
    has_content = True

    def make_field(self, name, body):
        if not isinstance(body, nodes.Node):
            body = nodes.paragraph(text=body)
        return nodes.field(
            '',
            nodes.field_name(text=name),
            nodes.field_body('', body))

    def make_field_list(self, iterable):
        if isinstance(iterable, dict):
            iterable = iterable.items()
        field_list_node = nodes.field_list()
        field_list_node.extend([self.make_field(k, v) for k, v in iterable])
        return field_list_node

    def process_validators(self, field):
        validators = nodes.enumerated_list()
        for v in field.validators:
            vp_key = '%s.%s' % (v.__class__.__module__, v.__class__.__name__)
            vp = validator_processors.get(vp_key, None)
            if vp:
                validators.append(nodes.list_item('', nodes.paragraph(text=vp(v))))
        return validators

    def extract_field_properties(self, field, field_list=True):
        copy = ('default', 'description')
        properties = []
        for attr in copy:
            if hasattr(field, attr):
                properties.append((attr, getattr(field, attr, '')))
        properties.append(('widget', field.widget.__class__.__name__))
        properties.append(('label', field.label.text))
        for k, v in field.flags.__dict__.items():
            properties.append((k, v))
        properties.append(('validators', self.process_validators(field)))
        if field_list:
            return self.make_field_list(properties)
        return properties

    def make_definition_list(self, term, definition=None, classifier=None):
        definition_list = nodes.definition_list_item()
        if not isinstance(term, nodes.Node):
            term = nodes.strong(text=term)
        definition_list.append(term)
        if classifier is not None:
            definition_list.append(nodes.classifier(text=classifier))
        if definition is not None:
            if isinstance(definition, (list, tuple)):
                definition_list.append(nodes.definition('', *definition))
            else:
                definition_list.append(nodes.definition('', definition))

        return definition_list

    def process_field_generic(self, field, parent):
        properties = self.extract_field_properties(field)
        parent.append(
            self.make_definition_list(
                term=field.name,
                definition=properties,
                classifier=field.type,
            )
        )

    def process_field_FieldList(self, field, parent):
        subfield = field.unbound_field.bind(form=None, name=field.name, prefix='')
        subfield.name = '%s[]' % subfield.name
        subfield.label = field.label
        self.process_field_delegate(subfield, parent)

    def process_field_FormField(self, field, parent):
        definition_list = self.make_definition_list(
            term=field.name,
            classifier=field.type,
        )

        self.process_form(field.form_class, definition_list)

        parent.append(definition_list)

    def process_field_delegate(self, field, parent):
        if getattr(field.__class__, 'model_helper', False):  # Avoid recursion on FormField
            return
        # Try specific process first, then generic process
        process_field_method = getattr(self, 'process_field_%s' % field.type, getattr(self, 'process_field_generic'))
        process_field_method(field, parent)

    def process_form(self, formclass, parent):
        assert issubclass(formclass, Form)
        fields = nodes.definition_list()
        parent.append(nodes.definition('', fields))
        forminstance = formclass()

        for field in forminstance:
            self.process_field_delegate(field, fields)

    def run(self):
        # This starts processing and delegates to specific and generic process methods for forms and fields
        obj_path = self.content[0]
        formclass = import_obj(obj_path)

        root = nodes.definition_list()
        module, classname = obj_path.rsplit('.', 1)
        root.append(nodes.term(
            None,
            '',
            nodes.emphasis(text='Form '),
            nodes.literal(text='%s.' % module),
            nodes.strong(text=classname)))

        self.process_form(formclass, root)

        return [root]


def setup(app):
    app.add_directive('wtforms', WTFormsDirective)
