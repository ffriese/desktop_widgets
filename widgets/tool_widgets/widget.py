import logging

from PyQt5.QtWidgets import QWidget


class Widget(QWidget):

    def log(self, debug_msg, *args, level=logging.DEBUG):
        if type(debug_msg) is not str:
            debug_msg = str(debug_msg)
        if args:
            debug_msg = f"{debug_msg} {' '.join([str(a) for a in args])}"
        logging.getLogger(self.__class__.__name__).log(level, debug_msg)

    def log_info(self, debug_msg, *args):
        self.log(debug_msg, *args, level=logging.INFO)

    def log_debug(self, debug_msg, *args):
        self.log(debug_msg, *args, level=logging.DEBUG)

    def log_warn(self, debug_msg, *args):
        self.log(debug_msg, *args, level=logging.WARN)

    def log_error(self, debug_msg, *args):
        self.log(debug_msg, *args, level=logging.ERROR)

    def log_fatal(self, debug_msg, *args):
        self.log(debug_msg, *args, level=logging.FATAL)
