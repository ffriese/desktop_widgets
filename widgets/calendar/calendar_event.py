import logging
import math
import re
import webbrowser
from datetime import datetime, date, timedelta
from typing import Union

from PyQt5.QtCore import pyqtSignal, Qt, QRect
from PyQt5.QtGui import QIcon, QPainter, QPen, QFont, QResizeEvent
from PyQt5.QtWidgets import QWidget, QMenu, QAction, QGraphicsDropShadowEffect, QLabel, QVBoxLayout

from helpers.rrule_helper import get_recurrence_text
from helpers.tools import ImageTools, PathManager, SignalingThread
from plugins.calendarplugin.calendar_plugin import Event, CalendarAccessRole, EventInstance
from plugins.weather.iconsets import IconSet
from plugins.weather.weather_data_types import Temperature, WeatherDescription, Wind
from plugins.weather.weather_plugin import WeatherReport
from helpers.widget_helpers import SideGrip
from widgets.tool_widgets import EmojiPicker
from widgets.tool_widgets.widget import Widget


class CalendarEventWidget(Widget):
    delete_signal = pyqtSignal(str, object)  # id, updated Event

    edit_request_signal = pyqtSignal()
    delete_request_signal = pyqtSignal()

    time_change_request = pyqtSignal(datetime, datetime)
    date_change_request = pyqtSignal(date, date)

    __ICONS__ = {}
    __MAP_IMAGES__ = {}

    @classmethod
    def get_icon_base_64(cls, path: str, size: int, fallback: str = '') -> str:
        if path in CalendarEventWidget.__ICONS__.keys():
            if size in CalendarEventWidget.__ICONS__[path].keys():
                return CalendarEventWidget.__ICONS__[path][size]
        else:
            CalendarEventWidget.__ICONS__[path] = {}
        try:
            CalendarEventWidget.__ICONS__[path][size] = ImageTools.pixmap_to_base64(
                    QIcon(path).pixmap(size, size))
            return CalendarEventWidget.__ICONS__[path][size]
        except ValueError:
            return fallback

    @classmethod
    def get_map_image_base_64(cls, location_string):
        # return ""
        if location_string in cls.__MAP_IMAGES__:
            return cls.__MAP_IMAGES__[location_string]

        ## move to own class
        import requests

        from credentials import MapQuestCredentials
        response = requests.get(f"https://www.mapquestapi.com/staticmap/v5/map?key"
                      f"={MapQuestCredentials.get_api_key()}&center={location_string}&size=250,250&zoom=10&locations={location_string}", stream=True)
        if response.status_code == 200:

            import base64

            uri = ("data:" +
                   response.headers['Content-Type'] + ";" +
                   "base64," + base64.b64encode(response.content).decode("utf-8"))

            cls.__MAP_IMAGES__[location_string] = f"<img src='{uri}'>"

        else:
            cls.__MAP_IMAGES__[location_string] = ""

        return cls.__MAP_IMAGES__[location_string]

    def __init__(self, parent, event: Union[Event, EventInstance], begin, end):
        super(CalendarEventWidget, self).__init__(parent=parent)
        self.__mousePressPos = None
        self.__mouseMovePos = None
        self.shadow = QGraphicsDropShadowEffect()
        self.shadow.setBlurRadius(5)
        self.shadow.setXOffset(-3)
        self.shadow.setYOffset(3)
        self.setGraphicsEffect(self.shadow)
        self.begin = begin
        self.end = end
        self.setMinimumHeight(5)
        self.event = event
        self.tooltip_data = ''
        self.tooltip_thread = SignalingThread(target=self.create_tool_tip)
        self.tooltip_thread.finished.connect(self.update_tooltip_data)
        self.tooltip_thread.setDaemon(True)
        self.tooltip_widget = QWidget(self)
        self.tooltip_widget.setStyleSheet('background-color: red')
        self.tooltip_widget.hide()
        self.tooltip_widget_label = QLabel('')
        self.tooltip_widget_label.setWordWrap(True)
        self.tooltip_widget.setLayout(QVBoxLayout())
        self.tooltip_widget.layout().setContentsMargins(0, 0, 0, 0)
        self.tooltip_widget.layout().addWidget(self.tooltip_widget_label)

        self.setWindowFlag(Qt.SubWindow)
        if self.root_event().calendar.access_role == CalendarAccessRole.OWNER:
            if not self.event_instance().all_day:
                self.top_grip = SideGrip(self, Qt.TopEdge)
                self.bottom_grip = SideGrip(self, Qt.BottomEdge)
                self.top_grip.resized.connect(lambda r: self.request_dragged_time_update(r, Qt.TopEdge))
                self.bottom_grip.resized.connect(lambda r: self.request_dragged_time_update(r, Qt.BottomEdge))
                self.top_grip.resizing.connect(self.show_time_tooltip)
                self.bottom_grip.resizing.connect(self.show_time_tooltip)
                self.top_grip.resizing_end.connect(self.tooltip_widget.hide)
                self.bottom_grip.resizing_end.connect(self.tooltip_widget.hide)
            else:
                self.left_grip = SideGrip(self, Qt.LeftEdge)
                self.right_grip = SideGrip(self, Qt.RightEdge)
                self.left_grip.resized.connect(lambda r: self.request_dragged_time_update(r, Qt.LeftEdge))
                self.right_grip.resized.connect(lambda r: self.request_dragged_time_update(r, Qt.RightEdge))
                self.left_grip.resizing.connect(lambda r: self.show_time_tooltip(r, Qt.Horizontal))
                self.right_grip.resizing.connect(lambda r: self.show_time_tooltip(r, Qt.Horizontal))
                self.left_grip.resizing_end.connect(self.tooltip_widget.hide)
                self.right_grip.resizing_end.connect(self.tooltip_widget.hide)

        if not self.event_instance().all_day:
            if not self.event_instance().start.date() != self.event_instance().end.date() :
                start_time_format = '%a %d.%m. %H:%M'
                end_time_format = '%H:%M'
            else:
                start_time_format = '%a %d.%m. %H:%M'
                end_time_format = '%a %d.%m. %H:%M'

            self.time = f"{self.event_instance().start.strftime(start_time_format)} - " \
                        f"{self.event_instance().end.strftime(end_time_format)}"
        else:
            if self.event_instance().start.date() == self.event_instance().end.date() or \
                    (self.event_instance().end - timedelta(days=1)).date() == self.event_instance().start.date():
                start_time_format = '%a %d.%m.'
                self.time = f"{self.event_instance().start.strftime(start_time_format)}"
            else:
                start_time_format = '%a %d.%m.'
                end_time_format = '%a %d.%m.'
                self.time = f"{self.event_instance().start.strftime(start_time_format)} - " \
                            f"{(self.event_instance().end - timedelta(days=1)).strftime(end_time_format)}"

        try:
            icon, summary = EmojiPicker.split_summary(self.event_instance().title)
            self.summary = summary
            if icon:
                self.icon = EmojiPicker.get_emoji_icon_from_unicode(icon, 32)
            else:
                self.icon = None
        except KeyError:
            self.summary = None
            self.icon = None
            logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg=self.event_instance())
        except IndexError:
            icon, summary = EmojiPicker.split_summary(self.event_instance().title)
            self.summary = summary
            self.icon = None

        try:
            self.location = self.event_instance().location
        except KeyError:
            self.location = None
        try:
            self.description = self.event_instance().description.replace('\n', '<br>').replace(' ', '&nbsp;')
            self.urls = re.findall(r"(?P<url>https?://[^\s]+)", self.event_instance().description)
        except KeyError:
            self.description = None
        self.tooltip_thread.start()
        self.show()
        self.setStyleSheet('QToolTip {background-color: rgb(30, 30, 30); '
                           'color: white; '
                           'border: 1.5px solid gray;'
                           'padding: 5px;border-radius: 2px;}')

        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        self.context_menu = QMenu('context menu')
        # self.context_menu.setStyleSheet('background-color: rgb(50,50,50)')

        self.context_menu.setStyleSheet('QMenu{ background-color: rgb(255,255, 255); color: rgb(0,0,0); '
                                        '       icon-size: 20px;} '
                                        'QMenu::item{ background: transparent;} '
                                        'QMenu::item:selected { background-color: rgb(196,233,251);}')
        self.edit_action = QAction(QIcon(PathManager.get_icon_path('edit_event.png')),
                                   'Edit event', self)

        self.context_menu.addAction(self.edit_action)
        if self.event_instance().calendar.access_role != CalendarAccessRole.OWNER:
            self.edit_action.setDisabled(True)
            self.edit_action.setText('Edit (read-only)')
            self.edit_action.setIcon(QIcon(PathManager.get_icon_path('lock_event.png')))
        else:

            self.edit_action.triggered.connect(self.edit_event)

            if self.event_instance().is_recurring():
                rec_id = self.event_instance().recurring_event_id
                # self.edit_action.setText('Edit recurring event')
                self.recurring = True
                # cal_plugin.get_rec_event(self.event)
                if self.root_event().exdates:
                    self.restore_exdates_menu = QMenu('Restore removed instances', self)
                    self.exdate_restore_actions = {}
                    for exdate in self.root_event().exdates:
                        self.exdate_restore_actions[exdate] = QAction(f'Restore {exdate}', self)
                        self.restore_exdates_menu.addAction(self.exdate_restore_actions[exdate])
                    self.context_menu.addMenu(self.restore_exdates_menu)

            else:
                self.recurring = False
            self.delete_action = QAction(QIcon(PathManager.get_icon_path('delete_event.png')),
                                         'Delete event', self)
            self.delete_action.triggered.connect(self.delete_event)
            self.context_menu.addAction(self.delete_action)
        self.url_actions = []
        for url in self.urls:
            url_action = QAction(QIcon(PathManager.get_icon_path('link.png')),
                                 f'Go to {url}', self)
            url_action.triggered.connect(lambda: webbrowser.open(url))
            self.url_actions.append(url_action)
            self.context_menu.addAction(url_action)

    def update_tooltip_data(self):
        self.setToolTip(self.tooltip_data)

    def root_event(self) -> Event:
        if isinstance(self.event, Event):
            return self.event
        elif isinstance(self.event, EventInstance):
            return self.event.root_event

    def event_instance(self) -> Event:
        if isinstance(self.event, Event):
            return self.event
        elif isinstance(self.event, EventInstance):
            return self.event.instance

    def create_tool_tip(self):
        if self.icon is not None:
            img = ImageTools.pixmap_to_base64(self.icon.pixmap(28, 28))
        else:
            img = ''
        time_str = f"<tr><td>{self.get_icon_base_64(PathManager.get_icon_path('time.png'), 10, '<b>Time:</b>')} " \
                   f"</td><td>{self.time}</td></tr>" if self.time else ''
        loc_str = f"<tr><td>{self.get_icon_base_64(PathManager.get_icon_path('location.png'), 10, '<b>Location:</b>')} " \
                  f"</td><td>{self.location}</td></tr>  <tr><td></td><td>" \
                  f"{self.get_map_image_base_64(self.location)}</td></tr>" if self.location else ''
        desc_str = f"<tr><td>{self.get_icon_base_64(PathManager.get_icon_path('description.png'), 10, '<b>Description:</b>')} " \
                   f"</td><td>{self.description}</td></tr>" if self.description else ''
        alarm_str = f"<tr><td>{self.get_icon_base_64(PathManager.get_icon_path('bell.png'), 10, '<b>Alarm:</b>')} " \
                    f"</td><td>{self.event_instance().alarm.alarm_time.strftime('%H:%M')}</td></tr>" if self.event_instance().alarm else ''
        recurrence = f"<tr><td>{self.get_icon_base_64(PathManager.get_icon_path('recurring.png'), 10, '<b>Recurrence:</b>')} " \
                     f"</td><td>{get_recurrence_text(self.root_event().recurrence)}</td></tr>" if self.root_event().recurrence else ''
        weather = ''

        try:
            if hasattr(self.parent().parent(), 'weather_data') and self.parent().parent().weather_data:
                weather_data: WeatherReport = self.parent().parent().weather_data
                report = weather_data.get_report_from(self.event_instance().start, self.event_instance().end)
                if report:
                    temps = [dp.data.get(Temperature).get_temperature()['value'] for dp in report.values()]
                    min_t = round(min(temps))
                    max_t = round(max(temps))
                    temp = f"{min_t}-{max_t}" if min_t != max_t else str(min_t)

                    gusts = [dp.data.get(Wind).get_gust()['value'] * 3.6 for dp in report.values()]
                    winds = [dp.data.get(Wind).get_speed()['value'] * 3.6 for dp in report.values()]
                    wind = f"{round(min(winds))}-{round(max(winds))} km/h (Gusts: {round(max(gusts))} km/h)"
                    wind_icon = self.get_icon_base_64(PathManager.get_icon_path('wind.png'), 20)

                    data_point = list(report.values())[0].data

                    t_icon = self.get_icon_base_64(PathManager.get_icon_path('temperature_4.png'), 20)
                    code = data_point.get(WeatherDescription).get_code()['value']
                    icon_set = IconSet.WEATHER_UNDERGOUND
                    c_icon = self.get_icon_base_64(
                        PathManager.get_weather_icon_set_path(icon_set['folder'], f"{icon_set['data'][code]}.svg"), 20)

                    weather = f"<tr></tr><tr><td>{c_icon}</td><td>{code.name.replace('_', ' ').title()}</td></tr>" \
                              f"<tr><td>{t_icon}</td><td>{temp}°C</td></tr> " \
                              f"<tr><td>{wind_icon}</td><td>{wind}</td></tr> "
        except RuntimeError as e:
            print('RTE', e)
        self.tooltip_data = f'<h2>{img}<b> {self.summary}</b></h2>' \
                        f'<hr/>' \
                        f'<table>' \
                        f'{time_str}' \
                        f'{loc_str}' \
                        f'{desc_str}' \
                        f'{recurrence}' \
                        f'{alarm_str}' \
                        f'{weather}' \
                        f'<tr></tr></table>' \
                        f"{self.get_icon_base_64(PathManager.get_icon_path('cal.png'), 10, '<i>Calendar:</i>')}" \
                        f" <i>{self.event_instance().calendar.name}</i>" \

    def show_context_menu(self, pos):
        self.context_menu.exec(self.mapToGlobal(pos))

    def edit_event(self):
        self.edit_request_signal.emit()

    def delete_event(self):
        self.delete_request_signal.emit()

    def __repr__(self):
        if not hasattr(self, 'summary'):
            return str(self.__dict__)
        return f'{self.summary}  {self.begin} {self.end}'

    @staticmethod
    def round_time(hours, round_min=5.0):
        minutes = float(hours * 60.0)
        tmp = minutes / float(round_min)
        tmp2 = round(tmp)
        tmp = float(tmp2) * float(round_min)
        return tmp / 60.0

    def rect_to_times(self, rect: QRect, start_hour=0, end_hour=24):
        hours_displayed = end_hour - start_hour
        percentage_start = float(rect.y()) / float(self.parent().height())
        start_hours = self.round_time(percentage_start * hours_displayed, 5.0) + start_hour
        s_h = math.floor(start_hours)
        s_m = round((start_hours - s_h) * 60.0)

        percentage_end = float(rect.y() + rect.height()) / float(self.parent().height())
        end_hours = self.round_time(percentage_end * hours_displayed, 5.0) + start_hour
        e_h = math.floor(end_hours)
        e_m = round((end_hours - e_h) * 60.0)
        return s_h, s_m, e_h, e_m

    def rect_to_days(self, rect: QRect):
        percentage_start = float(rect.x()) / float(self.parent().width())
        start_day = math.floor(percentage_start * self.parent().days)
        percentage_end = float(rect.x() + rect.width()) / float(self.parent().width())
        end_day = math.floor(percentage_end * self.parent().days)
        return start_day, end_day

    def request_dragged_time_update(self, rect: QRect, resized_from: Qt.Edge):
        self.tooltip_widget.hide()
        if resized_from in [Qt.TopEdge, Qt.BottomEdge]:
            start_hour = self.parent().start_hour
            end_hour = self.parent().end_hour
            s_h, s_m, e_h, e_m = self.rect_to_times(rect, start_hour, end_hour)
            # print(f'{s_h:02d}:{s_m:02d}', f'{e_h:02d}:{e_m:02d}')
            if resized_from == Qt.TopEdge:
                new_start = self.event_instance().start.replace(hour=s_h, minute=s_m)
                new_end = self.event_instance().end
            else:
                new_start = self.event_instance().start
                if e_h == 24:
                    new_end = (self.event_instance().end+timedelta(days=1)).replace(hour=0, minute=0)
                else:
                    new_end = self.event_instance().end.replace(hour=e_h, minute=e_m)

            self.time_change_request.emit(new_start, new_end)
        else:
            start_day, end_day = self.rect_to_days(rect)
            new_start = self.parent().start_date + timedelta(days=start_day)
            new_end = self.parent().start_date + timedelta(days=end_day)
            new_start = datetime.combine(new_start, datetime.min.time())
            new_end = datetime.combine(new_end, datetime.min.time())
            self.date_change_request.emit(new_start, new_end)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if hasattr(self, 'top_grip'):
            self.top_grip.move(0, 0)
            self.bottom_grip.setGeometry(
                  0, self.rect().top() + self.rect().height()-3,
                  self.rect().width(), 3)
        if hasattr(self, 'left_grip'):
            self.left_grip.move(0, 0)
            self.right_grip.setGeometry(
                  self.rect().left() + self.rect().width() -3, 0,
                  3, self.rect().height())

    def show_time_tooltip(self, rect: QRect, direction=Qt.Vertical):
        if direction == Qt.Vertical:
            start_hour = self.parent().start_hour
            end_hour = self.parent().end_hour
            s_h, s_m, e_h, e_m = self.rect_to_times(rect, start_hour, end_hour)
            self.tooltip_widget_label.setText(f'{s_h:02d}:{s_m:02d} - {e_h:02d}:{e_m:02d}')
        else:
            start_day, end_day = self.rect_to_days(rect)
            start_date = self.parent().start_date + timedelta(days=start_day)  # type: datetime.date
            end_date = self.parent().start_date + timedelta(days=end_day) # type: datetime.date
            if start_date == end_date:
                self.tooltip_widget_label.setText(f"{start_date.strftime('%d.%m.')}")
            else:
                self.tooltip_widget_label.setText(f"{start_date.strftime('%d.%m.')} - {end_date.strftime('%d.%m.')}")

        self.tooltip_widget.resize(self.width(), 20 * self.parent().width()/self.width())
        self.tooltip_widget.show()

    def mousePressEvent(self, event):
        if self.event_instance().calendar.access_role in [CalendarAccessRole.OWNER, CalendarAccessRole.WRITER]:
            self.__mousePressPos = None
            self.__mouseMovePos = None
            if event.button() == Qt.LeftButton:
                self.__mousePressPos = event.globalPos()
                self.__mouseMovePos = event.globalPos()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.event_instance().calendar.access_role in [CalendarAccessRole.OWNER, CalendarAccessRole.WRITER]:
            if event.buttons() == Qt.LeftButton:
                # adjust offset from clicked point to origin of widget
                currPos = self.mapToGlobal(self.pos())
                globalPos = event.globalPos()
                diff = globalPos - self.__mouseMovePos
                newPos = self.mapFromGlobal(currPos + diff)
                self.parent()._event_got_moved(self, newPos)

                self.__mouseMovePos = globalPos

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.event_instance().calendar.access_role in [CalendarAccessRole.OWNER, CalendarAccessRole.WRITER]:
            if self.__mousePressPos is not None:
                moved = event.globalPos() - self.__mousePressPos
                # if moved.manhattanLength() > 3:
                #     event.ignore()
                #     return
                self.parent()._event_got_moved_end(self, self.pos())
                return

        super().mouseReleaseEvent(event)

    def paintEvent(self, paint_event):
        painter = QPainter(self)
        painter.setBrush(self.event_instance().calendar.bg_color)
        painter.setPen(Qt.NoPen)
        # painter.pen().setJoinStyle(Qt.BevelJoin)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.drawRoundedRect(QRect(0, 0, self.width(), self.height()), 4.0, 4.0)
        if self.event_instance().bg_color is not None:
            painter.setBrush(self.event_instance().get_bg_color())
            painter.drawRoundedRect(QRect(2, 0, self.width()-2, self.height()), 4.0, 4.0)
        pen = QPen(self.event_instance().get_fg_color())
        stroke = 1
        pen.setWidth(stroke)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(self.event_instance().get_fg_color())
        painter.setFont(QFont('Calibri', 10))
        if self.icon is not None:
            self.icon.paint(painter, QRect(2, 2, 15, 15))
            painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.TextWordWrap, '      '+self.summary)
        else:
            painter.drawText(QRect(0, 0, self.width(), self.height()), Qt.TextWordWrap, self.summary)

        icon_size = 15
        icon_margin = 2
        alarm_icon_pos = self.width() - (icon_size + icon_margin), icon_margin
        rec_icon_pos = self.width() - (icon_size + icon_margin), self.height() - (icon_size + icon_margin)
        sync_icon_pos = rec_icon_pos

        if self.event_instance().alarm:
            alarm_icon = QIcon(PathManager.get_icon_path('bell.png'))
            alarm_icon.paint(painter, QRect(*alarm_icon_pos, icon_size, icon_size))

        if self.root_event().recurrence:
            rec_icon = QIcon(PathManager.get_icon_path('recurring.png'))
            rec_icon.paint(painter, QRect(*rec_icon_pos, icon_size, icon_size))

        if not self.event_instance().is_synchronized():
            if self.root_event().recurrence:  # if rec_icon also present, shift sync icon to the left
                sync_icon_pos[0] -= (icon_size + icon_margin)
            sync_icon = QIcon(PathManager.get_icon_path('cloud-sync-icon.png'))
            sync_icon.paint(painter, QRect(*sync_icon_pos, icon_size, icon_size))
