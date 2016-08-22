""" Facebook automation """

def do_login(app, username, password):
    js = """
    document.forms.login_form.querySelector('[name="email"]').value = '{username}';
    document.forms.login_form.querySelector('[name="pass"]').value = '{password}';

    bot.trigger_wait_page_load = true;
    document.forms.login_form.querySelector('input[type="submit"]').click();
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


def register_handlers(app):
    app.add_handler('facebook.login', login)
