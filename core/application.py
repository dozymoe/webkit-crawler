""" Shared Application """

import os
import re
from collections import OrderedDict
from functools import partial
from logging import DEBUG, ERROR, INFO, WARNING
from threading import Lock
from uuid import uuid4
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
try:
    # python2.6 support
    from simplejson import load as json_load
except ImportError:
    from json import load as json_load
try:
    from urllib.parse import urlsplit
except ImportError:
    from urlparse import urlsplit
try:
    from PyQt5.QtWidgets import QApplication
    from PyQt5.QtCore import QUrl, QTimer, pyqtSignal, qInstallMessageHandler
    from PyQt5.QtWebKitWidgets import QWebPage, QWebView
    from PyQt5.QtNetwork import QNetworkReply, QNetworkRequest
except ImportError:
    from PyQt4.QtGui import QApplication
    from PyQt4.QtCore import QUrl, QTimer, pyqtSignal
    from PyQt4.QtCore import qInstallMsgHandler
    from PyQt4.QtWebKit import QWebPage, QWebView
    from PyQt4.QtNetwork import QNetworkReply, QNetworkRequest

from core.helpers import flatten_settings_definition, make_list
from core.webpage import WebPage

ENUM_FRAME_DATA_ACTIVE = 0
ENUM_FRAME_DATA_TIMER_CALLBACK = 1
ENUM_FRAME_DATA_TIMER_COUNTER = 2


