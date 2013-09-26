import re
import webapp2
from collections import OrderedDict
from docutils import nodes
from docutils.statemachine import ViewList
from sphinx.util.compat import Directive
from sphinx.util.nodes import nested_parse_with_titles
from mcash.sphinx import utils
from webapp2_extras import routes as wa_routes
from pprint import pprint

from sphinxcontrib.httpdomain import HTTPResource


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



class ApiEndpointDirective(Directive):
    has_content = True

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
            methods = self.allowed_methods.intersection(map(webapp2._normalize_handler_method, route.methods or []))
            if url not in urls:
                urls[url] = set(methods)
            else:
                urls[url].update(methods)
        return handlers

    def get_doc(self, obj):
        try:
            while True:
                obj = obj.__wrapped__
        except AttributeError:
            pass
        return obj.__doc__ or ''

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
        for line in self.get_doc(method).split('\n'):
            yield line
        yield ''

    def make_rst(self):
        for handler, urls in self.handler_map.items():
            title = self.get_resource_name(handler)
            yield title
            yield '-' * len(title)
            for url, methods in urls.items():
                for method_name in methods:
                    method = getattr(handler, method_name)
                    if method is None:
                        continue
                    for line in self.http_directive(method, method_name, url):
                        yield line

    def run(self):
        node = nodes.section()
        node.document = self.state.document
        result = ViewList()
        for line in self.make_rst():
            result.append(line, '<autowebapp>')
        nested_parse_with_titles(self.state, result, node)
        return node.children


