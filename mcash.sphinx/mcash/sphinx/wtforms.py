"""
This Sphinx extension displays WTForms with fields
"""
import re
import itertools
from collections import OrderedDict
from docutils import nodes
from sphinx.util.compat import Directive
from sphinx.util.docstrings import prepare_docstring
from docutils.statemachine import ViewList

from mcash.utils import import_obj
from mcash.utils import json
from mcash.core.forms.form import Form
from mcash.sphinx import utils
fields = import_obj('wtforms.fields')
from mcash.core.forms import fields


class form_fields_node(nodes.General, nodes.Element):
    pass


class field_type_node(nodes.General, nodes.Element):
    pass


class field_doc_node(nodes.General, nodes.Element):
    pass


def field_type_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    return [field_doc_node('', field_type_override_node(rawtext, text))], []


class field_type_override_node(nodes.General, nodes.Element):
    def __init__(self, rawtext, type):
        nodes.Element.__init__(self, type=type)


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


base_field_types = {
    'DecimalField', 'DateField', 'DateTimeField', 'FloatField', 'IntegerField', 'StringField', 'BooleanField',
    'TextAreaField',
}


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
        self.form_fields = env.wtforms_form_fields = getattr(env, 'wtforms_form_fields', OrderedDict())
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

    def process_docs(self, field, result):
        self.state.nested_parse(ViewList(utils.get_doc(field)), 0, result)

    def process_field_generic(self, field, parent):
        properties = self.extract_field_properties(field)
        specs_cell, description_cell = self.make_field_definition(
            parent,
            field_name=field.name,
            field_type='',
            **properties
        )
        env = self.state.document.settings.env
        if isinstance(field, fields.FormField):
            field_path = utils.get_import_path(field.form_class)
        else:
            field_path = utils.get_import_path(type(field))
        if field_path not in self.form_fields:
            result = nodes.Element()
            if isinstance(field, fields.FormField):
                self.process_form(field.form_class, result)
            else:
                self.parse_field_doc(type(field), result)
            self.form_fields[field_path] = {
                'doc': result.children,
                'target_id': "wtforms-fielddoc-%d" % env.new_serialno('wtforms-fielddoc')
            }
        for node in specs_cell.traverse(field_type_node):
            node['field_path'] = field_path

    def process_field_FieldList(self, field, parent):
        subfield = field.unbound_field.bind(form=None, name=field.name, prefix='')
        subfield.name = '%s[]' % subfield.name
        subfield.label = field.label
        self.process_field_delegate(subfield, parent)

    def process_field_FormField(self, field, parent):
        self.process_field_generic(field, parent)

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

    def process_form(self, form_class, parent):
        assert issubclass(form_class, Form)
        self.parse_field_doc(form_class, parent)
        table = self.prepare_table(parent)
        form_instance = form_class()

        for field in form_instance:
            if field.name == 'link':
                continue
            self.process_field_delegate(field, table)

    def parse_field_doc(self, obj, parent):
        result = nodes.Element()
        self.state.nested_parse(ViewList(utils.get_doc(obj)), 0, result)
        parent.extend(itertools.chain(
            *(n.children for n in result.traverse(field_doc_node))
        ))


class FormFieldsDirective(Directive):
    has_content = True

    def run(self):
        return [form_fields_node()]


class FieldDocDirective(Directive):
    has_content = True

    def run(self):
        parent = field_doc_node()
        self.state.nested_parse(ViewList(self.content), 0, parent)
        return [parent]


def process_form_field_nodes(app, doctree):
    env = app.builder.env
    form_fields = getattr(env, 'wtforms_form_fields', {})
    process_from_fields_dict(form_fields)
    content = []
    for form_path, form_info in form_fields.items():
        if form_info['is_base']:
            continue
        content.append(nodes.subtitle('', form_info['name'], ids=[form_info['target_id']]))
        content.extend(form_info['doc'])
        form_info['docname'] = env.docname
    for node in doctree.traverse(form_fields_node):
        node.replace_self(content)


def process_from_fields_dict(form_fields):
    for form_path, form_info in form_fields.items():
        override_nodes = nodes.Element('', *form_info['doc']).traverse(field_type_override_node)
        if override_nodes:
            new_form_path = override_nodes[0]['type']
            if new_form_path in base_field_types:
                form_info['is_base'] = True
                form_info['name'] = re.sub(r'(Field|Form)$', r'', new_form_path.split('.')[-1])
            else:
                form_fields[form_path] = form_fields[new_form_path]
            continue
        form_class = utils.import_obj(form_path)
        form_info['name'] = re.sub(r'(Field|Form)$', r'', form_class.__name__)
        form_info['is_base'] = form_class.__name__ in base_field_types


def process_form_field_references(app, doctree, fromdocname):
    env = app.builder.env
    form_fields = getattr(env, 'wtforms_form_fields', {})

    for node in doctree.traverse(field_type_node):
        parent = nodes.classifier()
        form_info = form_fields[node['field_path']]
        if form_info['is_base']:
            parent.append(nodes.Text(form_info['name']))
        else:
            ref = nodes.reference('', form_info['name'])
            ref['refdocname'] = form_info['docname']
            ref['refuri'] = app.builder.get_relative_uri(fromdocname, form_info['docname'])
            ref['refuri'] += '#' + form_info['target_id']
            parent.append(ref)
            parent.append(nodes.Text('*'))
        node.replace_self(parent)


def setup(app):
    app.add_directive('wtforms', WTFormsDirective)
    app.add_directive('formfields', FormFieldsDirective)
    app.add_directive('fielddoc', FieldDocDirective)
    app.connect('doctree-read', process_form_field_nodes)
    app.connect('doctree-resolved', process_form_field_references)
    app.add_role('fieldtype', field_type_role)
    app.add_object_type
