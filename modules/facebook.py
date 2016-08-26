""" Facebook automation """

import os
from collections import OrderedDict
try:
    # python2.6 support
    from simplejson import load as json_load
except ImportError:
    from json import load as json_load

from core.helpers import flatten_settings_definition


def do_login(app, username, password):
    js = """
    var form = document.forms.login_form;
    form.querySelector('[name="email"]').value = '{username}';
    form.querySelector('[name="pass"]').value = '{password}';

    bot.trigger_wait_page_load = true;
    form.querySelector('input[type="submit"]').click();
    """
    app.execjs(js.format(username=username, password=password))

    app.set_expects([
        {
            'path': '/',
            'selectorExists': 'div[data-click="profile_icon"]',
            'trigger': 'bot.nextQueue',
        }])
        

def login(app, username, password):
    app.add_handler('facebook.doLogin', do_login)

    app.set_expects([
        {
            'path': '/',
            'selectorExists': 'form#login_form',
            'trigger': 'facebook.doLogin',
            'triggerArgs':
            {
                'username': username,
                'password': password,
            }
        }])


def get_handlers():
    return (
        ('facebook.login', login),
    )


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'facebook_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
