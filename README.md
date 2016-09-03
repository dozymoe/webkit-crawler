# webkit-crawler

Simple crawler based on PyQt4 for javascript powered websites.

In truth it functions as user interaction automation, with workflow pattern
inspired by `pexpect`, fulfillment of expectations will trigger chains of
callbacks.


## Installation

Run `./configure.sh` which will create python virtualenv in `.virtualenv`
directory.


## Using

Example cron script:

    #!/bin/bash
    (
        export FACEBOOK_USERNAME=
        export FACEBOOK_PASSWORD=
        export FACEBOOK_FORUM_NAME=

        export APPLICATION_VISIBLE=0

        export REPORTER_DEFAULT_TYPE=syslog
        export REPORTER_EMAIL_ENABLED=1
        export REPORTER_EMAIL_CONTENT_SUBJECT="cron facebook unban members has failed"
        export REPORTER_EMAIL_CONTENT_FROM=
        export REPORTER_EMAIL_CONTENT_TO=
                                           
        cd /usr/src/local/facebook-unban
        source .virtualenv/bin/activate
        python main.py ufbm
    )


## Requirements

*  PyQt4
*  python-virtualenv
*  Xvfb (linux server)
