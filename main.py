import signal
import sys

from core.application import Application
from core.reporter import Reporter

app = None
settings = {}

def signal_handler(signum, frame):
    if app:
        app.exit(-1)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == '__main__' and len(sys.argv) > 1:
    if sys.argv[1] == 'ufbm':
        from tasks.ufbm import collect_settings
        from tasks.ufbm import unban_facebook_blocked_members

        collect_settings(settings)

        #if not int(settings['application.visible']):
        #    from pyvirtualdisplay import Display
        #    display = Display(backend='xvfb')
        #    display.start()

        app = Application('ufbm', settings)
        reporter = Reporter('ufbm', settings)
        reporter.attach(app)

        unban_facebook_blocked_members(app)
        exit(app.start())

exit(-1)
