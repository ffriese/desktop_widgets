import os
import sys
import importlib
import webbrowser
from logging.handlers import RotatingFileHandler

from PyQt5 import QtCore
################################################################################
# DO NOT REMOVE! THIS NEEDS TO BE IMPORTED BEFORE QApplication-Start           #
# DO NOT REMOVE! Even if your IDE tells you this is 'unused', it is necessary! #
from PyQt5.QtWebEngineWidgets import QWebEngineView                            #
################################################################################
from PyQt5.QtGui import QIcon, QFont, QScreen
from PyQt5.QtCore import QSettings, QObject, QVariant, pyqtSlot, Qt, QRect
from PyQt5.QtWidgets import *
from threading import Lock
from typing import List, Type, Dict, cast

import signal

from helpers.tools import tup2str
from widgets.base import BaseWidget
from widgets.calendar.calendar_widget import CalendarWidget
from helpers.tools import PathManager
from widgets.music import MusicWidget
from widgets.network import NetworkWidget
import logging

from widgets.tool_widgets.onboarding import OnboardingDialog


class Application(QApplication):
    def event(self, e):
        return QApplication.event(self, e)


class DesktopWidgetsCore(QObject):
    app = Application([])
    app.setStyleSheet("QToolTip {opacity: 200;}")
    app.setFont(QFont('Calibri'))

    QtCore.qInstallMessageHandler(lambda *_: None)
    # define project base path
    if getattr(sys, 'frozen', False):
        # frozen
        dir_ = os.path.dirname(sys.executable)
    else:
        # unfrozen
        dir_ = os.path.dirname(os.path.realpath(__file__))
    os.chdir(dir_)
    PathManager.__BASE_PATH__ = dir_

    @staticmethod
    def screens_to_hash(screens: List[QScreen]):
        screen_dict = {tup2str(screen.geometry().topLeft()): tup2str(screen.geometry().size()) for screen in screens}
        screen_list = sorted(screen_dict.keys())
        string = ';'.join([f"{k}:{screen_dict[k]}" for k in screen_list])
        return string

    def check_widget_positions(self):
        for widget in self.widgets:
            self.restore_widget_geometry(widget)

    def restore_widget_geometry(self, widget):
        geometry: QRect = self.read_geometry(widget)
        # geom =
        # screen_points =
        if geometry is not None:
            for point in [geometry.topLeft(), geometry.topRight(),
                          geometry.bottomLeft(), geometry.bottomRight()]:
                pass
            self.log('>> RESTORING WIDGET GEOMETRY:', geometry)
            QApplication.processEvents()
            widget.setGeometry(geometry)
            QApplication.processEvents()
            widget.setGeometry(geometry)
        else:
            self.log(f"GEOMETRY OF {widget} IS NONE!!!!", level=logging.WARN)

    def get_screen_config(self, app: QApplication):
        self.screen_config = self.screens_to_hash(app.screens())
        self.log(f'current screen-config: {self.screen_config}')
        return self.screen_config

    def screen_connected(self, screen: QScreen):
        app = cast(QApplication, self.sender())
        self.log(f'SCREEN CONNECTED! app:{app}, screen: {screen}')
        self.get_screen_config(app)
        self.check_widget_positions()

    def screen_disconnected(self, screen: QScreen):
        app = cast(QApplication, self.sender())
        self.log(f'SCREEN DISCONNECTED: app:{app}, screen: {screen}')
        self.get_screen_config(app)
        self.check_widget_positions()

    def __init__(self, config='default', available_widgets=None):
        super(DesktopWidgetsCore, self).__init__()
        self.onboarding_dialog = None
        signal.signal(signal.SIGINT, lambda *a: DesktopWidgetsCore.app.quit())
        DesktopWidgetsCore.app.startTimer(200)
        DesktopWidgetsCore.app.setQuitOnLastWindowClosed(False)  # Otherwise DebugWindow kills entire application on close

        DesktopWidgetsCore.app.screenRemoved.connect(self.screen_disconnected)
        DesktopWidgetsCore.app.screenAdded.connect(self.screen_connected)
        self.screen_config = self.get_screen_config(DesktopWidgetsCore.app)
        self.widgets = []  # type: List[BaseWidget]
        self.available_widgets = {}  # type: Dict[str, Type[BaseWidget]]
        self.dbg_win = None
        self.tray_icon = QSystemTrayIcon()
        self.tray_icon.setIcon(self.app.style().standardIcon(QStyle.SP_FileDialogListView))

        self.raise_action = QAction(QIcon(PathManager.get_icon_path('hide_widget.png')),
                                    "Raise Widgets", DesktopWidgetsCore.app)
        self.raise_action.triggered.connect(self.raise_all)
        self.quit_action = QAction(QIcon(PathManager.get_icon_path('logout.png')),
                                   "Quit DesktopWidgets", DesktopWidgetsCore.app)
        self.quit_action.triggered.connect(self.close)
        self.debug_widgets_action = QAction(DesktopWidgetsCore.app.style().standardIcon(QStyle.SP_DialogHelpButton),
                                            "Debug Widgets", DesktopWidgetsCore.app)
        self.debug_widgets_action.triggered.connect(self.debug_widgets)
        self.open_config_action = QAction(DesktopWidgetsCore.app.style().standardIcon(QStyle.SP_DriveFDIcon),
                                          "Open Config", DesktopWidgetsCore.app)
        self.open_config_action.triggered.connect(self.open_config)

        self.tray_menu_actions = {}
        self.tray_menu = QMenu()
        self.tray_menu.setTitle('Widgets')
        self.tray_menu.addAction(self.raise_action)
        # self.tray_menu.addAction(self.debug_widgets_action)
        self.tray_menu.addAction(self.open_config_action)
        self.tray_menu.addAction(self.quit_action)
        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.show()
        self.settings = QSettings('%s.ini' % config, QSettings.IniFormat)
        self.settings.setDefaultFormat(QSettings.IniFormat)
        self.settings_lock = Lock()
        self.log_dbg('=================', logging.INFO, core_msg=True)
        self.log_dbg('| Session Start |', logging.INFO, core_msg=True)
        self.log_dbg('=================', logging.INFO, core_msg=True)

        if available_widgets:
            for w in available_widgets:
                self.register_widget(w)

        if self.settings.childGroups().__contains__(self.__class__.__name__):
            # self.debug('waiting for read-lock')
            with self.settings_lock:
                self.settings.beginGroup(self.__class__.__name__)
                active_widgets = self.settings.value('active_widgets')
                if active_widgets is None:
                    self.activate_widgets = active_widgets = []
                    self.settings.setValue('active_widgets', [])
                self.settings.endGroup()
                self.settings.sync()
            if not active_widgets:
                self.log('no active widgets found. activate from tray.')
                OnboardingDialog.highlight_tray_icon(self.tray_icon, loop_count=10)
            for w in active_widgets:
                if w in self.available_widgets.keys():
                    self.activate_widget(self.available_widgets[w])
                else:
                    self.log('%s was not activated, because it is not registered' % w)
        else:
            self.show_onboarding_dialog()
        self.check_widget_positions()

    def show_onboarding_dialog(self):
        self.onboarding_dialog = OnboardingDialog(None, flags=Qt.WindowCloseButtonHint | Qt.Window)
        self.onboarding_dialog.highlight_tray_icon(self.tray_icon, loop_count=-1)
        self.onboarding_dialog.widget_class_activated.connect(self.activate_widget)
        self.onboarding_dialog.show()

    def open_widget(self):
        action = self.sender()
        widget_class = action.property('widget_class')
        self.activate_widget(widget_class)
        # self.tray_menu.removeAction(action)

    def register_widget(self, widget_class: Type[BaseWidget]):
        if widget_class not in self.available_widgets:
            self.available_widgets[widget_class.__name__] = widget_class
            open_action = QAction(QIcon(),
                                  "Open %s" % widget_class.__name__, DesktopWidgetsCore.app)
            open_action.setProperty('widget_class', widget_class)
            open_action.triggered.connect(self.open_widget)
            self.tray_menu_actions[widget_class] = {'open': open_action}
            self.tray_menu.addAction(open_action)

    def activate_widget(self, widget_class: Type[BaseWidget]):
        self.log('# adding %s...' % widget_class.__name__, level=logging.INFO)
        widget_class = getattr(importlib.import_module(widget_class.__module__), widget_class.__name__)
        widget = widget_class()
        try:
            open_action = self.tray_menu_actions[widget_class]['open']
            self.tray_menu_actions[widget_class].pop('open', None)
            self.tray_menu.removeAction(open_action)
        except KeyError:
            pass
        widget.widget_closed.connect(self.remove_widget)
        widget.widget_updated.connect(self.update_settings)
        widget.widget_geometry_changed.connect(self.update_geometry)
        widget.widget_reload_request.connect(self.reload_widget)
        widget.widget_debug.connect(self.log_dbg)
        self.app.installEventFilter(widget)

        if self.settings.childGroups().__contains__(widget.__class__.__name__):
            # self.debug('waiting for read-lock')
            with self.settings_lock:
                self.settings.beginGroup(widget.__class__.__name__)
                widget_settings = dict()
                for key in self.settings.allKeys():
                    widget_settings[key] = self.settings.value(key)
                self.settings.endGroup()
                self.settings.sync()
            # self.debug('released read-lock')
            for key in widget_settings:
                widget.apply_settings(key, widget_settings[key])

        # else:
        #     widget.show()

        self.restore_widget_geometry(widget)

        self.widgets.append(widget)
        self.tray_menu.addAction(widget.show_action)
        self.tray_menu.addAction(widget.hide_action)
        widget.context_menu.addSeparator()
        widget.context_menu.addAction(widget.reload_action)
        widget.context_menu.addAction(widget.hide_action)
        widget.context_menu.addAction(widget.close_action)
        widget.context_menu.addAction(self.quit_action)
        widget.start()
        widget.show()
        widget.activateWindow()
        widget.raise_()

        self.update_settings('active_widgets', [w.__class__.__name__ for w in self.widgets], sender=self)

    @pyqtSlot()
    def reload_widget(self):
        self.log('>>> reloading %s ...' % self.sender().__class__.__name__)
        # plugins = self.sender().plugins
        self.sender().close()
        importlib.reload(sys.modules[self.sender().__module__])
        # noinspection PyTypeChecker
        self.activate_widget(self.sender().__class__)

    @pyqtSlot()
    def remove_widget(self):
        widget = cast(BaseWidget, self.sender())
        self.widgets.remove(widget)
        self.tray_menu.removeAction(widget.show_action)
        self.tray_menu.removeAction(widget.hide_action)
        widget_class = widget.__class__
        open_action = QAction(QIcon(),
                              "Open %s" % widget_class.__name__, DesktopWidgetsCore.app)
        open_action.setProperty('widget_class', widget_class)
        open_action.triggered.connect(self.open_widget)
        self.tray_menu.addAction(open_action)

        self.update_settings('active_widgets', [w.__class__.__name__ for w in self.widgets], sender=self)

    @pyqtSlot(QRect)
    def update_geometry(self, rect, sender=None):
        if not sender:
            sender = self.sender()
        self.log('updating loc:', sender, self.screen_config, rect)
        with self.settings_lock:
            self.settings.beginGroup(sender.__class__.__name__)
            self.settings.beginGroup('geometry')
            self.settings.setValue(self.screen_config, rect)
            self.settings.endGroup()
            self.settings.endGroup()
            self.settings.sync()

    def read_geometry(self, widget):
        with self.settings_lock:
            self.settings.beginGroup(widget.__class__.__name__)
            self.settings.beginGroup('geometry')
            val = self.settings.value(self.screen_config, None)
            self.settings.endGroup()
            self.settings.endGroup()
            self.settings.sync()
            return val

    @pyqtSlot(str, QVariant)
    def update_settings(self, key, value, sender=None):
        if not sender:
            sender = self.sender()
        if key not in ['size', 'origin', 'hidden',  # working settings, no need to spam the console with debug output
                       'notes_text', 'collapsed_items',
                       'calendars', 'events', 'weather_data']:
            self.log('received settings_update: %s -> %s:%r' % (sender.__class__.__name__, key, value), level=logging.DEBUG)
        # self.debug('waiting for write-lock ')
        with self.settings_lock:
            self.settings.beginGroup(sender.__class__.__name__)
            if value is None:
                self.settings.remove(key)
            else:
                self.settings.setValue(key, value)
            self.settings.endGroup()
            self.settings.sync()
        # self.debug('released write-lock')

    @staticmethod
    def close():
        DesktopWidgetsCore.app.quit()

    def log(self, debug_msg, *args, level=logging.INFO):
        if type(debug_msg) is not str:
            debug_msg = str(debug_msg)
        for a in args:
            debug_msg += str(a)
        self.log_dbg(debug_msg, level, core_msg=True)

    @pyqtSlot(str, int)
    def log_dbg(self, msg, level, core_msg=False):
        if core_msg:
            sender = self.__class__.__name__.upper()
        else:
            sender = self.sender().__class__.__name__
        logging.getLogger(f'desktopwidgets.{sender}').log(level, msg)

    def debug_widgets(self):
        # pass
        if self.dbg_win is not None:
            self.dbg_win.close()
            logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg='dbg_win_closed')
            del self.dbg_win
        # TODO: push subwidgets, but fix debugwindow first
        importlib.reload(sys.modules['subwidgets.dbgwin'])
        logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg='reloaded %s' % sys.modules['subwidgets.dbgwin'])

        window_class = getattr(importlib.import_module('subwidgets.dbgwin'), 'DebugWindow')
        logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg='imported %s' % getattr(importlib.import_module('subwidgets.dbgwin'), 'DebugWindow'))
        self.dbg_win = window_class(self.widgets, parent=None)

    def open_config(self):
        webbrowser.open(self.settings.fileName())

    def raise_all(self):
        for w in self.widgets:
            w.raise_()

    @staticmethod
    def spin():
        DesktopWidgetsCore.app.exec_()


