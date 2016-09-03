import os
import sys
from ast import literal_eval
from collections import Mapping
from getpass import getpass
from re import compile, sub as subst
try:
    from urllib.parse import urlsplit, urlunsplit
except ImportError:
    from urlparse import urlsplit, urlunsplit


def evaluate_conditional(expr_list, context):
    re_replacement = compile(r'({([\w.]+)})')
    re_split = compile(r'\s')

    for expr in make_list(expr_list):
        try:
            match = re_replacement.search(expr)
            while match:
                expr = expr.replace(match.group(1), context[match.group(2)])
                match = re_replacement.search(expr)
        except KeyError:
            break

        try:
            var1, comp, var2 = [x for x in re_split.split(expr) if x]

            var1 = literal_eval(var1)
            var2 = literal_eval(var2)

            if not comp in ('<', '<=', '>', '>=', '==', '!='):
                raise ValueError()

            if comp == '<' and var1 >= var2:
                break
            elif comp == '<=' and var1 > var2:
                break
            elif comp == '>' and var1 <= var2:
                break
            elif comp == '>=' and var1 < var2:
                break
            elif comp == '==' and var1 != var2:
                break
            elif comp == '!=' and var1 == var2:
                break

        except ValueError:
            sys.stderr.write('invalid conditional: %s\n' % expr)
            break
    else:
        return True

    return False


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
    elif sys.version_info[0] >= 3:
        fn_input = input
    else:
        fn_input = raw_input

    return fn_input(config['prompt'])


def is_active_settings(setting, settings):
    for active_setting in settings:
        if setting.startswith(active_setting):
            return True
    return False


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


def make_list(items, nodict=True):
    if items is None:
        return []
    elif not is_non_string_iterable(items):
        return [items]
    elif nodict and isinstance(items, dict):
        return [items]
    else:
        return items


def traverse_dom_element(element, excludes=[]):
    while child:
        if not child.tagName() in excludes:
            yield child
        for c in traverse_dom_element(child, excludes):
            yield c
        child = child.nextSibling()


def strip_tags(element):
    result = []
    for el in traverse_dom_element(element,
            excludes=['button', 'script']):

        result.append(el.toPlainText())

        #result = ' '.join([e for e in soup.recursiveChildGenerator() \
        #        if isinstance(e, unicode)])

    return subst(r'[ \t]+', ' ', ' '.join(result)).strip()


def url_join(*parts, **kwargs):
    """
    Normalize url parts and join them with a slash.
    adapted from: http://codereview.stackexchange.com/q/13027
    """
    def concat_paths(sequence):
        result = []
        for path in sequence:
            result.append(path)
            if path.startswith('/'):
                break
        return '/'.join(reversed(result))

    schemes, netlocs, paths, queries, fragments = zip(*(urlsplit(part) for part in reversed(parts)))
    scheme = next((x for x in schemes if x), kwargs.get('scheme', 'http'))
    netloc = next((x for x in netlocs if x), '')
    path = concat_paths(paths)
    query = queries[0]
    fragment = fragments[0]
    return urlunsplit((scheme, netloc, path, query, fragment))
