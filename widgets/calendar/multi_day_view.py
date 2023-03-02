import logging
from datetime import datetime, date, timedelta, time as d_time
import math
from collections import OrderedDict
from typing import Union, List, Dict

from PyQt5.QtCore import Qt, QRect, pyqtSignal, QPoint
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QBrush
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QApplication

from helpers.tools import time_method
from plugins.calendarplugin.calendar_plugin import Event, EventInstance
from plugins.weather.weather_data_types import Temperature, Precipitation, SunTime
from plugins.weather.weather_plugin import WeatherReport
from widgets.calendar.all_day_widget import AllDayWidget
from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.calendar.daily_weather_widget import DailyWeatherWidget
from widgets.calendar.day_widget import DayWidget
from widgets.tool_widgets.widget import Widget
from helpers.viz_helper import PrecipitationVisualization, TemperatureVisualization


class MultiDayView(Widget):
    event_edit_request = pyqtSignal(CalendarEventWidget)
    event_delete_request = pyqtSignal(CalendarEventWidget)
    event_rescale_request = pyqtSignal(CalendarEventWidget, datetime, datetime)
    event_date_change_request = pyqtSignal(CalendarEventWidget, date, date)

    def __init__(self):
        super(MultiDayView, self).__init__()
        self.days = None
        self.start_date = None
        self.layout = QVBoxLayout()
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(40, 15, 15, 15)
        self.start_hour = 0
        self.end_hour = 24
        self.all_day_view = AllDayWidget()
        self.all_day_view.event_removed.connect(self.remove_event)  # propagate to all day-widgets for multi-day-events
        self.all_day_view.event_edit_request.connect(self.event_edit_request)
        self.all_day_view.event_delete_request.connect(self.event_delete_request)
        self.all_day_view.event_date_change_request.connect(self.event_date_change_request)
        self.day_layout = QHBoxLayout()
        self.day_layout.setSpacing(1)
        self.day_layout.setContentsMargins(0, 0, 0, 0, )

        self.daily_weather_widget = DailyWeatherWidget()

        self.layout.addWidget(self.daily_weather_widget)
        self.layout.addWidget(self.all_day_view)
        self.layout.addLayout(self.day_layout)
        self.setLayout(self.layout)
        self.day_widgets: List[DayWidget] = []
        self.weather_data = None

    def hours_displayed(self):
        return self.end_hour - self.start_hour

    def change_hours(self, start_hour, end_hour):
        self.start_hour = start_hour
        self.end_hour = end_hour
        for dw in self.day_widgets:
            dw.change_hours(start_hour, end_hour)
        self.repaint()

    def refresh(self, days, start_date, start_hour, end_hour):
        self.days = days
        self.daily_weather_widget.refresh(days, start_date)
        self.all_day_view.refresh(days, start_date)
        for dw in self.day_widgets:
            dw.event_edit_request.disconnect(self.event_edit_request)
            dw.event_delete_request.disconnect(self.event_delete_request)
            dw.event_time_change_request.disconnect(self.event_rescale_request)
            self.day_layout.removeWidget(dw)
            dw.deleteLater()
        self.day_widgets.clear()
        self.start_date = start_date
        self.start_hour = start_hour
        self.end_hour = end_hour
        for d in range(0, self.days):
            dw = DayWidget(self.start_date + timedelta(days=d), self.start_hour, self.end_hour)
            dw.event_removed.connect(self.remove_event)  # propagate to all day-widgets for multi-day-events
            dw.event_edit_request.connect(self.event_edit_request)
            dw.event_delete_request.connect(self.event_delete_request)
            dw.event_time_change_request.connect(self.event_rescale_request)
            self.day_widgets.append(dw)
            self.day_layout.addWidget(dw)
        QApplication.processEvents()

    def set_filter(self, calendar_filter: List[str]):
        self.all_day_view.set_filter(calendar_filter)
        for dw in self.day_widgets:
            dw.set_filter(calendar_filter)

    def set_weather(self, weather_data):
        self.weather_data = weather_data
        self.daily_weather_widget.set_weather(weather_data)
        self.update(self.rect())

    def add_event(self, event: Union[Event, EventInstance]):
        today = self.start_date
        event_instance = event if isinstance(event, Event) else event.instance

        if today + timedelta(days=self.days) >= event_instance.start.date() \
                and today <= event_instance.end.date():

            # self.debug('tyring: %r' % event['summary'])
            event_days = (event_instance.end.date() - event_instance.start.date()).days + 1
            date_offset = (event_instance.start.date() - today).days

            if event_instance.all_day:
                event_days -= 1
                begin = -1
                end = -1

                print(f'{event_instance.title}: {event_instance.start.date()}-{event_instance.end.date()} -> eds:{event_days}, begin:{begin}, end:{end}')
                for day in range(0, event_days):
                    column = date_offset + day
                    if 0 <= column < self.days:
                        if begin < 0:
                            begin = column  # self.day_widgets[column].geometry().x()
                            end = column  # begin + self.day_widgets[column].geometry().width()
                        else:
                            end = column  # self.day_widgets[column].geometry().x() + \
                            # self.day_widgets[column].geometry().width()

                print(f'{event_instance.title}: {event_instance.start.date()}-{event_instance.end.date()} -> eds:{event_days}, begin:{begin}, end:{end}')
                if begin >= 0:
                    self.all_day_view.add_event(event, begin, end + 1)

            else:
                for day in range(0, event_days):
                    column = date_offset + day
                    if 0 <= column < self.days:
                        # self.debug('painting day %r of %r (col: %r)' % (day, event['summary'], column))
                        if day > 0:
                            start_hour = 0  # self.start_hour??
                        else:
                            start_hour = event_instance.start.hour + (event_instance.start.minute / 60)  # real
                        if day == event_days - 1:
                            end_hour = event_instance.end.hour + (event_instance.end.minute / 60)  # real
                        else:
                            end_hour = 24  # self.end_hour??
                        self.day_widgets[column].add_event(event, start_hour, end_hour)

    def add_events(self, events: Dict[str, Union[Event, List[EventInstance]]]):
        for event_id, event in events.items():
            if isinstance(event, list):
                for ev in event:
                    self.add_event(ev)

            elif isinstance(event, Event):
                self.add_event(event)
            else:
                ...

    def remove_event(self, event_id: str, new_event: Union[Event, List[EventInstance], None] = None):
        found = 0
        for dw in self.day_widgets:
            found += 1 if dw.remove_event(event_id) else 0
        found += 1 if self.all_day_view.remove_event(event_id) else 0
        if found == 0:
            self.log_error(f'REMOVING EVENT {event_id} FAILED!!!')
        else:
            self.log_info(f'removed {found} widgets belonging to {event_id}')
        if new_event is not None:
            if isinstance(new_event, list):
                self.add_events({new_event[0].root_event.id: new_event})
            else:
                self.add_events({new_event.id: new_event})

    def remove_all(self):
        for dw in self.day_widgets:
            dw.remove_all()
        self.all_day_view.remove_all()

    def show_events(self):
        self.all_day_view.set_events_visible(True)
        for dw in self.day_widgets:
            dw.set_events_visible(True)

    def hide_events(self):
        self.all_day_view.set_events_visible(False)
        for dw in self.day_widgets:
            dw.set_events_visible(False)

    def map_to_time(self, p1: QPoint, p2: QPoint):
        wid_1 = None
        wid_2 = None
        for dw in self.day_widgets:
            pos_1 = dw.mapFromGlobal(p1)
            pos_2 = dw.mapFromGlobal(p2)
            if 0 < pos_1.x() < dw.width() and 0 < pos_1.y() < dw.height():
                wid_1 = dw
            if 0 < pos_2.x() < dw.width() and 0 < pos_2.y() < dw.height():
                wid_2 = dw

        if wid_1 is not None and wid_2 is not None:
            if wid_1 == wid_2:
                start_w = end_w = wid_1
                if p1.y() > p2.y():
                    start = wid_1.mapFromGlobal(p2)
                    end = wid_1.mapFromGlobal(p1)
                else:
                    start = wid_1.mapFromGlobal(p1)
                    end = wid_1.mapFromGlobal(p2)
            else:
                if p1.x() > p2.x():
                    start_w = wid_2
                    end_w = wid_1
                    start = wid_2.mapFromGlobal(p2)
                    end = wid_1.mapFromGlobal(p1)
                else:
                    start_w = wid_1
                    end_w = wid_2
                    start = wid_1.mapFromGlobal(p1)
                    end = wid_2.mapFromGlobal(p2)

            def get_date_time(y, widget):
                hr = round((self.hours_displayed() * y / widget.height()) * 4.0, 0) / 4
                hour = int(math.floor(hr))
                minute = int(round((hr - hour) * 60))
                day = widget.day
                hour += + self.start_hour
                if hour > 23:
                    hour = 0
                    minute = 0
                    day = widget.day + timedelta(days=1)
                return datetime.combine(day, d_time(hour=hour, minute=minute))
            start_time = get_date_time(start.y(), start_w)
            end_time = get_date_time(end.y(), end_w)
            return start_time, end_time
        return None

    def paintEvent(self, _paint_event):
        if not self.day_widgets:
            return
        # TODO: FIND A BETTER WAY TO FIX THE REPAINT BUG!!!
        if self.day_widgets[0].geometry().x() == 0:
            self.parent().update()
            return

        painter = QPainter(self)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 50)))
        # draw grid
        for d_idx, day_wid in enumerate(self.day_widgets):
            if day_wid.day == datetime.now().date():
                painter.fillRect(day_wid.geometry(), QColor(20, 90, 50, 150))
            for h_idx, wid in enumerate(day_wid.widgets):
                x = wid.x() + day_wid.x()
                y = wid.y() + day_wid.y()
                w = wid.width()
                h = wid.height()
                if h_idx == 0:
                    painter.drawLine(x, y, x + w, y)  # top
                if d_idx == 0:
                    painter.drawLine(x, y, x, y + h)  # left
                painter.drawLine(x, y + h, x + w, y + h)  # bottom
                painter.drawLine(x + w, y, x + w, y + h)  # right
        # draw grid for all-day-events
        for d_idx, all_day_wid in enumerate(self.all_day_view.bg_widgets):
            x = all_day_wid.x() + self.all_day_view.x()
            y = all_day_wid.y() + self.all_day_view.y()
            w = all_day_wid.width()
            h = all_day_wid.height()
            if d_idx == 0:
                painter.drawLine(x, y, x, y + h)  # left
            painter.drawLine(x, y, x + w, y)  # top
            painter.drawLine(x, y + h, x + w, y + h)  # bottom
            painter.drawLine(x + w, y, x + w, y + h)  # right

        # super(MultiDayView, self).paintEvent(_paint_event)
        # draw times
        pen = QPen(QColor(255, 255, 255))
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setFont(QFont('Calibri', 8))
        for t in range(self.start_hour, self.end_hour+1):
            painter.drawText(QRect(
                self.day_widgets[0].geometry().x() - 30,  # TODO:REMOVE MAGIC NUMBER
                self.day_widgets[0].geometry().y() - 7 +
                (t-self.start_hour) * (self.day_widgets[0].geometry().height() / self.hours_displayed()),
                30,  # TODO:REMOVE MAGIC NUMBER
                self.day_widgets[0].geometry().height() / self.hours_displayed()), Qt.TextWordWrap, '%02d:00' % t)

        # draw weather
        if self.weather_data:
            self.paint_weather(painter, self.weather_data)

        # draw now-line
        now = datetime.now()
        start = now.replace(hour=self.start_hour, minute=0, second=0)
        end = now.replace(hour=23, minute=59, second=59) if self.end_hour == 24 else \
            now.replace(hour=self.end_hour, minute=0, second=0)
        if start <= now <= end:
            hour = now.hour + (now.minute / 60) - self.start_hour
            _circle_w = 6
            _x = self.day_widgets[0].geometry().x() - _circle_w
            _y = self.day_widgets[0].geometry().y() + hour * \
                 (self.day_widgets[0].geometry().height() / self.hours_displayed())
            _w = self.day_widgets[0].geometry().width() + _circle_w
            pen = QPen(QColor(255, 0, 0))
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawLine(_x, _y, _x + _w, _y)
            painter.setBrush(QColor(255, 0, 0))
            painter.setRenderHint(QPainter.Antialiasing)
            painter.drawEllipse(QRect(_x, _y - _circle_w / 2, _circle_w, _circle_w))

    def paint_weather(self, painter: QPainter, weather_report: WeatherReport):
        visualizations = OrderedDict([
            (Precipitation, PrecipitationVisualization(self.start_hour, self.end_hour)),
            (Temperature, TemperatureVisualization(self.start_hour, self.end_hour)),
        ])

        painter.setRenderHint(QPainter.Antialiasing)

        from plugins.weather.weather_data_types import  PrecipitationType
        mylist = [p[1].data[Precipitation].get_type()['value'] for p in weather_report.get_merged_report().items() if
                  p[1].data[Precipitation].get_type()['value'] != PrecipitationType.FREEZING_RAIN]

        def get_y(_time: datetime):

            _hour = _time.hour + (_time.minute / 60) - self.start_hour
            start_y = _hour * (self.day_widgets[0].geometry().height() / self.hours_displayed())
            start_y = min(max(0, start_y), self.day_widgets[0].geometry().height())
            return self.day_widgets[0].geometry().y() + start_y

        # visualize sunrise/sunset
        for time, single_report in weather_report.get_daily_report().items():
            offset = (time.date() - self.start_date).days
            if offset < 0:
                continue
            if offset < len(self.day_widgets):
                try:
                    sun_time = single_report.data[SunTime]
                    sunset = sun_time.get_sunset()['value']
                    sunrise = sun_time.get_sunrise()['value']
                    if sunset is None or sunrise is None:
                        pass
                    else:
                        painter.setPen(Qt.NoPen)
                        painter.setBrush(QBrush(QColor(215, 230, 0, 50)))
                        y1 = get_y(sunrise)
                        y2 = get_y(sunset)
                        x = self.day_widgets[offset].x()
                        w = self.day_widgets[offset].width()
                        painter.drawRect(x, y1, w, y2-y1)
                except KeyError:
                    logging.getLogger(self.__class__.__name__).log(level=logging.ERROR,
                                                                   msg=f'oh-oh {single_report.data.keys()}')

        offset = 0
        for time, single_report in weather_report.get_merged_report().items():
            if max(self.start_hour - 1, 0) <= time.hour <= min(self.end_hour + 1, 24):
                new_offset = (time.date() - self.start_date).days
                if new_offset < 0:
                    continue
                if new_offset < len(self.day_widgets):
                    if new_offset != offset:  # complete old path and create new one
                        offset = new_offset
                        for weather_data_type, viz in visualizations.items():
                            viz.complete_path(painter, self.day_widgets[offset-1].geometry())
                    y = get_y(time)
                    for weather_data_type, viz in visualizations.items():
                        if weather_data_type in single_report.data:
                            viz.add_data_point(single_report.data[weather_data_type], self.day_widgets[offset].geometry(), y)
                        else:
                            self.log_warn(f'{weather_data_type} not found in {single_report.data}')
        # draw last day
        for weather_data_type, viz in visualizations.items():
            viz.complete_path(painter, self.day_widgets[offset].geometry())