class StreamLogger(object):

    def __init__(self, _logger, log_level=logging.INFO):
        self.logger: logging.Logger = _logger
        self.log_level = log_level

    def write(self, buf):
        for line in buf.rstrip().splitlines():
            self.logger.log(self.log_level, line.rstrip())

    def flush(self):
        pass


if __name__ == '__main__':
    logfile = 'debug.log'

    general_log_level = logging.DEBUG
    console_log_level = logging.INFO

    file_handler = RotatingFileHandler(logfile, maxBytes=1024 * 1024,
                                       backupCount=5, encoding='utf-8')

    STD_OUT_LOG_LEVEL = os.environ.get('STD_OUT_LOG_LEVEL', 'INFO')
    STD_ERR_LOG_LEVEL = os.environ.get('STD_ERR_LOG_LEVEL', 'ERROR')

    handlers = []
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    file_handler.setFormatter(formatter)
    handlers.append(file_handler)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.INFO)
    if hasattr(stream_handler, 'stream'):
        # don't add if built without console-support
        handlers.append(stream_handler)

    for handler in handlers:
        logger.addHandler(handler)

    sys.stdout = StreamLogger(logger, logging._nameToLevel[STD_OUT_LOG_LEVEL])
    sys.stderr = StreamLogger(logger, logging._nameToLevel[STD_ERR_LOG_LEVEL])

    for handler in handlers:
        logging.getLogger(f'desktopwidgets.{DesktopWidgetsCore.__name__.upper()}').\
            log(level=logging.INFO, msg=f'enabled stream_handler {handler}. has stream: {hasattr(handler, "stream")} '
                                        f'({handler.stream if hasattr(handler, "stream") else ""})')

    logging.getLogger('qrainbowstyle').setLevel(logging.FATAL)
    # logging.getLogger('googleapiclient.discovery').setLevel(logging.ERROR)
    # logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)

    import faulthandler
    logging.getLogger(f'desktopwidgets.{DesktopWidgetsCore.__name__.upper()}').\
        log(level=logging.INFO, msg='enabling fault-handler')
    faulthandler.enable(open('crash.log', 'a'), all_threads=True)

    core = DesktopWidgetsCore(available_widgets=[
        MusicWidget,
        CalendarWidget,
        NetworkWidget,
        # 'ClockWidget',
    ]
                         )

    core.spin()
