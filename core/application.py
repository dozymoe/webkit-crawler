import os
from collections import OrderedDict
from functools import partial
try:
    # python2.6 support
    from simplejson import load as json_load
except ImportError:
    from json import load as json_load
from logging import DEBUG, ERROR, INFO, WARNING
from PyQt4.QtGui import QApplication
from PyQt4.QtCore import QUrl, QTimer, pyqtSignal, qInstallMsgHandler
from PyQt4.QtWebKit import QWebFrame, QWebPage, QWebView
try:
    from queue import Empty, Queue
except ImportError:
    from Queue import Empty, Queue
from uuid import uuid4

from core.helpers import flatten_settings_definition, make_list
from core.proxy import FrameData, Proxy

def null_message_handler(*args, **kwargs):
    pass

# disable qt related messages
qInstallMsgHandler(null_message_handler)


class WebPage(QWebPage):
    """
    QWebPage that prints Javascript errors to logger.

    Adapted from http://www.tylerlesmann.com/2009/oct/01/web-scraping-pyqt4/
    """
    onLog = pyqtSignal(int, str)

    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        self.onLog.emit(DEBUG, 'Javascript:%s:%s: %s' % (sourceID, lineNumber,
                message))


class Application(QApplication):
    _queue = None
    _handlers = None
    _active_task = None
    _timeout_expects = None
    _visible = False
    _frames_data = None

    onLog = pyqtSignal(int, str)

    def __init__(self, settings):
        super(Application, self).__init__([])

        self.settings = settings
        self._frames_data = {}
        self._visible = int(self.settings['application.visible'])

        self.web_page = WebPage()
        self.web_page.onLog.connect(self.onLog)
        self.web_page.frameCreated.connect(self._on_frame_created)

        frame = self.web_page.mainFrame()
        frame_data = self._register_frame(frame)

        frame.javaScriptWindowObjectCleared.connect(partial(
                self._on_pageload_finished, frame=frame))

        st = self.web_page.settings()
        st.setAttribute(
            st.AutoLoadImages,
            int(self.settings['application.settings.load_images']))

        self.web_view = QWebView()
        self.web_view.setPage(self.web_page)

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timeout)

        self.proxy = Proxy()
        self.proxy.onLog.connect(self.onLog)
        self.proxy.onAddQueue.connect(self.add_queue)
        self.proxy.onTrigger.connect(self._on_trigger)
        self.proxy.onCallHandler.connect(self._on_call_handler)

        self._queue = Queue()

        self.clear_handlers()


    def start(self):
        self._on_next_queue()
        if self._visible:
            self.show()
        return self.exec_()


    def _on_next_queue(self, app=None):
        if not self._active_task is None:
            self._queue.task_done()

        try:
            self._active_task = task = self._queue.get(timeout=15)
        except Empty:
            self.onLog.emit(INFO, 'No more task in queue')
            self.exit(0)
            return

        self.proxy.set_expects(task['expects']);

        self.proxy._trigger_wait_page_load = True
        self.web_page.mainFrame().load(QUrl(task['goto']))


    def show(self):
        self.web_view.show()


    def add_queue(self, task):
        self._queue.put(task)


    def _on_timeout(self):
        self.onLog.emit(DEBUG, 'Expects timeout')
        self.set_expects(self._timeout_expects or [])
        self.web_page.triggerAction(QWebPage.Stop)


    def _register_frame(self, frame):
        data = FrameData()
        data.set_name('frame-' + uuid4().hex)
        frame.setObjectName(data.name)

        self._frames_data[data.name] = data
        return data


    def _on_frame_created(self, frame):
        frame_data = self._register_frame(frame)
        frame.javaScriptWindowObjectCleared.connect(partial(
                self._on_pageload_finished, frame=frame))

        frame.destroyed.connect(self._on_frame_destroyed)


    def _on_frame_destroyed(self, frame):
        del self._frames_data[str(frame.objectName())]


    def _on_pageload_finished(self, frame=None):
        if frame is None:
            # this happens if the frame was forced stop, probably, not sure
            self.error('Problem while loading the page.')
            self.exit(-1)
            return

        self.proxy._trigger_wait_page_load = False
        self.onLog.emit(DEBUG, 'DOMContentLoaded ' + frame.baseUrl().toString())

        frame.addToJavaScriptWindowObject('bot', self.proxy)
        frame.addToJavaScriptWindowObject('botFrameData',
                self._frames_data[str(frame.objectName())])

        frame.evaluateJavaScript("""
            (function() {
                function process_expectation(expect) {
                    var selectors;

                    if (expect.host) {
                        var host = document.location.host;

                        if (!expect.host.match(host)) {
                            bot.debug(expect.trigger + ' location.host: "' +
                                    host + '" "' + expect.host + '"');

                            return;
                        }
                    }

                    if (expect.path) {
                        var path = document.location.pathname;

                        if (!expect.path.match(path)) {
                            bot.debug(expect.trigger + ' location.pathname: "' +
                                    path + '" "' + expect.path + '"');

                            return;
                        }
                    }

                    if (expect.hash) {
                        var hash = document.location.hash;

                        if (!expect.hash.match(hash)) {
                            bot.debug(expect.trigger + ' location.hash: "' +
                                    hash + '" "' + expect.hash + '"');

                            return;
                        }
                    }

                    selectors = expect.selectorNotExists || [];
                    for (var ii = 0; ii < selectors.length; ii++) {
                        if (document.querySelector(selectors[ii])) {
                            bot.debug(expect.trigger + ' selector-not-exists: '
                                    + selectors[ii]);

                            return;
                        }
                    }

                    selectors = expect.selectorExists || [];
                    for (var ii = 0; ii < selectors.length; ii++) {
                        if (!document.querySelector(selectors[ii])) {
                            bot.debug(expect.trigger + ' selector-exists: '
                                    + selectors[ii]);

                            return;
                        }
                    }

                    bot.info(expect.trigger + ' triggered.');
                    bot.trigger(expect.trigger, expect.triggerArgs || {},
                             expect.triggerDelay || 0, botFrameData);
                }

                window.bothelp_clickElement = function(el) {
                    if (el.fireEvent) {
                        el.fireEvent('onclick');
                    }
                    else {
                        var evt = document.createEvent('Events');
                        evt.initEvent('click', true, false);
                        el.dispatchEvent(evt);
                    }
                };

                document.addEventListener('DOMContentLoaded', function() {
                    window.setInterval(function() {
                        if (!bot.active || bot.trigger_wait_page_load) return;

                        for (var ii = 0; ii < bot.expects.length; ii++) {
                            process_expectation(bot.expects[ii]);
                        }
                    }, 3000);
                });
            }());
        """)


    def execjs(self, text):
        return self.frame.evaluateJavaScript(text)


    def set_expects(self, expects):
        newlist = make_list(expects)
        for item in newlist:
            for key in item:
                if not key in ('path', 'hash', 'host', 'selectorExists',
                        'selectorNotExists', 'trigger', 'triggerArgs',
                        'triggerDelay'):

                    self.onLog.emit(
                        WARNING,
                        '%s is not a valid expect field' % key)

            item['selectorExists'] = make_list(item.get('selectorExists'))
            item['selectorNotExists'] = make_list(item.get('selectorNotExists'))

        self.proxy.set_expects(newlist)


    def set_timeout_expects(self, timeout, expects):
        self.timer.start(timeout * 1000)
        self._timeout_expects = timeout_expects


    def add_handler(self, name, value):
        self._handlers[name] = value


    def clear_handlers(self):
        # clear handlers registration
        self._handlers = {'bot.nextQueue': self._on_next_queue}


    def _on_trigger(self, trigger_name, trigger_args, frame_data):
        # in python2 QString can't be used as dictionary keys
        trigger_name = str(trigger_name)
        trigger_args = dict((str(key), trigger_args[key]) for \
                key in trigger_args)

        if trigger_name in self._handlers:
            self.frame = self.web_page.findChild(QWebFrame, frame_data.name)
            self._handlers[trigger_name](self, **trigger_args)
        else:
            self.onLog.emit(ERROR, 'no handler for trigger %s' % trigger_name)
            self.exit(-1)


    def _on_call_handler(self, handler_name, handler_args, frame_data):
        # in python2 QString can't be used as dictionary keys
        handler_name = str(handler_name)
        handler_args = dict((str(key), handler_args[key]) for \
                key in handler_args)

        if handler_name in self._handlers:
            self.frame = self.web_page.findChild(QWebFrame, frame_data.name)
            self._handlers[handler_name](self, **handler_args)
        else:
            self.onLog.emit(ERROR, 'no handler for call %s' % handler_name)
            self.exit(-1)


    def info(self, message):
        self.onLog.emit(INFO, message)

    def debug(self, message):
        self.onLog.emit(DEBUG, message)

    def error(self, message):
        self.onLog.emit(ERROR, message)

    def warn(self, message):
        self.onLog.emit(WARNING, message)


def get_settings_definition():
    settings_filename = os.path.join(os.path.dirname(__file__),
            'application_settings.json')

    with open(settings_filename) as f:
        settings = json_load(f, object_pairs_hook=OrderedDict)

    return flatten_settings_definition(settings)
