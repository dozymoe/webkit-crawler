import os
import sys
from collections import OrderedDict
from email.mime.text import MIMEText
try:
    # python2.6 support
    from simplejson import load as json_load
except ImportError:
    from json import load as json_load
from logging import getLogger, DEBUG, INFO, WARNING, ERROR
from logging.handlers import RotatingFileHandler, SysLogHandler
try:
    from logging.handlers import StreamHandler
except ImportError:
    from logging import StreamHandler
from smtplib import SMTP

from core.helpers import flatten_settings_definition

def str_to_log_level(log_level):
    if log_level == 'debug':
        return DEBUG
    elif log_level == 'info':
        return INFO
    elif log_level == 'warning':
        return WARNING
    elif log_level == 'error':
        return ERROR
    else:
        sys.stderr.write('Unknown log_level: "%s"\n' % log_level)
        return INFO

def log_level_to_str(log_level):
    if log_level == DEBUG:
        return 'DEBUG'
    elif log_level == INFO:
        return 'INFO'
    elif log_level == WARNING:
        return 'WARNING'
    elif log_level == ERROR:
        return 'ERROR'
    else:
        return 'UNKNOWN_%s' % log_level


class MailReporter(object):
    settings = None
    _logs = None
    _log_level = None
    _log_level_send = None
    _send = None

    def __init__(self, settings):
        self.settings = settings

        self._logs = []
        self._send = False
        self._log_level = str_to_log_level(settings['reporter.email.log_level'])
        self._log_level_send = str_to_log_level(
                settings['reporter.email.log_level_send'])


    def attach(self, thingy):
        if int(self.settings['reporter.email.enabled']) == 0:
            return

        thingy.onLog.connect(self._on_log)

        if hasattr(thingy, 'aboutToQuit'):
            thingy.aboutToQuit.connect(self._on_app_quit)


    def _on_log(self, log_level, message):
        if log_level >= self._log_level_send:
            self._send = True
        if log_level >= self._log_level:
            self._logs.append((log_level, message))


    def _generate_content(self):
        for log_level, text in self._logs:
            yield '%s: %s' % (log_level_to_str(log_level), text)


    def _on_app_quit(self):
        if not self._send:
            return

        msg = MIMEText('\n'.join(self._generate_content()))
        msg['Subject'] = self.settings['reporter.email.content.subject']
        msg['From'] = self.settings['reporter.email.content.from']
        msg['To'] = self.settings['reporter.email.content.to']

        sender = SMTP(host=self.settings['reporter.email.sender.host'],
                port=int(self.settings['reporter.email.sender.port']))

        if int(self.settings['reporter.email.sender.use_tls']):
            sender.starttls()

        if self.settings['reporter.email.sender.username']:
            sender.login(user=self.settings['reporter.email.sender.username'],
                    password=self.settings['reporter.email.sender.password'])

        sender.sendmail(from_addr=msg['From'], msg=msg.as_string(),
                to_addrs=[to.strip() for to in msg['To'].split(',')])

        sender.quit()


class Reporter(object):
    _log = None
    _mailer = None
    settings = None

    def __init__(self, name, settings):
        self.settings = settings
        self._mailer = MailReporter(settings)

        self._log = getLogger(name)
        self._log.setLevel(str_to_log_level(
            settings['reporter.default.log_level']))

        output_type = settings['reporter.default.type']
        if output_type == 'syslog':
            self._log.addHandler(SysLogHandler(address='/dev/log'))

        elif output_type == 'file':
            filename = settings['reporter.default.filename']
            if not filename:
                filename = '%s.log' % name

            filesize = int(settings['reporter.default.filesize'])
            filecount = int(settings['reporter.default.filecount'])
            if filecount > 0:
                filecount -= 1

            self._log.addHandler(RotatingFileHandler(filename,
                    maxBytes=filesize, backupCount=filecount))

        elif output_type == 'console':
            self._log.addHandler(StreamHandler())


    def attach(self, thingy):
        thingy.onLog.connect(self._log.log)
        self._mailer.attach(thingy)


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'reporter_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
