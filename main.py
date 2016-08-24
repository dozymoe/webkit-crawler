import logging
import os
import sys

from core.engine import Application

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

if __name__ == '__main__' and len(sys.argv) > 1:
    if sys.argv[1] == 'ufbm':
        from tasks.ufbm import collect_settings, unban_facebook_blocked_members

        settings = dict(collect_settings())
        app = Application(sys.argv, logger=log)
        app.settings = settings

        unban_facebook_blocked_members(app)
        exit(app.start())

exit(-1)
