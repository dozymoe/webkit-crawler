from functools import partial
from logging import DEBUG, ERROR, INFO, WARNING
from PyQt4.QtCore import pyqtSignal, pyqtSlot, pyqtProperty, QObject, QTimer

class FrameData(QObject):
    _name = ''

    def _get_name(self):
        return self._name

    def set_name(self, value):
        self._name = value

    name = pyqtProperty(str, fget=_get_name)


class Proxy(QObject):
    _expects = None
    _data = None
    _delay_timer = None


    onTrigger = pyqtSignal(str, 'QVariantMap', FrameData)

    def _trigger(self, trigger_name, trigger_args, frame_data):
        self.onTrigger.emit(trigger_name, trigger_args, frame_data)

    @pyqtSlot(str, 'QVariantMap', int, FrameData)
    def trigger(self, trigger_name, trigger_args, trigger_delay, frame_data):
        self._active = False
        if trigger_delay > 0:
            try:
                self._delay_timer.timeout.disconnect()
            except:
                pass

            self._delay_timer.timeout.connect(partial(self._trigger,
                    trigger_name=trigger_name, trigger_args=trigger_args,
                    frame_data=frame_data))

            self._delay_timer.start(trigger_delay * 1000)
        else:
            self._trigger(trigger_name, trigger_args, frame_data)


    onCallHandler = pyqtSignal(str, 'QVariantMap', FrameData)

    @pyqtSlot(str, 'QVariantMap', FrameData)
    def call(self, handler_name, handler_args, frame_data):
        self.onCallHandler.emit(handler_name, handler_args, frame_data)


    _active = False

    def _get_active(self):
        return self._active

    def _set_active(self, value):
        self._active = value

    active = pyqtProperty(bool, fget=_get_active, fset=_set_active)


    _trigger_wait_page_load = False

    def _get_trigger_wait_page_load(self):
        return self._trigger_wait_page_load

    def _set_trigger_wait_page_load(self, value):
        self._trigger_wait_page_load = value

    trigger_wait_page_load = pyqtProperty(bool,
            fget=_get_trigger_wait_page_load, fset=_set_trigger_wait_page_load)


    def _get_expects(self):
        return self._expects

    def set_expects(self, value):
        self._expects = value
        self._active = True

    expects = pyqtProperty('QVariantList', fget=_get_expects)


    def _get_data(self):
        return self._data

    def _set_data(self, value):
        self._data = value

    data = pyqtProperty('QVariantMap', fget=_get_data, fset=_set_data)


    onAddQueue = pyqtSignal('QVariantMap')

    @pyqtSlot('QVariantMap')
    def add_queue(self, task):
        self.onQueue.emit(task)


    onLog = pyqtSignal(int, str)

    @pyqtSlot(str)
    def info(self, message):
        self.onLog.emit(INFO, message)

    @pyqtSlot(str)
    def debug(self, message):
        self.onLog.emit(DEBUG, message)

    @pyqtSlot(str)
    def error(self, message):
        self.onLog.emit(ERROR, message)

    @pyqtSlot(str)
    def warn(self, message):
        self.onLog.emit(WARNING, message)


    def __init__(self):
        super(Proxy, self).__init__()
        self._delay_timer = QTimer()