class Application(QApplication):
    _active_task = None
    _exit_timer = None
    _expects = None
    _expects_active = False
    _expects_if_timeout = None
    _expects_timer = None
    _frame_data = None
    _frame_data_lock = None
    _frame_timer = None
    _handlers = None
    _queue = None
    _trigger_delay_timer = None
    _visible = True

    log_event = pyqtSignal(int, str, str)
    name = ''

    def __init__(self, name, settings):
        super(Application, self).__init__([])

        self.name = name
        self.settings = settings

        self.web_view = QWebView()

        self._exit_timer = QTimer(self)
        self._exit_timer.setSingleShot(True)
        self._exit_timer.setInterval(1000)

        self._expects = []
        self._expects_if_timeout = []
        self._expects_timer = QTimer(self)
        self._expects_timer.setSingleShot(True)
        self._expects_timer.timeout.connect(self._on_expects_timeout)
        self._frame_data = {}
        self._frame_data_lock = Lock()
        self._frame_timer = QTimer(self)
        self._frame_timer.start(3000)
        self._queue = Queue()
        self._trigger_delay_timer = QTimer(self)
        self._trigger_delay_timer.setSingleShot(True)
        self._visible = int(self.settings['application.visible'])

        self.web_page = WebPage(self.web_view)
        self.web_page.log_event.connect(self.log_event)
        self.web_page.frameCreated.connect(self._on_frame_created)
        self._on_frame_created(self.web_page.mainFrame())
        #self.web_page.networkAccessManager().finished.connect(
        #        self._on_http_response)

        self.web_view.setPage(self.web_page)

        st = self.web_page.settings()
        st.setAttribute(
            st.AutoLoadImages,
            int(self.settings['application.settings.load_images']))
        st.setAttribute(
            st.JavaEnabled,
            int(self.settings['application.settings.java_enabled']))
        st.setAttribute(
            st.PluginsEnabled,
            int(self.settings['application.settings.plugins_enabled']))

        self.clear_handlers()

        # redirect qt related messages
        try:
            qInstallMessageHandler(self._pyqt5_null_message_handler)
        except NameError:
            qInstallMsgHandler(self._pyqt4_null_message_handler)


    def start(self):
        self.process_next_queue()
        if self._visible:
            self.web_view.show()
        return self.exec_()


    def add_queue(self, task, publish=False):
        self._queue.put(task)


    def process_next_queue(self):
        self._on_next_queue_trigger(self)


    def get_frame_related_data(self, frame):
        """
        There is a pool of reusable frame data, because browser's frames were
        easily created and destroyed.
        """
        with self._frame_data_lock:
            frame_data = self._frame_data.get(str(frame.objectName()))
        return frame_data


    def set_expects(self, expects):
        self._expects_active = True

        newlist = make_list(expects)
        for item in newlist:
            for key in item:
                if not key in ('path', 'hash', 'host', 'selector_exists',
                        'selector_not_exists', 'trigger', 'trigger_args',
                        'trigger_delay', 'trigger_wait_pageload', 'custom'):

                    self.warn('"%s" is not a valid expect field.' % key)

            item['selector_exists'] = make_list(item.get('selector_exists'))
            item['selector_not_exists'] = make_list(
                    item.get('selector_not_exists'))

        self._expects = newlist


    def set_timeout_expects(self, timeout, expects):
        self._expects_timer.start(timeout * 1000)
        self._expects_if_timeout = make_list(expects)


    def set_upload_files(self, filenames):
        self.web_page.upload_files = make_list(filenames)


    def add_handler(self, name, value):
        self._handlers[name] = value


    def clear_handlers(self):
        # clear handlers registration
        self._handlers = {
            'core.next_queue': self._on_next_queue_trigger,
            'core.page_not_found': self._on_page_not_found_trigger}


    def load(self, url):
        self.web_view.load(QUrl(url))


    def info(self, message):
        self.log_event.emit(INFO, message, 'default')

    def debug(self, message):
        self.log_event.emit(DEBUG, message, 'default')

    def error(self, message):
        self.log_event.emit(ERROR, message, 'default')

    def warn(self, message):
        self.log_event.emit(WARNING, message, 'default')


    def exit(self, return_code):
        self.web_view.hide()
        self._expects_active = False
        self.web_view.stop()
        self._exit_timer.timeout.connect(partial(
                super(Application, self).exit, return_code))

        self._exit_timer.start(1000)


    def _url_matched_expectation(self, expect, scheme, netloc, path, query,
            segment):

        if 'host' in expect and not re.match(expect['host'], netloc):
            self.debug('%s location.host: "%s" "%s"' % (expect['trigger'],
                    expect['host'], netloc))
            return False

        if 'path' in expect and not re.match(expect['path'], path):
            self.debug('%s location.pathname: "%s" "%s"' % (expect['trigger'],
                    expect['path'], path))
            return False

        if 'hash' in expect and not re.match(expect['hash'], segment):
            self.debug('%s location.hash: "%s" "%s"' % (expect['trigger'],
                    expect['hash'], segment))
            return False

        return True 


    def process_expectations(self, expect, frame, urlparts):
        if not self._url_matched_expectation(expect, *urlparts):
            return

        document = frame.documentElement()

        for selector in expect.get('selector_exists', []):
            if document.findFirst(selector).isNull():
                self.debug('%s selector_exists: %s' % (expect['trigger'],
                        selector))
                return

        for selector in expect.get('selector_not_exists', []):
            if not document.findFirst(selector).isNull():
                self.debug('%s selector_not_exists: %s' % (expect['trigger'],
                        selector))
                return

        if 'custom' in expect and not expect['custom'](self, frame, *urlparts):
            return

        self.debug('%s triggered.' % expect['trigger'])
        self._expects_active = False

        trigger_delay = expect.get('trigger_delay', 0)
        if trigger_delay:
            try:
                self._trigger_delay_timer.timeout.disconnect()
            except Exception as e:
                pass

            self._trigger_delay_timer.timeout.connect(partial(self.trigger,
                    frame=frame, trigger_name=expect['trigger'],
                    trigger_args=expect.get('trigger_args', [])))

            self._trigger_delay_timer.start(trigger_delay * 1000)
        else:
            self.trigger(frame, expect['trigger'],
                    expect.get('trigger_args', []))


    def trigger(self, frame, trigger_name, trigger_args):
        if self._trigger_delay_timer.isActive():
            self._trigger_delay_timer.stop()

        trigger_args = dict((str(key), trigger_args[key]) for \
                key in trigger_args)

        if trigger_name in self._handlers:
            self._handlers[trigger_name](self, frame, **trigger_args)
        else:
            self.error('No handler for trigger %s.' % trigger_name)
            self.exit(-1)


    @staticmethod
    def _on_page_not_found_trigger(app, frame):
        app.error('PageNotFound: %s.' % frame.baseUrl().toString())
        app.exit(-1)


    @staticmethod
    def _on_next_queue_trigger(app, frame=None):
        if not app._active_task is None:
            app._queue.task_done()

        try:
            app._active_task = task = app._queue.get(timeout=15)
        except Empty:
            app.info('No more task in the queue.')
            app.web_view.close()
            app.exit(0)
            return

        expects = make_list(task['expects'])
        for expect in expects:
            expect['trigger_wait_pageload'] = True

        app.set_expects(expects)
        app.load(task['goto'])


    def _on_expects_timeout(self):
        self.debug('No expectations were fulfilled after a periode.')
        self.set_expects(self._expects_if_timeout or [])
        self.web_page.triggerAction(QWebPage.Stop)


    def _on_frame_created(self, frame):
        """ Called when QWebPage created a QWebFrame """
        frame_name = 'frame-' + uuid4().hex
        frame.setObjectName(frame_name)
        frame_data = {
            ENUM_FRAME_DATA_ACTIVE: False,
            ENUM_FRAME_DATA_TIMER_CALLBACK: partial(self._on_frame_timer,
                    frame=frame),

            ENUM_FRAME_DATA_TIMER_COUNTER: 0,
        }

        with self._frame_data_lock:
            self._frame_data[frame_name] = frame_data

        self._frame_timer.timeout.connect(
                frame_data[ENUM_FRAME_DATA_TIMER_CALLBACK])

        frame.destroyed.connect(self._on_frame_destroyed)
        #frame.javaScriptWindowObjectCleared.connect(partial(
        #        self._on_frame_reset, frame=frame))
        frame.loadFinished.connect(partial(
                self._on_frame_loaded, frame=frame))


    def _on_frame_destroyed(self, frame):
        """ Called when QWebFrame was destroyed """
        frame_name = str(frame.objectName())
        with self._frame_data_lock:
            frame_data = self._frame_data.get(frame_name)
            if frame_data is None:
                return

            del self._frame_data[frame_name]
            self._frame_timer.timeout.disconnect(
                    frame_data[ENUM_FRAME_DATA_TIMER_CALLBACK])


    def _on_frame_loaded(self, success, frame=None):
        self._on_frame_reset(frame)


    def _on_frame_reset(self, frame=None):
        """
        Called when the javascript `window` object were destroyed, usually just
        before page reload.
        """
        if frame is None:
            # this happens if the frame was forced stop, probably, not sure
            self.error('Problem while loading the page.')
            self.exit(-1)
            return
        self.debug('DOMContentLoaded ' + frame.baseUrl().toString())

        frame.evaluateJavaScript("""
            window.bot = {
                click: function(el) {
                    if (el.click) {
                        el.click()
                    }
                    else if (el.fireEvent) {
                        el.fireEvent('onclick');
                    }
                    else {
                        var evt = document.createEvent('Events');
                        evt.initEvent('click', true, false);
                        el.dispatchEvent(evt);
                    }
                },
            };
        """)

        frame_data = self.get_frame_related_data(frame)
        frame_data[ENUM_FRAME_DATA_TIMER_COUNTER] = 0
        frame_data[ENUM_FRAME_DATA_ACTIVE] = True


    def _on_frame_timer(self, frame):
        if not self._expects_active:
            # we have obsolete expects
            return

        frame_data = self.get_frame_related_data(frame)
        if frame_data is None:
            return

        if not frame_data[ENUM_FRAME_DATA_ACTIVE]:
            # the frame hasn't been fully loaded
            return

        wait_pageload = False

        urlparts = urlsplit(str(frame.baseUrl().toString()))
        for expect in self._expects:
            # is it an obsolete frame
            if expect.get('trigger_wait_pageload', False) and \
                    frame_data[ENUM_FRAME_DATA_TIMER_COUNTER] > 0:

                wait_pageload = True
                continue

            self.process_expectations(expect, frame, urlparts)
            if not self._expects_active:
                # one of the triggers has been activated
                break

        if not wait_pageload:
            frame_data[ENUM_FRAME_DATA_TIMER_COUNTER] += 1


    def _pyqt4_null_message_handler(self, msgtype, msg):
        """ Nuke Qt related error messages """
        self.log_event.emit(DEBUG, str(msg), 'qt')


    def _pyqt5_null_message_handler(self, msgtype, msgctx, msg):
        """ Nuke Qt related error messages """
        self.log_event.emit(DEBUG, str(msg), 'qt')


    def _on_http_response(self, response):
        error = response.error()
        if error == QNetworkReply.NoError:
            return

        url = str(response.url().toString())
        scheme, netloc, path, query, segment = urlsplit(url)
        filename, ext = os.path.splitext(path)

        if len(ext) and ext[1:] in ('gif', 'css', 'js', 'png', 'jpg', 'jpeg',
                'ico'):

            return

        status_code = int(response.attribute(
                QNetworkRequest.HttpStatusCodeAttribute).toInt())

        for expect in self._expects:
            if self._url_matched_expectation(expect, scheme, netloc,
                    path, query, segment):

                self.log_event.emit(WARNING, '%s: %s' % (status_code, url),
                        'http')

                break
        else:
            self.log_event.emit(DEBUG, '%s: %s' % (status_code, url), 'http')


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'application_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
