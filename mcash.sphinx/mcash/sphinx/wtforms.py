"""
This Sphinx extension displays WTForms with fields
"""
import inspect
from docutils import nodes
from sphinx.util.compat import Directive
from sphinx.util.docstrings import prepare_docstring
from docutils.statemachine import ViewList

from mcash.utils import import_obj
from mcash.utils import json
from mcash.core.forms.form import Form
from mcash.sphinx import utils
fields = import_obj('wtforms.fields')


class form_fields_node(nodes.General, nodes.Element):
    pass


class field_type_node(nodes.General, nodes.Element):
    pass


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
    serialized_type = getattr(field, 'serialized_type', None)
    if isinstance(serialized_type, basestring):
        return serialized_type
    if serialized_type is not None:
        return get_field_type(serialized_type)
    if isinstance(field, fields.FormField):
        field_type = get_field_type(type(field).mro()[1])
        if field_type is None:
            return field.form_class.__name__.rstrip('Form')
        return field_type
    if not inspect.isclass(field):
        field = type(field)
    if len(field.mro()) > 1:
        cls = field.mro()[1]
        if cls in field_type_map:
            return field_type_map[cls]
        return get_field_type(cls)
    return None


def get_validator_description(validator, default=None):
    description = getattr(validator, 'description', None)
    if description is not None:
        return description
    for cls in type(validator).mro():
        vp_key = '%s.%s' % (cls.__module__, cls.__name__)
        vp = validator_processors.get(vp_key, None)
        if vp is not None:
            return vp(validator)
    return type(validator).__name__


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
    'wtforms.validators.Optional': lambda v: 'Optional',
    'wtforms.validators.Regexp': lambda v: 'Regexp: %s' % v.regex.pattern,
    'wtforms.validators.Required': lambda v: 'Data required (new or existing on update)',
    'wtforms.validators.URL': lambda v: 'URL',
    'wtforms.validators.UUID': lambda v: 'UUID (regexp: %s)' % v.regex.pattern,
    'mcash.core.forms.validators.NetmaskValidator': lambda v: 'Valid netmask IP v %s' % (v.version or '4 and 6'),
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
        self.form_fields = env.wtforms_form_fields = getattr(env, 'wtforms_form_fields', {})
        self.process_form(formclass, root)

        return [root]

    def process_validators(self, field):
        validators = []
        for v in field.validators:
            description = get_validator_description(v)
            li = nodes.list_item()
            result = ViewList(prepare_docstring(description))
            self.state.nested_parse(result, 1, li)
            validators.append(li)
        return validators

    def process_field_desscription(self, description, parent):
        description = ViewList(
            prepare_docstring(
                description
            )
        )
        self.state.nested_parse(description, 0, parent)


    def extract_field_properties(self, field, field_list=False):
        return {
            'default': field.default,
            'widget': field.__class__.__name__,
            'validators': self.process_validators(field),
            'required': field.flags.required,
            'description': field.description if field.description else field.label.text,
        }

    def make_field_definition(self, parent, field_name, field_type, **properties):
        specs_cell, description_cell = self.prepare_cells(parent)
        if not isinstance(field_name, nodes.Node):
            field_name = nodes.strong(text=field_name)
        specs_cell.append(field_name)
        specs_cell.append(field_type_node('', nodes.Text(field_type)))

        required = properties['required']
        specs_cell.append(nodes.classifier('', 'required' if required else 'optional'))
        if not required and 'default' in properties:
            specs_cell.append(nodes.classifier('', 'default=%s' % json.dumps(properties['default'])))
        if 'validators' in properties:
            specs_cell.append(nodes.bullet_list('', *properties['validators']))
        self.process_field_desscription(properties['description'], description_cell)
        return specs_cell, description_cell

    def process_field_generic(self, field, parent):
        properties = self.extract_field_properties(field)
        return self.make_field_definition(
            parent,
            field_name=field.name,
            field_type=get_field_type(field),
            **properties
        )

    def process_field_FieldList(self, field, parent):
        subfield = field.unbound_field.bind(form=None, name=field.name, prefix='')
        subfield.name = '%s[]' % subfield.name
        subfield.label = field.label
        self.process_field_delegate(subfield, parent)

    def process_field_FormField(self, field, parent):
        env = self.state.document.settings.env
        left_cell, right_cell = self.process_field_generic(field, parent)
        form_path = utils.get_import_path(field.form_class)
        for node in left_cell.traverse(field_type_node):
            if form_path not in self.form_fields:
                result = []
                self.process_form(field.form_class, result)
                self.form_fields[form_path] = {
                    'doc': result,
                    'name': get_field_type(field),
                    'target_id': "wtforms-formfield-%d" % env.new_serialno('wtforms-formfield')
                }
            node['form_path'] = form_path

    def process_field_delegate(self, field, parent):
        if getattr(field.__class__, 'model_helper', False):  # Avoid recursion on FormField
            pass
            # Try specific process first, then generic process
        if isinstance(field, fields.FormField):
            process_field_method = self.process_field_FormField
        else:
            process_field_method = getattr(
                self, 'process_field_%s' % field.type, getattr(self, 'process_field_generic'))
        process_field_method(field, parent)

    def prepare_table(self, parent):
        tbody = nodes.tbody(
            '',
        )
        table = nodes.table(
            '',
            nodes.tgroup(
                '',
                nodes.colspec(colwidth=1),
                nodes.colspec(colwidth=1),
                tbody,
            ),
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
        self.state.nested_parse(ViewList(utils.get_doc(formclass)), 0, parent)
        fields = self.prepare_table(parent)
        forminstance = formclass()

        for field in forminstance:
            if field.name == 'link':
                continue
            self.process_field_delegate(field, fields)


class FormFieldsDirective(Directive):
    has_content = True

    def run(self):
        return [form_fields_node()]


def process_form_field_nodes(app, doctree):
    env = app.builder.env
    for node in doctree.traverse(form_fields_node):
        content = []
        for form_path, form_info in getattr(env, 'wtforms_form_fields', {}).items():
            content.append(nodes.subtitle('', form_info['name'].capitalize(), ids=[form_info['target_id']]))
            content.extend(form_info['doc'])
            form_info['docname'] = env.docname
        node.replace_self(content)


def process_form_field_references(app, doctree, fromdocname):
    env = app.builder.env
    form_fields = getattr(env, 'wtforms_form_fields', None)

    for node in doctree.traverse(field_type_node):
        parent = nodes.classifier()
        if 'form_path' in node:
            form_info = form_fields[node['form_path']]
            ref = nodes.reference('', '', *node.children)
            ref['refdocname'] = form_info['docname']
            ref['refuri'] = app.builder.get_relative_uri(fromdocname, form_info['docname'])
            ref['refuri'] += '#' + form_info['target_id']
            parent.append(ref)
            parent.append(nodes.Text('*'))
        else:
            parent.extend(node.children)
        node.replace_self(parent)


def setup(app):
    app.add_directive('wtforms', WTFormsDirective)
    app.add_directive('formfields', FormFieldsDirective)
    app.connect('doctree-read', process_form_field_nodes)
    app.connect('doctree-resolved', process_form_field_references)
