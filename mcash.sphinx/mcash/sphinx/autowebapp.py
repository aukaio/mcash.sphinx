import re
import inspect
from collections import OrderedDict

from docutils import nodes
from docutils.statemachine import ViewList
from sphinx.util.compat import Directive
from sphinx.util.nodes import nested_parse_with_titles

import webapp2
from mcash.sphinx import utils
from webapp2_extras import routes as wa_routes


def setup(app):
    app.add_directive('autowebapp', ApiEndpointDirective)


def flatten_routes(routes):
    """
    Flatten a nested MultiRoute-Route structure into a sequence of routes.
    :param routes: The route structure to be flattened
    :type routes: collections.Iterable
    :return: A generator yielding Routes
    """
    for route in routes:
        if isinstance(route, wa_routes.MultiRoute):
            for sub_route in flatten_routes(route.get_match_children()):
                yield sub_route
        else:
            yield route


def get_route_handler(route):
    handler = route.handler
    if isinstance(handler, basestring):
        handler = webapp2.import_string(handler)
        route.handler = handler
    return handler


def normalize_template(template):
    return re.sub('<(\w+):[^>]+>', r'<\1>', template)


def get_auth_level(f):
    try:
        level = f._auth_level
    except AttributeError:
        return None
    else:
        from mcash.auth.authinfo import AuthLevel
        for name, value in inspect.getmembers(AuthLevel, lambda m: isinstance(m, int)):
            if value == level:
                return name
    return None


class ApiEndpointDirective(Directive):
    has_content = True
    show_not_implemented = True

    required_arguments = 1
    option_spec = {
        'allowed-methods': lambda s: set(map(webapp2._normalize_handler_method, s.strip().split())),
        'exclude-handlers': lambda s: set(s.strip().split()),
    }

    def __init__(self, name, arguments, options, content, lineno,
                 content_offset, block_text, state, state_machine):
        super(ApiEndpointDirective, self).__init__(
            name, arguments, options, content, lineno, content_offset, block_text, state, state_machine
        )
        self.allowed_methods = self.options['allowed-methods']
        self.exclude_handlers = self.options['exclude-handlers']
        (self.routes_path, ) = self.arguments
        self.routes = tuple(flatten_routes(utils.import_obj(self.routes_path)))
        #self.handlers = {get_route_handler(route): route for route in self.routes}
        self.handler_map = self.build_handler_map()

    def build_handler_map(self):
        """
        {
            handler1: {
                url1: set(methods),
                ...
            },
            ...
        }
        """
        handlers = OrderedDict()
        for route in self.routes:
            handler = get_route_handler(route)
            if handler.__name__ in self.exclude_handlers:
                continue
            if handler in handlers:
                urls = handlers[handler]
            else:
                urls = handlers[handler] = OrderedDict()
            url = normalize_template(route.template)
            if url in urls:
                methods = urls[url]
            else:
                methods = urls[url] = {}

            for method_name in self.allowed_methods.intersection(
                    map(webapp2._normalize_handler_method, route.methods or [])
            ):
                methods[method_name] = route.handler_method or method_name

        return handlers

    def get_resource_name(self, handler):
        try:
            return handler.resource_name.replace('_', ' ')
        except AttributeError:
            pass
        name = handler.__name__
        name = re.sub(r'([A-Z]+)', r' \1', name).strip().split()
        if name[-1].lower() == 'handler':
            name.pop()
        return ' '.join(name)

    def http_directive(self, method, method_name, path):
        yield ''
        yield '.. http:{method}:: {path}'. format(method=method_name, path=path)
        yield ''
        if self.show_not_implemented and hasattr(method, '_not_implemented'):
            reason = method._not_implemented
            if reason:
                reason = ': ' + reason
            yield '    *NOT IMPLEMENTED%s*' % reason
        yield ''
        auth_level = get_auth_level(method)
        if auth_level is not None:
            yield '    *Required auth level: %s*' % auth_level
        yield ''
        for line in utils.get_doc(method):
            yield '    ' + line
        for line in self.process_schemas(method):
            yield '    ' + line
        yield ''

    def form_directive(self, form):
        if form is None:
            yield '*None*'
            yield ''
            raise StopIteration
        if isinstance(form, list):
            form = form[0]
            yield '*A list of objects containing the following data*'
        path = utils.get_import_path(form)
        yield ''
        yield '.. wtforms:: {path}'.format(path=path)
        yield ''

    def process_schemas(self, handler_method):
        for title, form_name in (('Request schema', 'input_form'), ('Response schema', 'output_form')):
            yield '**%s**' % title
            yield ''
            form = getattr(handler_method, form_name, None)
            for line in self.form_directive(form):
                yield line

    def make_rst(self):
        for handler, urls in self.handler_map.items():
            title = self.get_resource_name(handler)
            yield title.capitalize()
            yield '-' * len(title)
            for line in utils.get_doc(handler):
                yield line
            yield ''
            for url, methods in urls.items():
                for method_name, handler_method in methods.items():
                    handler_method = getattr(handler, handler_method, None)
                    if handler_method is None or hasattr(handler_method, '_undocumented'):
                        continue
                    for line in self.http_directive(handler_method, method_name, url):
                        yield line

    def run(self):
        node = nodes.section()
        node.document = self.state.document
        result = ViewList()
        for line in self.make_rst():
            result.append(line, '<autowebapp>')
        nested_parse_with_titles(self.state, result, node)
        return node.children


