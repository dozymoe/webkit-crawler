import logging
import sys

from engine import Application

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger()

app = Application(sys.argv, logger=log)

if __name__ == '__main__' and len(sys.argv) > 1:
    if sys.argv[1] == 'ufbm':
        from tasks.ufbm import unban_facebook_blocked_members

        unban_facebook_blocked_members(app)
    else:
        exit(-1)

app.start()
