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

        thingy.log_event.connect(self._on_log)

        if hasattr(thingy, 'aboutToQuit'):
            thingy.aboutToQuit.connect(self._on_app_quit)


    def _on_log(self, log_level, message, group):
        if log_level >= self._log_level_send:
            self._send = True
        if log_level >= self._log_level:
            self._logs.append((str(group), log_level, str(message)))


    def _generate_content(self):
        for group, log_level, text in self._logs:
            yield '%s: %s: %s' % (log_level_to_str(log_level), group, text)


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
    _mailer = None
    settings = None
    known_logs = ('default', 'http', 'javascript', 'qt')

    def __init__(self, name, settings):
        self.settings = settings
        self._mailer = MailReporter(settings)

        base_dir = os.path.dirname(os.path.dirname(
                os.path.realpath(__file__)))

        log_dir = os.path.join(base_dir, 'logs')

        for logname in self.known_logs:
            log = getLogger(logname)
            log.setLevel(str_to_log_level(
                settings['reporter.%s.log_level' % logname]))

            output_type = settings['reporter.%s.type' % logname]
            if output_type == 'syslog':
                log.addHandler(SysLogHandler(address='/dev/log'))

            elif output_type == 'file':
                filename = settings['reporter.%s.filename' % logname]
                if not filename:
                    filename = '%s-%s.log' % (name, logname)
                elif os.path.dirname(filename) == '':
                    filename = os.path.join(log_dir, '%s-%s' % (name,
                            filename))

                filesize = int(settings['reporter.%s.filesize' % logname])
                filecount = int(settings['reporter.%s.filecount' % logname])
                if filecount > 0:
                    filecount -= 1

                log.addHandler(RotatingFileHandler(filename,
                        maxBytes=filesize, backupCount=filecount))

            elif output_type == 'console':
                log.addHandler(StreamHandler())


    def attach(self, thingy):
        thingy.log_event.connect(self._on_log)
        self._mailer.attach(thingy)


    def _on_log(self, log_level, message, group):
        group = str(group)
        if group in self.known_logs:
            log = getLogger(group)
            log.log(log_level, message)
        else:
            log = getLogger('default')
            log.error('Unknown logger: %s.' % group)


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'reporter_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
