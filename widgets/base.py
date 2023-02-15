import importlib
import logging
import sys
from inspect import signature
from threading import Lock
from typing import Type, Union

from PyQt5.QtGui import *
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5 import QtCore
from termcolor import colored

from credentials import NoCredentialsSetException, CredentialsNotValidException, CredentialType
from helpers import styles
from helpers.tools import PathManager
from helpers.settings_storage import SettingsStorage
from plugins.base import BasePlugin, APIDeprecatedException, APILimitExceededException
from helpers.widget_helpers import ResizeHelper


class BaseWidget(QWidget, object):
    widget_updated = pyqtSignal(str, QVariant)
    widget_geometry_changed = pyqtSignal(QRect)
    widget_closed = pyqtSignal()
    widget_reload_request = pyqtSignal()
    widget_debug = pyqtSignal(str, int)

    def __init__(self, parent=None, width=300, height=300):
        super().__init__(parent, Qt.Tool)
        self._user_triggered_move_event: Union[QPoint, None] = None
        self._user_triggered_resize_event: Union[QRect, None] = None
        self.setWindowFlag(QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        self.background_color = QColor(0, 0, 0, 190)
        self.border_color = QColor(255, 255, 255, 50)
        self.border_margin = 7
        # self.background_widget = BlurredBackground(self)
        widget_name = self.__class__.__name__.replace('Widget', ' Widget')
        self.plugins = []

        self.settings_switcher = {
            'fg_font': (setattr, ['self', 'key', 'value'], QFont),
            'background_color': (setattr, ['self', 'key', 'value'], QColor),
            'border_margin': (setattr, ['self', 'key', 'value'], int),
            'border_color': (setattr, ['self', 'key', 'value'], QColor),
            'hidden': (self.hide_or_show, ['value'], lambda val: val in ['true', 'True']),
            'origin': (self.move, ['value'], QPoint),
            'size': (self.resize, ['value'], QSize)
        }

        self._pending_settings_timer = QTimer()
        self._pending_settings_timer.setSingleShot(True)
        self._pending_settings_timer.setInterval(1000)
        self._pending_settings_timer.timeout.connect(self._update_pending_settings)
        self._pending_settings_lock = Lock()
        self._pending_settings_updates = {}

        self._pending_geometry_timer = QTimer()
        self._pending_geometry_timer.setSingleShot(True)
        self._pending_geometry_timer.setInterval(1000)
        self._pending_geometry_timer.timeout.connect(self._update_pending_geometry)
        self._pending_geometry_lock = Lock()
        self._pending_geometry = None

        self.__alt_left_mouse_down_loc__ = None
        self.__original_loc__ = None
        self.__alt_right_mouse_down_loc__ = None
        self.__original_geometry__ = None
        self.__resize_section__ = None

        self.toString = {
            QFont: lambda font: ', '.join(font.toString().split(',')[:2]),
            QColor: lambda col: col.name(),
            QTimer: lambda t: 'every %.2f seconds ' % (float(t.interval()) / 1000.0)
        }

        self.show_action = QAction(QIcon(PathManager.get_icon_path('hide_widget.png')),
                                   'Show ' + widget_name, self)
        self.hide_action = QAction(QIcon(PathManager.get_icon_path('hide_widget.png')),
                                   'Hide ' + widget_name, self)
        self.reload_action = QAction(QIcon(PathManager.get_icon_path('reload_widget.png')),
                                     'Reload ' + widget_name, self)
        self.close_action = QAction(QIcon(PathManager.get_icon_path('close_widget.png')),
                                    'Close ' + widget_name, self)
        self.color_pick_action = QAction(QIcon(PathManager.get_icon_path('pantone.png')),
                                         'Change Background Color', self)
        self.font_pick_action = QAction(QIcon(PathManager.get_icon_path('font.png')),
                                        'Change Font')
        self.color_picker = QColorDialog(self)
        self.color_picker.setStyleSheet(styles.get_style('darkblue'))
        self.color_picker.setOption(QColorDialog.ShowAlphaChannel)

        self.font_picker = QFontDialog(self)
        self.font_picker.setStyleSheet(styles.get_style('darkblue'))
        self.fg_font = self.font()
        self.tmp_font = self.font()

        self.reload_action.triggered.connect(self.request_reload)
        self.show_action.triggered.connect(self.show)
        self.hide_action.triggered.connect(self.hide)
        self.close_action.triggered.connect(self.close)
        self.color_pick_action.triggered.connect(self.pick_bg_color)
        self.font_pick_action.triggered.connect(self.pick_font)

        self.resize(width, height)

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.context_menu = QMenu('context menu')
        self.context_menu.setStyleSheet(styles.get_style('darkblue'))
        # self.context_menu.setStyleSheet('QMenu{ background-color: rgb(255,255, 255); color: rgb(0,0,0); '
        #                                 '       icon-size: 20px;} '
        #                                 'QMenu::item{ background: transparent;} '
        #                                 'QMenu::item:selected { background-color: rgb(196,233,251);}')
        self.context_menu.addAction(self.color_pick_action)
        self.context_menu.addAction(self.font_pick_action)
        self.context_menu.addSeparator()

        self.timer = QTimer()
        self.timer.setInterval(1000)

        self.__data__ = {}

    def start(self):
        self.color_picker.setCurrentColor(self.background_color)
        self._load_data()

    @pyqtSlot(str, QVariant)
    def apply_settings(self, key, value):
        #  self.debug('set %s:%r' % (key, value))
        try:
            settings_function, used_params, value_type = self.settings_switcher[key]
            potential_params = {'self': self, 'key': key,
                                'value': value_type(value) if value_type is not None else value}
            args = [potential_params[param] for param in used_params]
            # self.debug('key: %s, f: %r, args: %r' % (key, settings_function, args))
            settings_function(*args)
            if key not in [
                'hidden', 'notes_background_color', 'collapsed_items',
                'background_color', 'notes_text', 'project_filter', 'api_token', 'player',
                'lyrics_provider', 'events', 'calendars', 'weather_data'
            ]:
                try:
                    val = self.toString[type(value)](value)
                except:
                    val = value
                self.log('successfully set %s : %r' % (key, val))
        except KeyError:
            self.log('no function implemented for %s!!' % key)
        except Exception as e:
            self.log('could not set %s:%r (%s)' % (key, value, str(e)))

    def _load_data(self):
        self.__data__ = SettingsStorage.load_or_default(self.__class__.__name__, {})
        self.log_info('loaded', self.__data__)
        for key, value in self.__data__.items():
            setattr(self, key, value)

    def _save_data(self):
        SettingsStorage.save(self.__data__, self.__class__.__name__)
        self.log_info('saved', self.__data__)

    def hide_or_show(self, hide):
        if hide:
            self.hide()
        else:
            self.show()

    def _received_new_data(self, data: object):
        # noinspection PyTypeChecker
        self.received_new_data(self.sender(), data)

    def received_new_data(self, plugin: BasePlugin, data: object):
        raise NotImplementedError(f'{self.__class__.__name__} must implement this method!')

    def _question_mbox(self, title, msg):
        return QMessageBox.question(self, title, msg, QMessageBox.Yes | QMessageBox.No)

    def _received_plugin_exception(self, exception: Exception):
        self.log('sender:', self.sender())
        # noinspection PyTypeChecker
        plugin = self.sender()  # type: BasePlugin
        try:
            self.log_info('exec ', exception)
            raise exception
        except NoCredentialsSetException as ncse:
            self.log_info('caught NoCredentialsSetException')
            if ncse.credential_type == CredentialType.SSL_VERIFY:
                # Do not ask for 'credentials', directly go to SSL-VERIFY check
                reply = QMessageBox.Yes
            else:
                reply = self._question_mbox(title='Missing Credentials!',
                                            msg=f'Your {plugin.__class__.__name__} is requesting credentials. '
                                                f'Would you like to set them?')
            if reply == QMessageBox.Yes:
                if not ncse.enter_credentials(self, plugin):
                    plugin.new_data_available.emit(None)
            else:
                plugin.new_data_available.emit(None)
        except CredentialsNotValidException as cnve:
            reply = self._question_mbox(title='Invalid Credentials!',
                                        msg=f'Your {plugin.__class__.__name__} reported invalid credentials. '
                                            f'Would you like to set them again?')
            if reply == QMessageBox.Yes:
                if not cnve.reenter_credentials(self, plugin):
                    plugin.new_data_available.emit(None)
            else:
                plugin.new_data_available.emit(None)
        except APIDeprecatedException as ade:
            QMessageBox.warning(self, 'API Deprecated',
                                f'{self.__class__.__name__} uses a deprecated API '
                                f'in {plugin.__class__.__name__}.\n\n'
                                f'{ade}.\n\n'
                                )
            plugin.new_data_available.emit(None)
        except APILimitExceededException as arle:
            QMessageBox.warning(self, 'API Rate-Limit exceeded',
                                f'{self.__class__.__name__} exceeded API-Rate-Limit '
                                f'in {plugin.__class__.__name__}.\n\n'
                                f'{arle}.\n\n'
                                )
            plugin.new_data_available.emit(None)
        # except SSLNoVerifyException as sslnve:
        #     ...
        except Exception as e:
            self.received_plugin_exception(plugin, e)

    def received_plugin_exception(self, plugin: BasePlugin, exception: Exception):
        fnc = self.received_plugin_exception
        QMessageBox.critical(self, 'UNHANDLED EXCEPTION!',
                             f'{self.__class__.__name__} encountered an unhandled Exception '
                             f'in {plugin.__class__.__name__}.\n\n'
                             f'{type(exception)}: {exception}.\n\n'
                             f'{self.__class__.__name__} '
                             f'must implement \n\ndef {fnc.__name__}{signature(fnc)}\n\n'
                             f'to catch this.\n\n'
                             f'The program will now exit.'
                             )
        raise NotImplementedError(f'{self.__class__.__name__} must implement this method!')

    def register_plugin(self, plugin_class: Type[BasePlugin], attr):
        plugin_class = getattr(importlib.import_module(plugin_class.__module__), plugin_class.__name__)
        plugin = plugin_class()  # type: BasePlugin
        plugin.plugin_log.connect(self.widget_debug)
        plugin.new_data_available.connect(self._received_new_data)
        plugin.threaded_exception.connect(self._received_plugin_exception)
        setattr(self, attr, plugin)
        self.plugins.append(plugin)
        self.log('registered %s as \'%s\'' % (plugin.__class__.__name__, attr))
        plugin.setup()

    def deregister_plugin(self, plugin, attr):
        plugin.plugin_log.disconnect(self.widget_debug)
        plugin.new_data_available.disconnect(self._received_new_data)
        plugin.threaded_exception.disconnect(self._received_plugin_exception)
        plugin.quit()
        self.plugins.remove(plugin)
        delattr(self, attr)
        self.log('removed %s as \'%s\'' % (plugin.__class__.__name__, attr))

    @pyqtSlot(QPoint)
    def show_context_menu(self, pos):
        if not QGuiApplication.keyboardModifiers() & Qt.AltModifier == Qt.AltModifier:
            self.context_menu.exec(self.mapToGlobal(pos))

    @pyqtSlot()
    def pick_bg_color(self):
        def close_handler():
            self.color_picker.finished.disconnect()
            self.color_picker.colorSelected.disconnect()

        def color_handler(new_bg):
            # new_bg.setAlpha(190)
            self.background_color = new_bg
            self.widget_updated.emit('background_color', self.background_color)
            self.repaint()

        self.color_picker.finished.connect(close_handler)
        self.color_picker.colorSelected.connect(color_handler)
        self.color_picker.show()

    @pyqtSlot()
    def pick_font(self):
        def close_handler():
            self.font_picker.finished.disconnect()
            if self.tmp_font != self.fg_font:
                self.fg_font = self.tmp_font
                self.font_changed()
            # self.fonts.fontSelected.disconnect()

        def font_handler(new_font):
            self.fg_font = new_font
            self.tmp_font = self.fg_font
            self.widget_updated.emit('fg_font', self.fg_font)
            self.font_changed()

        try:
            self.font_picker.fontSelected.disconnect()
        except:
            pass

        self.tmp_font = self.fg_font
        self.font_picker.setCurrentFont(self.fg_font)
        self.font_picker.finished.connect(close_handler)
        self.font_picker.fontSelected.connect(font_handler)
        self.font_picker.show()

    @pyqtSlot()
    def request_reload(self):
        if self.timer.isActive():
            self.timer.stop()
            self.timer.disconnect()
        for plugin in self.plugins:
            plugin.quit()
            self.log(' >> reloading %s ...' % plugin.__class__.__name__)
            importlib.reload(sys.modules[plugin.__module__])
        self.widget_reload_request.emit()

    def font_changed(self):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(self.border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.background_color)
        margin = self.border_margin
        painter.drawRect(margin, margin, self.width() - (margin * 2), self.height() - (margin * 2))

    def hide(self):
        super(BaseWidget, self).hide()
        self.hide_action.setVisible(False)
        self.show_action.setVisible(True)
        self.widget_updated.emit('hidden', True)

    def show(self):
        super(BaseWidget, self).show()
        self.hide_action.setVisible(True)
        self.show_action.setVisible(False)
        self.widget_updated.emit('hidden', False)

    def close(self):
        super(BaseWidget, self).close()
        for plugin in self.plugins:
            plugin.quit()
        self.widget_closed.emit()

    def get_top_level_widget(self, widget):
        if widget.parent() is not None:
            return self.get_top_level_widget(widget.parent())
        return widget

    def eventFilter(self, obj: 'QObject', event: 'QEvent') -> bool:
        if self != self.get_top_level_widget(obj):
            return False
        if isinstance(event, QMouseEvent):
            if not self.geometry().contains(event.globalPos()) and \
                    self.__alt_left_mouse_down_loc__ is None and \
                    self.__alt_right_mouse_down_loc__ is None:
                return False
            # noinspection PyTypeChecker
            if QGuiApplication.keyboardModifiers() & Qt.AltModifier == Qt.AltModifier:
                if event.type() == QEvent.MouseButtonPress:
                    if event.button() == Qt.LeftButton:
                        self.__alt_left_mouse_down_loc__ = event.globalPos()
                        self.__original_loc__ = self.pos()
                    else:
                        self.__alt_right_mouse_down_loc__ = event.globalPos()
                        self.__original_geometry__ = self.geometry()
                        self.__resize_section__ = ResizeHelper.get_resize_section(self.__original_geometry__,
                                                                                  self.__alt_right_mouse_down_loc__)
                        self.setCursor(
                            Qt.SizeBDiagCursor if self.__resize_section__ in [Qt.BottomLeftSection, Qt.TopRightSection]
                            else Qt.SizeFDiagCursor)
                elif event.type() == QEvent.MouseButtonRelease:
                    self.__alt_left_mouse_down_loc__ = None
                    self.__original_loc__ = None
                    self.__alt_right_mouse_down_loc__ = None
                    self.__original_geometry__ = None
                    self.__resize_section__ = None
                    self.setCursor(Qt.ArrowCursor)
                elif event.type() == QEvent.MouseMove:
                    if self.__alt_left_mouse_down_loc__ is not None:
                        new_pos = self.__original_loc__ + (event.globalPos() - self.__alt_left_mouse_down_loc__)
                        self._user_triggered_move_event = new_pos
                        self.move(new_pos)
                    elif self.__alt_right_mouse_down_loc__ is not None:
                        section = self.__resize_section__
                        diff = (event.globalPos() - self.__alt_right_mouse_down_loc__)
                        new_height = self.__original_geometry__.height()
                        new_width = self.__original_geometry__.width()
                        new_x = self.__original_geometry__.x()
                        new_y = self.__original_geometry__.y()
                        if section == Qt.TopLeftSection:
                            new_height -= diff.y()
                            new_width -= diff.x()
                            new_x += diff.x() + (new_width - max(new_width, self.minimumWidth()))
                            new_y += diff.y() + (new_height - max(new_height, self.minimumHeight()))
                        elif section == Qt.TopRightSection:
                            new_height -= diff.y()
                            new_width += diff.x()
                            new_y += diff.y() + (new_height - max(new_height, self.minimumHeight()))
                        elif section == Qt.BottomLeftSection:
                            new_height += diff.y()
                            new_width -= diff.x()
                            new_x += diff.x() + (new_width - max(new_width, self.minimumWidth()))
                        elif section == Qt.BottomRightSection:
                            new_height += diff.y()
                            new_width += diff.x()
                        # todo: can sometimes crash after screen disconnects
                        self._user_triggered_resize_event = QRect(new_x, new_y, new_width, new_height)
                        self.setGeometry(new_x, new_y, new_width, new_height)
                        self.customResizeEvent(QSize(new_width,  new_height))
                return True
            else:
                self.__alt_left_mouse_down_loc__ = None
                self.__original_loc__ = None
                self.__alt_right_mouse_down_loc__ = None
                self.__original_geometry__ = None
                self.__resize_section__ = None
                self.setCursor(Qt.ArrowCursor)
        elif isinstance(event, QKeyEvent) and event.type() == QEvent.KeyRelease and event.key() == Qt.Key_Alt:
            self.__alt_left_mouse_down_loc__ = None
            self.__original_loc__ = None
            self.__alt_right_mouse_down_loc__ = None
            self.__original_geometry__ = None
            self.__resize_section__ = None
            self.setCursor(Qt.ArrowCursor)

        return super().eventFilter(obj, event)

    def moveEvent(self, event):
        if self._user_triggered_move_event is not None \
                and self._user_triggered_move_event == event.pos():
            # self.schedule_settings_update('origin', event.pos())
            self.schedule_move(event.pos())
            self._user_triggered_move_event = None
        elif self._user_triggered_resize_event is None:
            self.log_debug('RECEIVED NON-USER-TRIGGERED MOVE-EVENT!!! to', event.pos())

    def customResizeEvent(self, size: QSize):
        # self.log_info('CUSTOM RESIZED', size)
        if self._user_triggered_resize_event is not None \
                and self._user_triggered_resize_event.size() == size:
            # self.schedule_settings_update('size', event.size())
            self.schedule_resize(size)
            self._user_triggered_resize_event = None
        else:
            self.log_info('?????????????????????RECEIVED CUSTOM NON-USER-TRIGGERED RESIZE-EVENT!!! to', size)

    def resizeEvent(self, event):
        if self._user_triggered_resize_event is not None \
                and self._user_triggered_resize_event.size() == event.size:
            # self.schedule_settings_update('size', event.size())
            self.schedule_resize(event.size())
            self._user_triggered_resize_event = None

    def schedule_move(self, pos: QPoint):
        with self._pending_geometry_lock:
            if self._pending_geometry is None:
                self._pending_geometry = self.geometry()
            self._pending_geometry.moveTo(pos)
            if self._pending_geometry_timer.isActive():
                self._pending_geometry_timer.stop()
            self._pending_geometry_timer.start()

    def schedule_resize(self, size: QSize):
        with self._pending_geometry_lock:
            if self._pending_geometry is None:
                self._pending_geometry = self.geometry()
            self._pending_geometry.setSize(size)
            if self._pending_geometry_timer.isActive():
                self._pending_geometry_timer.stop()
            self._pending_geometry_timer.start()

    def _update_pending_geometry(self):
        with self._pending_geometry_lock:
            self.widget_geometry_changed.emit(self._pending_geometry)

    def schedule_settings_update(self, key: str, value: object):
        with self._pending_settings_lock:
            self._pending_settings_updates[key] = value
            if self._pending_settings_timer.isActive():
                self._pending_settings_timer.stop()
            self._pending_settings_timer.start()

    def _update_pending_settings(self):
        with self._pending_settings_lock:
            for key in list(self._pending_settings_updates.keys()):
                value = self._pending_settings_updates.pop(key)
                self.widget_updated.emit(key, value)

    def log(self, debug_msg, *args, level=logging.DEBUG):
        if type(debug_msg) is not str:
            debug_msg = str(debug_msg)
        if args:
            debug_msg = f"{debug_msg} {' '.join([str(a) for a in args])}"
        if level >= logging.ERROR:
            debug_msg = colored(debug_msg, 'red')
        self.widget_debug.emit(debug_msg, level)

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


class BlurredBackground(QWidget):
    def __init__(self, parent=None):
        super(BlurredBackground, self).__init__(parent)
        blur = QGraphicsBlurEffect()
        blur.setBlurRadius(5)
        self.setGraphicsEffect(blur)

        self.main_widget = parent
        self.bg = QImage()
        self.margin = self.main_widget.border_margin
        self.timer = QTimer()
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.retake_screen)
        self.timer.start()

    def retake_screen(self):
        origin = self.mapToGlobal(QPoint(0, 0))
        logging.getLogger(self.__class__.__name__).log(logging.DEBUG,
                                                       f'{self.main_widget.__class__.__name__}, {origin.x()}, {origin.y()}'
                                                       f'{QGuiApplication.screens()[0].size()},'
                                                       f'{QGuiApplication.screens()[1].size()}')

        if origin.x() > QGuiApplication.screens()[0].size().width():
            screen = QGuiApplication.screens()[0]
        else:
            screen = QGuiApplication.screens()[1]
        self.main_widget.hide()
        shot = screen.grabWindow(0,
                                 origin.x() + self.margin,
                                 origin.y() + self.margin,
                                 self.width() - self.margin * 2,
                                 self.height() - self.margin * 2)

        self.bg = QImage(shot)
        self.main_widget.show()

        self.timer.setInterval(10000)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(self.main_widget.border_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.main_widget.background_color)
        painter.drawImage(self.margin, self.margin, self.bg)
