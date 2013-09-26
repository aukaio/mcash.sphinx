from importlib import import_module


__all__ = ['import_obj']


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


