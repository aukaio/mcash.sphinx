"""
This Sphinx extension displays WTForms with fields
"""
import inspect
from docutils import nodes
from sphinx.util.compat import Directive
from sphinx.util.docstrings import prepare_docstring

from mcash.utils import import_obj
from mcash.core.forms.form import Form
from mcash.sphinx import utils
fields = import_obj('wtforms.fields')


def range_string_builder(var_name):
    def build_string(v):
        if v.min == v.max:
            s = '{var_name} == {max}'
        else:
            s = ''
            if v.min > -1:
                s += '{min} <= '
            s += '{var_name}'
            if v.max > -1:
                s += ' <= {max}'
        return s.format(min=v.min, max=v.max, var_name=var_name)
    return build_string


field_type_map = {
    getattr(fields, name): name[:-5].lower() for name in (
        'DecimalField', 'DateField', 'DateTimeField', 'FloatField', 'IntegerField', 'StringField', 'BooleanField',
    )
}


def get_field_type(field):
    if not inspect.isclass(field):
        field = type(field)
    serialized_type = getattr(field, 'serialized_type', None)
    if serialized_type is not None:
        field = serialized_type
    for cls in field.mro():
        if cls in field_type_map:
            return field_type_map[cls]
    return 'Unknown'


validator_processors = {
    'wtforms.validators.AnyOf': lambda v: 'Value in %s' % v.values_formatter(v.values),
    'wtforms.validators.DataRequired': lambda v: 'Data required (new or existing on update)',
    'wtforms.validators.Email': lambda v: 'Email (regexp: %s)' % v.regex.pattern,
    'wtforms.validators.EqualTo': lambda v: 'value == value of %s' % v.fieldname,
    'wtforms.validators.InputRequired': lambda v: 'Input required',
    'wtforms.validators.IPAddress': lambda v: 'IP address v4:%s v6:%s' % (v.ipv4, v.ipv6),
    'wtforms.validators.MacAddress': lambda v: 'Valid MAC address',
    'wtforms.validators.NoneOf': lambda v: 'Value not in %s' % v.values_formatter(v.values),
    'wtforms.validators.NumberRange': range_string_builder('value'),
    'wtforms.validators.Length': range_string_builder('length'),
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
    show_form_name = False


    def run(self):
        # This starts processing and delegates to specific and generic process methods for forms and fields
        obj_path = self.content[0]
        formclass = import_obj(obj_path)

        root = nodes.definition_list()
        module, classname = obj_path.rsplit('.', 1)
        if self.show_form_name:
            root.append(nodes.term(
                None,
                '',
                nodes.emphasis(text='Form '),
                nodes.literal(text='%s.' % module),
                nodes.strong(text=classname)))

        env = self.state.document.settings.env
        form_fields = env.wtforms_form_fields = getattr(env, 'wtforms_form_fields', [])
        FormProcessor(form_fields=form_fields).process_form(formclass, root)

        print form_fields
        return [root]


class form_fields_node(nodes.General, nodes.Element):
    pass


class FormFieldsDirective(Directive):
    has_content = True

    def run(self):
        return [form_fields_node()]


def process_form_field_nodes(app, doctree, fromdocname):
    env = app.builder.env
    form_processor = FormProcessor([])

    for node in doctree.traverse(form_fields_node):
        content = []
        for form in getattr(env, 'wtforms_form_fields', ()):
            form = utils.import_obj(form)
            content.append(nodes.subtitle('', form.__name__))
            form_processor.process_form(form, content)
        node.replace_self(content)


class FormProcessor(object):
    def __init__(self, form_fields):
        self.form_fields = form_fields

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

    def extract_field_properties(self, field, field_list=False):
        return {
            'default': field.default,
            'description': field.description if field.description else field.label.text,
            'widget': field.__class__.__name__,
            'validators': self.process_validators(field),
        }

    def make_definition_list(self, parent, term, definition=None, classifier=None):
        left_cell, right_cell = self.prepare_cells(parent)
        if not isinstance(term, nodes.Node):
            term = nodes.strong(text=term)
        left_cell.append(term)
        if classifier is not None:
            left_cell.append(nodes.classifier(text=classifier))
        if definition is not None:
            required = definition.get('required', False)
            left_cell.append(nodes.classifier('', 'required' if required else 'optional'))
            defs = []
            if not required and 'default' in definition:
                left_cell.append(nodes.classifier('', definition['default']))
            if 'validators' in definition:
                defs.extend(definition['validators'])
            left_cell.extend(nodes.paragraph('', d) if not isinstance(d, nodes.Node) else d for d in defs)
            right_cell.append(nodes.paragraph('', '\n'.join(prepare_docstring(definition['description']))))
        return left_cell, right_cell

    def process_field_generic(self, field, parent):
        properties = self.extract_field_properties(field)
        self.make_definition_list(
            parent,
            term=field.name,
            definition=properties,
            classifier=get_field_type(field),
            )

    def process_field_FieldList(self, field, parent):
        subfield = field.unbound_field.bind(form=None, name=field.name, prefix='')
        subfield.name = '%s[]' % subfield.name
        subfield.label = field.label
        self.process_field_delegate(subfield, parent)

    def process_field_FormField(self, field, parent):
        self.process_field_generic(field, parent)
        self.form_fields.append(utils.get_import_path(field.form_class))

    def process_field_delegate(self, field, parent):
        if getattr(field.__class__, 'model_helper', False):  # Avoid recursion on FormField
            pass
            # Try specific process first, then generic process
        if isinstance(field, fields.FormField):
            process_field_method = self.process_field_FormField
        else:
            process_field_method = getattr(self, 'process_field_%s' % field.type, getattr(self, 'process_field_generic'))
        process_field_method(field, parent)

    def prepare_table(self, parent):
        tbody = nodes.tbody(
            '',
            )
        table = nodes.table(
            '',
            nodes.tgroup(
                '',
                nodes.colspec(colwidth=1, classes=['foo-raw']),
                nodes.colspec(colwidth=1),
                tbody,
                ),
            classes=['foo']
        )
        parent.append(table)
        return tbody

    def prepare_cells(self, parent):
        left_cell, right_cell = nodes.entry(), nodes.entry()
        row = nodes.row('', left_cell, right_cell)
        parent.append(row)
        return left_cell, right_cell

    def process_form(self, formclass, parent):
        assert issubclass(formclass, Form)
        fields = self.prepare_table(parent)
        forminstance = formclass()

        for field in forminstance:
            if field.name == 'link':
                continue
            self.process_field_delegate(field, fields)


def setup(app):
    app.add_directive('wtforms', WTFormsDirective)
    app.add_directive('formfields', FormFieldsDirective)
    app.connect('doctree-resolved', process_form_field_nodes)
