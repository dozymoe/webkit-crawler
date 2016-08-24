import os
import sys
from builtins import input # python2/3 compatible `input()`
from collections import Mapping
from getpass import getpass


def flatten_settings(data, prefix=None):
    """see http://stackoverflow.com/a/6036037"""
    for key in data:
        item = data[key]
        if prefix:
            new_prefix = prefix + '.' + key
        else:
            new_prefix = key

        if isinstance(item, Mapping):
            for child_item in flatten_settings(item, new_prefix):
                yield child_item
        else:
            yield (new_prefix, item)


def flatten_settings_definition(data, prefix=None):
    """see http://stackoverflow.com/a/6036037"""
    for key in data:
        item = data[key]
        if isinstance(item, Mapping):
            if prefix:
                new_prefix = prefix + '.' + key
            else:
                new_prefix = key
            for child_item in flatten_settings_definition(item, new_prefix):
                yield child_item
        else:
            break
    else:
        return

    yield (prefix, data)


def get_settings_value(name, config, settings_in_file):
    if name in settings_in_file:
        return settings_in_file[name]

    env_name = name.upper().replace('.', '_')
    if env_name in os.environ:
        return os.environ[env_name]

    if 'default' in config:
        return config['default']

    if config.get('masked', False):
        fn_input = getpass
    else:
        fn_input = input

    return fn_input(config['prompt'])


def is_non_string_iterable(data):
    # http://stackoverflow.com/a/17222092
    try:
        if isinstance(data, unicode) or isinstance(data, str):
            return False
    except NameError:
        pass
    if isinstance(data, bytes):
        return False
    try:
        iter(data)
    except TypeError:
        return False
    try:
        hasattr(None, data)
    except TypeError:
        return True
    return False


def log_message(logger, level, message):
    if logger:
        logger.log(level, message)
    elif level in (logging.ERROR, logging.FATAL, logging.WARNING):
        sys.stderr.write(message)
        sys.stderr.write('\n')
    else:
        sys.stdout.write(message)
        sys.stdout.write('\n')


def make_list(items, nodict=False):
    if items is None:
        return []
    elif not is_non_string_iterable(items):
        return [items]
    elif nodict and isinstance(items, dict):
        return [items]
    else:
        return items
