from logging import DEBUG, ERROR, INFO, WARNING
try:
    from PyQt5.QtCore import pyqtSignal
    from PyQt5.QtWebKitWidgets import QWebPage
    QStringList = list
except ImportError:
    from PyQt4.QtCore import pyqtSignal
    from PyQt4.QtWebKit import QWebPage
    try:
        from PyQt4.QtCore import QStringList
    except ImportError:
        QStringList = list


class WebPage(QWebPage):
    """
    QWebPage that prints Javascript errors to logger.

    Adapted from http://www.tylerlesmann.com/2009/oct/01/web-scraping-pyqt4/
    """
    log_event = pyqtSignal(int, str, str)
    upload_files = None

    def chooseFile(self, frame=None, suggested=''):
        self.log_event.emit(DEBUG, 'FileUpload:suggestedFile: %s' % suggested)
        if self.upload_files is not None:
            files = self.upload_files
            self.upload_files = None
            return files[0]

        return super(WebPage, self).chooseFile(frame, suggested)


    def extension(self, extension, option, output):
        self.log_event.emit(DEBUG, 'MultipleFileUpload')

        if extension == self.ChooseMultipleFilesExtension and \
                self.upload_files is not None:

            files = self.upload_files
            self.upload_files = None
            output.fileNames = QStringList(files)
            return True

        return super(WebPage, self).extension(extension, option, output)


    def javaScriptAlert(self, frame, message):
        self.log_event.emit(WARNING, 'Alert: %s' % message, 'javascript')
        super(WebPage, self).javaScriptAlert(frame, message)


    def javaScriptConfirm(self, frame, message):
        self.log_event.emit(DEBUG, 'Confirm: %s' % message, 'javascript')
        return super(WebPage, self).javaScriptConfirm(frame, message)


    def javaScriptConsoleMessage(self, message, lineNumber, sourceID):
        self.log_event.emit(DEBUG, 'Log:%s:%s: %s' % (sourceID,
                lineNumber, message), 'javascript')


    def javaScriptPrompt(self, frame, message, default, result):
        self.log_event.emit(DEBUG, 'Prompt: %s' % message, 'javascript')
        return super(WebPage, self).javaScriptPrompt(frame, message, default,
                result)
