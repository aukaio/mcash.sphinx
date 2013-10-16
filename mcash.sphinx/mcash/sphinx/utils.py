from importlib import import_module

from sphinx.util.docstrings import prepare_docstring


__all__ = ['import_obj', 'get_import_path', 'not_implemented', 'get_doc']


def import_obj(path):
    parts = path.split('.')
    curr_path = parts.pop(0)
    obj = import_module(curr_path)
    for part in parts:
        curr_path += '.' + part
        try:
            obj = getattr(obj, part)
        except AttributeError:
            obj = import_module(curr_path)
    return obj


def get_import_path(obj):
    return obj.__module__ + '.' + obj.__name__


def get_doc(obj):
    try:
        while True:
            obj = obj.__wrapped__
    except AttributeError:
        pass
    ds = obj.__doc__
    if ds is None:
        return []
    ds = prepare_docstring(ds)
    if ds is None:
        return []
    return ds

