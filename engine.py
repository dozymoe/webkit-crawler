import logging
import sys
from PyQt4.QtGui import QApplication
from PyQt4.QtCore import QUrl, QObject, pyqtSignal, pyqtSlot, pyqtProperty, QTimer
from PyQt4.QtWebKit import QWebPage, QWebView
from queue import Empty, Queue

def log_message(logger, level, message):
    if logger:
        logger.log(level, message)
    elif level in (logging.ERROR, logging.FATAL, logging.WARNING):
        sys.stderr.write(message)
        sys.stderr.write('\n')
    else:
        sys.stdout.write(message)
        sys.stdout.write('\n')


def is_non_string_iterable(data):
    # http://stackoverflow.com/a/17222092
    try:
        if isinstance(data, unicode) or isinstance(data, str):
            return False
    except NameError:
        pass
    if isinstance(data, bytes):
        return False
    try:
        iter(data)
    except TypeError:
        return False
    try:
        hasattr(None, data)
    except TypeError:
        return True
    return False


def make_list(items, nodict=False):
    if items is None:
        return []
    elif not is_non_string_iterable(items):
        return [items]
    elif nodict and isinstance(items, dict):
        return [items]
    else:
        return items


class Proxy(QObject):
    _log = None
    _expects = None


    onTrigger = pyqtSignal(str, 'QVariantMap')

    @pyqtSlot(str, 'QVariantMap')
    def trigger(self, trigger_name, trigger_args):
        self._active = False
        self.onTrigger.emit(trigger_name, trigger_args)


    _active = False

    def _get_active(self):
        return self._active

    def set_active(self, value):
        self._active = value

    active = pyqtProperty(bool, fget=_get_active)


    _wait_page_reload = False

    def _get_wait_page_reload(self):
        return self._wait_page_reload

    def _set_wait_page_reload(self, value):
        self._wait_page_reload = value

    wait_page_reload = pyqtProperty(bool, fget=_get_wait_page_reload,
            fset=_set_wait_page_reload)


    def _get_expects(self):
        return self._expects

    def set_expects(self, value):
        self._expects = value
        self._active = True

    expects = pyqtProperty('QVariantList', fget=_get_expects)


    onAddQueue = pyqtSignal('QVariantMap')

    @pyqtSlot('QVariantMap')
    def add_queue(self, task):
        self.onQueue.emit(task)


    @pyqtSlot(str)
    def info(self, message):
        log_message(self._log, logging.INFO, message)

    @pyqtSlot(str)
    def debug(self, message):
        log_message(self._log, logging.DEBUG, message)

    @pyqtSlot(str)
    def error(self, message):
        log_message(self._log, logging.ERROR, message)

    @pyqtSlot(str)
    def warn(self, message):
        log_message(self._log, logging.WARNING, message)


    def __init__(self):
        super().__init__()
        self._expects = {}


class WebPage(QWebPage):
    _log = None

    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        log_message(self._log, logging.WARNING, 'Javascript:%s:%s: %s' % (
                sourceID, lineNumber, message))


class Application(QApplication):
    _log = None
    _queue = None
    _handlers = None
    _active_task = None
    _timeout_expects = None
    _visible = False

    def __init__(self, argv, logger=None, load_images=False, show=True):
        super().__init__(argv)

        self._log = logger
        self._visible = show

        self.web_page = WebPage()
        self.web_page._log = logger

        st = self.web_page.settings()
        st.setAttribute(st.AutoLoadImages, load_images)

        self.web_view = QWebView()
        self.web_view.setPage(self.web_page)
        self.web_view.loadFinished.connect(self._on_pageload_finished)

        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timeout)

        self.proxy = Proxy()
        self.proxy._log = logger
        self.proxy.onAddQueue.connect(self.add_queue)
        self.proxy.onTrigger.connect(self._on_trigger)

        self._queue = Queue()

        self.clear_handlers()


    def start(self):
        self._on_next_queue()
        if self._visible:
            self.show()
        sys.exit(self.exec_())


    def _on_next_queue(self, app=None):
        if not self._active_task is None:
            self._queue.task_done()

        try:
            self._active_task = task = self._queue.get(timeout=15)
        except Empty:
            log_message(self._log, logging.INFO, 'No more task in queue')
            self.exit(0)
            return

        self.proxy.set_expects(task['expects']);

        self.proxy.wait_page_reload = True
        self.web_page.currentFrame().load(QUrl(task['goto']))


    def show(self):
        self.web_view.show()


    def add_queue(self, task):
        self._queue.put(task)


    def _on_timeout(self):
        log_message(self._log, logging.DEBUG, 'Expects timeout')
        self.set_expects(self._timeout_expects or [])
        self.web_page.triggerAction(QWebPage.Stop)


    def _on_pageload_finished(self, successful):
        log_message(self._log, logging.DEBUG, 'DOM content loaded')

        self.proxy.wait_page_reload = False
        self.frame = self.web_page.currentFrame()
        self.frame.addToJavaScriptWindowObject('bot', self.proxy)
        self.frame.evaluateJavaScript("""
            (function() {
                function process_expectation(expect) {
                    var selectors;

                    if (expect.path) {
                        var path = document.location.pathname;

                        bot.debug(expect.trigger + ' location.pathname: "' +
                            path + '" "' + expect.path + '"');

                        if (!expect.path.match(path)) return;
                    }

                    if (expect.hash) {
                        var hash = document.location.hash;

                        bot.debug(expect.trigger + ' location.hash: "' + hash +
                                '" "' + expect.hash + '"');

                        if (!expect.hash.match(hash)) return;
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
                    bot.trigger(expect.trigger, expect.triggerArgs || {});
                }

                setInterval(function() {
                    if (!bot.active || bot.wait_page_reload) return;

                    for (var ii = 0; ii < bot.expects.length; ii++) {
                        process_expectation(bot.expects[ii]);
                    }
                }, 3000);

                window.bothelp_clickElement = function(el) {
                    if (el.click) {
                        el.click();
                    }
                    else {
                        var evt = document.createEvent('MouseEvents');
                        evt.initMouseEvent('click', true, true, window, 0, 0, 0, 0, 0, false, false, false, false, 0, null);
                        el.dispatchEvent(evt);
                    }
                };
            }());
        """)


    def execjs(self, text):
        return self.frame.evaluateJavaScript(text)


    def set_expects(self, expects):
        newlist = make_list(expects)
        for item in newlist:
            for key in item:
                if not key in ('path', 'hash', 'selectorExists',
                        'selectorNotExists', 'trigger', 'triggerArgs'):

                    log_message(self._log, logging.WARNING,
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


    def _on_trigger(self, trigger_name, trigger_args):
        if trigger_name in self._handlers:
            self._handlers[trigger_name](self, **trigger_args)
        else:
            log_message(self._log, logging.ERROR,
                    'no handler for trigger %s' % trigger_name)
            self.exit(-1)
