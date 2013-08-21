"""
This Sphinx extension fixes issues related to Google ndb. At the moment the only fix is the signature of tasklets.
The real signature is hidden behind the tasklet decorator if this extension is not used.
"""
import inspect


def process_signature(app, what, name, obj, options, signature, return_annotation):
    if what in ('function', 'method') and hasattr(obj, '__wrapped__'):
        argspec = inspect.getargspec(obj.__wrapped__)
        if what == 'method':
            if argspec[0] and argspec[0][0] in ('cls', 'self'):
                del argspec[0][0]
        signature = inspect.formatargspec(*argspec)
    return signature, return_annotation


def setup(app):
    app.connect('autodoc-process-signature', process_signature)
