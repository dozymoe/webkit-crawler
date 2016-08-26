import sys
from pyvirtualdisplay import Display

from core.application import Application
from core.reporter import Reporter

if __name__ == '__main__' and len(sys.argv) > 1:
    settings = {}

    if sys.argv[1] == 'ufbm':
        from tasks.ufbm import collect_settings
        from tasks.ufbm import unban_facebook_blocked_members

        collect_settings(settings)

        if not int(settings['application.visible']):
            display = Display(backend='xvfb')
            display.start()

        app = Application(settings)
        reporter = Reporter('ufbm', settings)
        reporter.attach(app)

        unban_facebook_blocked_members(app)
        exit(app.start())

exit(-1)
