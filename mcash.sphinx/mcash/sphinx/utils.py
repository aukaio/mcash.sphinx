from importlib import import_module


__all__ = ['import_obj', 'get_import_path']


def import_obj(path):
    parts = path.split('.')
    curr_path = parts.pop(0)
    obj = import_module(curr_path)
    for part in parts:
        curr_path += '.' +  part
        try:
            obj = getattr(obj, part)
        except AttributeError:
            obj = import_module(curr_path)
    return obj


def get_import_path(obj):
    return obj.__module__ + '.' + obj.__name__


