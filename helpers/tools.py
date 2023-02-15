import os
import time
from pathlib import Path
from threading import Thread
from typing import Union

from PyQt5.QtCore import QObject, pyqtSignal, QBuffer, QIODevice, QPoint, QSize
from PyQt5.QtGui import QPixmap


def time_method(method):
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = method(*args, **kwargs)
        end_time = time.time()
        print(f"{method.__name__} took {end_time - start_time:.2f} seconds to run")
        return result
    return wrapper


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


class PathManager:
    __BASE_PATH__ = None  # initially set by main function

    @staticmethod
    def _combine_path(args, filename=None):
        if filename is not None:
            args.append(filename)
        return os.path.join(*args)

    @staticmethod
    def get_project_base_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__], filename)

    @staticmethod
    def get_new_emoji_data_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'emojis_new'], filename)

    @staticmethod
    def get_new_emoji_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'emojis_new', 'ios_emojis'], filename)

    @staticmethod
    def get_image_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'images'], filename)

    @staticmethod
    def get_icon_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'icons'], filename)

    @staticmethod
    def get_emoji_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'emojis'], filename)

    @staticmethod
    def get_calendar_default_icons_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'default_calendar_icons'], filename)

    @staticmethod
    def get_weather_icon_set_path(icon_set_name: str, filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'weather_icons', icon_set_name],
                                         filename)

    @staticmethod
    def get_html_path(filename=None):
        return PathManager._combine_path([PathManager.__BASE_PATH__, 'resources', 'html'], filename)

    @staticmethod
    def join_path(*args):
        return PathManager._combine_path([PathManager.__BASE_PATH__,  *args])

    @staticmethod
    def make_path(path: Union[str, Path]):
        try:
            if isinstance(path, Path):
                path.mkdir()
            else:
                Path(PathManager.join_path(path)).mkdir()
        except FileExistsError:
            pass

