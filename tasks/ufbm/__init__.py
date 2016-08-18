""" Unban Facebook Blocked Members """

import os

from modules.facebook import register_handlers as facebook_handlers

FORUM_NAME = os.environ['FACEBOOK_FORUM']

FACEBOOK_URL = 'https://www.facebook.com'
FORUM_BLOCKED_PATH = '/groups/' + FORUM_NAME + '/blocked/'
FORUM_BLOCKED_URL = FACEBOOK_URL + FORUM_BLOCKED_PATH


def do_unban_confirm(app):
    js = """
    bot.wait_page_reload = true;
    document.querySelector('button[name="remove_block"]').click();
    """
    app.execjs(js)

    app.set_expects([
        {
            'path': FORUM_BLOCKED_PATH + '?',
            'selectorExists': '#pagelet_group_blocked div[id^="member_"] .adminActions > a[ajaxify*="action=remove_block"]',
            'selectorNotExists': 'button[name="remove_block"]',
            'trigger': 'ufbm.doUnban',
        }])


def do_unban(app):
    js = """
    var el = document.querySelector('#pagelet_group_blocked div[id^="member_"] .adminActions > a[ajaxify*="action=remove_block"]');
    bothelp_clickElement(el);
    """
    app.execjs(js)

    app.add_handler('ufbm.doUnbanConfirm', do_unban_confirm)

    app.set_expects([
        {
            'path': FORUM_BLOCKED_PATH + '?',
            'selectorExists': 'button[name="remove_block"]',
            'trigger': 'ufbm.doUnbanConfirm',
        }])


def unban(app):
    app.clear_handlers()

    app.add_handler('ufbm.doUnban', do_unban)

    app.set_expects([
        {
            'path': FORUM_BLOCKED_PATH + '?',
            'selectorExists': '#pagelet_group_blocked div[id^="member_"] .adminActions > a[ajaxify*="action=remove_block"]',
            'trigger': 'ufbm.doUnban',
        }])


def unban_facebook_blocked_members(app):
    facebook_handlers(app)
    app.add_handler('ufbm.unban', unban);

    app.add_queue(
        {
            'goto': FACEBOOK_URL,
            'expects': [
            {
                'trigger': 'facebook.login',
                'triggerArgs':
                {
                    'username': os.environ['FACEBOOK_USERNAME'],
                    'password': os.environ['FACEBOOK_PASSWORD'],
                }
            }],
        })

    app.add_queue(
        {
            'goto': FORUM_BLOCKED_URL,
            'expects': [
            {
                'trigger': 'ufbm.unban',
            }],
        })
