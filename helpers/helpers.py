from threading import Thread
from typing import Union

from PyQt5.QtCore import QObject, pyqtSignal, QBuffer, QIODevice, QPoint, QSize
from PyQt5.QtGui import QPixmap


class SignalWrapper(object):
    """
    Wrapper class to use for non QObjects
    """

    def create_wrapper(self, *args):
        class Wrapper(QObject):
            signal = pyqtSignal(*args)

            def __init__(self):
                super().__init__()

        return Wrapper

    def __init__(self, *args):
        self.wrapped = self.create_wrapper(*args)()

    def connect(self, slot):
        self.wrapped.signal.connect(slot)

    def disconnect(self, *slot):
        self.wrapped.signal.disconnect(*slot)

    def emit(self, *args):
        self.wrapped.signal.emit(*args)


# noinspection PyUnresolvedReferences
class SignalingThread(Thread):

    def __init__(self, group=None, target=None, name=None,
                 args=(), kwargs=None, *, daemon=None):
        super().__init__(group, target, name, args, kwargs, daemon=daemon)
        self.finished = SignalWrapper(object)

    def run(self) -> None:
        try:
            if self._target:
                result = self._target(*self._args, **self._kwargs)
                self.finished.emit(result)
        finally:
            # Avoid a ref-cycle if the thread is running a function with
            # an argument that has a member that points to the thread.
            del self._target, self._args, self._kwargs


class ImageTools:
    @staticmethod
    def pixmap_to_base64(pixmap: QPixmap) -> str:
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pixmap.save(buffer, "PNG", quality=100)
        image = bytes(buffer.data().toBase64()).decode()
        return f"<img src='data:image/png;base64, {image}'>"


def tup2str(tup: Union[QPoint, QSize]):
    if isinstance(tup, QPoint):
        return f"{tup.x()}.{tup.y()}"
    else:
        return f"{tup.width()}x{tup.height()}"


# https://stackoverflow.com/a/44549081
# author: Ian Chen
from collections import OrderedDict
from collections.abc import MutableMapping


class LRUCache(MutableMapping):
    def __init__(self, max_len, items=None):
        self._max_len = max_len
        self.d = OrderedDict()
        if items:
            for k, v in items:
                self[k] = v

    @property
    def max_len(self):
        return self._max_len

    def __getitem__(self, key):
        self.d.move_to_end(key)
        return self.d[key]

    def __setitem__(self, key, value):
        if key in self.d:
            self.d.move_to_end(key)
        elif len(self.d) == self.max_len:
            self.d.popitem(last=False)
        self.d[key] = value

    def __delitem__(self, key):
        del self.d[key]

    def __iter__(self):
        return self.d.__iter__()

    def __len__(self):
        return len(self.d)
