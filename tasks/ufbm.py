""" Unban Facebook Blocked Members """

from itertools import chain

from core.application import get_settings_definition as application_settings
from core.reporter import get_settings_definition as reporter_settings
from core.helpers import evaluate_conditional, flatten_settings
from core.helpers import get_settings_value, is_active_settings

from modules.facebook import get_handlers as facebook_handlers
from modules.facebook import get_settings_definition as facebook_settings
from modules.facebook import check_page_not_found as facebook404

ACTIVE_SETTINGS = (
    'application.',
    'reporter.',
    'facebook.home',
    'facebook.username',
    'facebook.password',
    'facebook.forum.name',
)

def _get_urls(app):
    fb_forum = app.settings['facebook.forum.name']
    fb_home_url = app.settings['facebook.home']

    urls = {
        'FORUM_BLOCKED_PATH': '/groups/' + fb_forum + '/blocked/',
        'FORUM_BLOCKED_URL': fb_home_url +'/groups/' + fb_forum + '/blocked/',
    }
    return urls


def on_do_unban_timeout_trigger(app, frame):
    app.debug('on_do_unban_timeout_trigger')

    urls = _get_urls(app)

    app.add_handler('ufbm.unban', on_unban_trigger)

    app.set_expects(
        [{
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'trigger': 'ufbm.unban',
            'trigger_wait_pageload': True,
        }])

    app.load(urls['FORUM_BLOCKED_URL'])


def on_do_empty_list_trigger(app, frame):
    app.info('No users were banned.')
    app.exit(0)


def on_do_unban_confirm_trigger(app, frame):
    urls = _get_urls(app)

    document = frame.documentElement()

    app.set_expects([
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'selector_exists': '#pagelet_group_blocked div[id^="member_"] ' +\
                    '.adminActions > a[ajaxify*="action=remove_block"]',

            'selector_not_exists': 'button[name="remove_block"]',
            'trigger': 'ufbm.do_unban',
            'trigger_wait_pageload': True,
        }])

    app.add_handler('ufbm.do_unban_timeout', on_do_unban_timeout_trigger)
    app.set_timeout_expects(15, {'trigger': 'ufbm.do_unban_timeout'})

    el_unblock = document.findFirst('button[name="remove_block"]')
    if el_unblock.isNull():
        app.error('Cannot find "remove block" confirm button, ' +\
                'UI may have changed')

        app.exit(-1)
    else:
        el_unblock.evaluateJavaScript('bot.click(this)')


def on_do_unban_trigger(app, frame):
    urls = _get_urls(app)

    document = frame.documentElement()

    app.add_handler('ufbm.do_unban_confirm', on_do_unban_confirm_trigger)
    app.add_handler('ufbm.do_empty_list', on_do_empty_list_trigger)

    app.set_expects([
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'selector_exists': 'button[name="remove_block"]',
            'trigger': 'ufbm.do_unban_confirm',
            'trigger_delay': 5,
        },
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'selector_exists': '.fbProfileBrowserNullstate.' +\
                    'fbProfileBrowserListContainer',

            'trigger': 'ufbm.do_empty_list',
        }])

    app.add_handler('ufbm.do_unban_timeout', on_do_unban_timeout_trigger)
    app.set_timeout_expects(30, {'trigger': 'ufbm.do_unban_timeout'})

    el_unblock = document.findFirst('#pagelet_group_blocked ' +
            'div[id^="member_"] .adminActions > ' +
            'a[ajaxify*="action=remove_block"]')

    el_unblock.evaluateJavaScript('bot.click(this)')


def on_unban_trigger(app, frame):
    urls = _get_urls(app)

    app.clear_handlers()

    app.add_handler('ufbm.do_unban', on_do_unban_trigger)
    app.add_handler('ufbm.do_empty_list', on_do_empty_list_trigger)

    app.set_expects([
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'selector_exists': '#pagelet_group_blocked div[id^="member_"] ' +\
                    '.adminActions > a[ajaxify*="action=remove_block"]',

            'trigger': 'ufbm.do_unban',
        },
        {
            'host': r'^www\.facebook\.com$',
            'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
            'selector_exists': '.fbProfileBrowserNullstate.' +\
                    'fbProfileBrowserListContainer',

            'trigger': 'ufbm.do_empty_list',
        }])


def unban_facebook_blocked_members(app):
    urls = _get_urls(app)

    for name, callback in facebook_handlers():
        app.add_handler(name, callback)

    app.add_handler('ufbm.unban', on_unban_trigger)

    app.add_queue(
        {
            'goto': app.settings['facebook.home'],
            'expects': [
            {
                'host': r'^www\.facebook\.com$',
                'path': r'^/$',
                'trigger': 'facebook.login',
            }],
        })

    app.add_queue(
        {
            'goto': urls['FORUM_BLOCKED_URL'],
            'expects': [
            {
                'host': r'^www\.facebook\.com$',
                'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
                'selector_exists': '#pagelet_group_blocked',
                'trigger': 'ufbm.unban',
            },
            {
                'host': r'^www\.facebook\.com$',
                'path': r'^%s?$' % urls['FORUM_BLOCKED_PATH'],
                'custom': facebook404,
                'trigger': 'core.page_not_found',
            }],
        })


def collect_settings(result, settings_in_file=None):
    primary_settings = dict(flatten_settings(settings_in_file or {}))

    all_settings = chain(facebook_settings(), application_settings(),
            reporter_settings())

    for name, config in all_settings:
        if 'default' in config:
            result[name] = config['default']

        if not is_active_settings(name, ACTIVE_SETTINGS):
            continue

        if not evaluate_conditional(config.get('if'), result):
            continue

        result[name] = get_settings_value(name, config, primary_settings)
