import functools
from importlib import import_module


__all__ = ['import_obj', 'get_import_path', 'not_implemented']


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


def not_implemented(reason=''):
    def decorator(f):
        @functools.wraps(f)
        def new_f(*args, **kwargs):
            raise NotImplementedError
        new_f._not_implemented = reason
        return new_f
    return decorator
