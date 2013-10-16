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


class field_type_ref(nodes.General, nodes.Element):
    pass


def wtforms_role(role, rawtext, text, lineno, inliner, options=[], content=[]):
    m = re.match(r'^(.+?)( <(.+?)>)?$', text)
    g = m.groups()
    ref = field_type_ref()
    if g[2] is None:
        ref['field_path'] = g[0]
    else:
        ref['field_path'] = g[2]
        ref['text'] = g[0]
    return [ref], []


class api_doc_node(nodes.General, nodes.Element):
    pass


def field_type_role(role, rawtext, text, lineno, inliner, options={}, content=[]):
    return [api_doc_node('', field_type_override_node(rawtext, text))], []


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
    'DecimalField', 'FloatField', 'IntegerField', 'StringField', 'BooleanField', 'TextAreaField',
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
    option_spec = {
        'exclude-docstring': bool,
    }

    def __init__(self, name, arguments, options, content, lineno,
                 content_offset, block_text, state, state_machine):
        super(WTFormsDirective, self).__init__(name, arguments, options, content, lineno,
                 content_offset, block_text, state, state_machine)
        self.exclude_docstring = self.options.get('exclude-docstring', False)

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
        specs_cell.append(nodes.classifier('', '', field_type_ref()))

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
                'target_id': "wtforms-fielddoc-%s-%d" % (env.docname, env.new_serialno('wtforms-fielddoc'))
            }
        for node in specs_cell.traverse(field_type_ref):
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
        if not self.exclude_docstring:
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
            *(n.children for n in result.traverse(api_doc_node))
        ))


class FormFieldsDirective(Directive):
    has_content = True

    def run(self):
        return [form_fields_node()]


class ApiDocDirective(Directive):
    has_content = True

    def run(self):
        parent = api_doc_node()
        self.state.nested_parse(ViewList(self.content), 0, parent)
        return [parent]


def process_form_field_nodes(app, doctree):
    env = app.builder.env
    form_fields = getattr(env, 'wtforms_form_fields', {})
    process_from_fields_dict(form_fields)
    document = doctree.traverse(nodes.document)[0]
    content = []
    for form_path, form_info in form_fields.items():
        if form_info['is_base']:
            continue
        sec = nodes.section(ids=[form_info['target_id']])
        sec.document = document
        sec.append(nodes.title('', form_info['name']))
        sec.extend(form_info['doc'])
        content.append(sec)
        form_info['docname'] = env.docname
    ff_nodes = doctree.traverse(form_fields_node)
    for node in ff_nodes:
        node.replace_self(content)
    if ff_nodes:
        env.build_toc_from(env.docname, doctree)


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


def find_field_info(field_info_map, path):
    try:
        return field_info_map[path]
    except KeyError:
        candidates = filter(lambda e: e[0].rsplit('.')[-1] == path, field_info_map.items())
        if len(candidates) == 1:
            return candidates[0][1]
        raise


def process_form_field_references(app, doctree, fromdocname):
    env = app.builder.env
    form_fields = getattr(env, 'wtforms_form_fields', {})

    for node in doctree.traverse(field_type_ref):
        form_info = find_field_info(form_fields, node['field_path'])
        if form_info['is_base']:
            ref = nodes.Text(form_info['name'])
        else:
            if 'text' in node:
                ref = nodes.reference('', node['text'])
            else:
                ref = nodes.reference('', form_info['name'])
            ref['refdocname'] = form_info['docname']
            ref['refuri'] = app.builder.get_relative_uri(fromdocname, form_info['docname'])
            ref['refuri'] += '#' + form_info['target_id']
        node.replace_self(ref)

    for node in doctree.traverse(field_type_override_node):
        node.parent.remove(node)


def process_html_context(app, pagename, templatename, context, doctree):
    if doctree is None:
        return
    env = app.builder.env
    toc = env.get_toctree_for(pagename, app.builder, collapse=True, maxdepth=3)
    toc = toc[0].deepcopy()
    uls = toc.traverse(nodes.bullet_list)
    top_ul = uls.pop(0)
    top_ul['classes'].extend(('nav', 'sidenav'))
    for node in uls:
        node['classes'].append('nav')
    context['sidebar_globaltoc'] = app.builder.render_partial(toc)['fragment']

    toc = env.get_toc_for(pagename, app.builder)
    if len(toc) == 1 and len(toc[0]) == 2:
        toc = toc[0][1]
    uls = toc.traverse(nodes.bullet_list)
    uls.pop(0)['classes'].append('nav sidenav')
    for node in uls:
        node['classes'].append('nav')


def visit_api_doc(self, node):
    new = nodes.paragraph()
    new.append(nodes.strong('API Documentation', 'API Documentation'))
    new.extend(node.children)
    node.replace_self(new)
    self.visit_paragraph(node)


def depart_api_doc(self, node):
    self.depart_paragraph(node)


def setup(app):
    app.add_directive('wtforms', WTFormsDirective)
    app.add_directive('form-fields', FormFieldsDirective)
    app.add_directive('api-documentation', ApiDocDirective)
    app.connect('doctree-read', process_form_field_nodes)
    app.connect('doctree-resolved', process_form_field_references)
    app.connect('html-page-context', process_html_context)
    app.add_role('field-type', field_type_role)
    app.add_role('wtforms', wtforms_role)

    app.add_node(api_doc_node, html=(visit_api_doc, depart_api_doc))
