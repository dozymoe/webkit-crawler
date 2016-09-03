""" Facebook automation """

import os
from collections import OrderedDict
try:
    # python2.6 support
    from simplejson import load as json_load
except ImportError:
    from json import load as json_load

from core.helpers import flatten_settings_definition


def check_page_not_found(app, frame, *args):
    document = frame.documentElement()
    header = document.findFirst('#content > .UIFullPage_Container ' +\
            'h2.uiHeaderTitle')

    if header.isNull():
        return False

    header_content = header.evaluateJavaScript('this.textContent')
    app.info(header_content)
    return True


def on_do_login_failed_trigger(app, frame):
    app.error('Invalid Facebook username and password: "%s".' % \
            app.settings['facebook.username'])

    app.exit(-1)


def on_do_login_trigger(app, frame):
    el_form = frame.documentElement().findFirst('form#login_form')
    if el_form.isNull():
        app.error("Cannot find Facebook's login form, UI has changed.")
        app.exit(-1)
        return

    el_username = el_form.findFirst('[name="email"]')
    if el_username.isNull():
        app.error("Cannot find Facebook's login username input, " +\
                "UI has changed.")

        app.exit(-1)
        return

    username = app.settings['facebook.username']
    el_username.evaluateJavaScript('this.value="%s"' % username)

    el_password = el_form.findFirst('[name="pass"]')
    if el_password.isNull():
        app.error("Cannot find Facebook's login password input, " +\
                "UI has changed.")

        app.exit(-1)
        return

    password = app.settings['facebook.password']
    el_password.evaluateJavaScript('this.value="%s"' % password)

    app.add_handler('facebook.do_login_failed', on_do_login_failed_trigger)

    app.set_expects([
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^/$',
            'selector_exists': 'div[data-click="profile_icon"]',
            'trigger': 'core.next_queue',
            'trigger_wait_pageload': True,
        },
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^/login\.php$',
            'trigger': 'facebook.do_login_failed',
            'trigger_wait_pageload': True,
        }])

    el_submit = el_form.findFirst('input[type="submit"]')
    if el_submit.isNull():
        app.error("Cannot find Facebook's login submit button, " +\
                "UI has changed.")

        app.exit(-1)
        return

    el_submit.evaluateJavaScript('bot.click(this)')


def on_login_trigger(app, frame):
    app.add_handler('facebook.do_login', on_do_login_trigger)

    app.set_expects([
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^/$',
            'selector_exists': 'form#login_form',
            'trigger': 'facebook.do_login',
        }])


def get_handlers():
    return (
        ('facebook.login', on_login_trigger),
    )


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'facebook_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
