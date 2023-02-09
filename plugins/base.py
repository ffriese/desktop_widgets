import logging
import time
import traceback
from datetime import datetime
from typing import Union

from PyQt5.QtCore import QObject, pyqtSignal

from helpers.helpers import SignalingThread
from termcolor import colored


class BasePlugin(QObject):

    plugin_log = pyqtSignal(str, int)
    new_data_available = pyqtSignal(object)
    threaded_exception = pyqtSignal(Exception)

    def __init__(self):
        super(BasePlugin, self).__init__()
        self.update_thread = None
        self.last_update = datetime.now()
        self.currently_updating = False

    def setup(self, *args):
        raise NotImplementedError()

    def quit(self):
        pass

    def update_async(self, *args, **kwargs) -> None:
        if not self.currently_updating:
            self.currently_updating = True
            self.update_thread = SignalingThread(target=self._update_sync, args=args, kwargs=kwargs)
            self.update_thread.finished.connect(self._new_data_ready)
            self.update_thread.setDaemon(True)
            self.update_thread.start()

    def _new_data_ready(self, results) -> None:
        self.currently_updating = False
        if isinstance(results, Exception):
            return
        self.new_data_available.emit(results)

    def _update_sync(self, allow_cache=False, *args, **kwargs) -> object:
        """
         wrapper function to pass exceptions to the widget for handling

        """
        try:
            start = time.time()
            result = self.update_synchronously(*args, **kwargs)
            self.log(f'returned after {time.time() - start:.2f} seconds')
            self.last_update = datetime.now()
            return result
        except NotImplementedError as ne:
            raise ne
        except Exception as e:
            self.log(self, 'CAUGHT EXCEPTION IN UPDATE SYNC:', e, type(e), level=logging.ERROR)
            self.threaded_exception.emit(e)
            return e

    def update_synchronously(self, *args, **kwargs) -> Union[object, None]:
        """
        synchronous update method for the plugin.
        will be called in a thread to enable an update without blocking
        Args:
            *args:

        Returns:

        """
        raise NotImplementedError(f'{self.__class__.__name__} must implement this method')

    def log(self, debug_msg, *args, level=logging.INFO, exception=None):
        if type(debug_msg) is not str:
            debug_msg = str(debug_msg)
        for a in args:
            debug_msg += ' ' + str(a)
        if level >= logging.ERROR:
            debug_msg = colored(debug_msg, 'red')
        self.plugin_log.emit('[%s]: %s' % (self.__class__.__name__, debug_msg), level)
        if exception:
            self.plugin_log.emit(''.join(traceback.format_exception(None, exception, exception.__traceback__)),
                                 level)

    def log_info(self, debug_msg, *args, **kwargs):
        self.log(debug_msg, *args, level=logging.INFO, **kwargs)

    def log_debug(self, debug_msg, *args, **kwargs):
        self.log(debug_msg, *args, level=logging.DEBUG, **kwargs)

    def log_error(self, debug_msg, *args, **kwargs):
        self.log(debug_msg, *args, level=logging.ERROR, **kwargs)

    def log_warn(self, debug_msg, *args, **kwargs):
        self.log(debug_msg, *args, level=logging.WARN, **kwargs)

    def log_fatal(self, debug_msg, *args, **kwargs):
        self.log(debug_msg, *args, level=logging.FATAL, **kwargs)


class APILimitExceededException(Exception):
    pass


class APIDeprecatedException(Exception):
    pass
