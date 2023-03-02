import datetime
import logging
import math
from datetime import date, timedelta
from typing import Union

from PyQt5.QtCore import pyqtSignal, Qt, QRect
from PyQt5.QtGui import QPaintEvent, QPainter, QFont, QPen, QColor
from PyQt5.QtWidgets import QWidget, QHBoxLayout

from plugins.calendarplugin.calendar_plugin import Event, EventInstance
from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.calendar.timeline_widget import TimelineWidget
from helpers.widget_helpers import CalendarHelper


class AllDayWidget(TimelineWidget):
    event_date_change_request = pyqtSignal(CalendarEventWidget, date, date)

    def __init__(self):
        super().__init__()
        self._upper_margin = 25
        self._lower_margin = 5

        self.days = None
        self.start_date = None
        self.bg_widgets = []
        self.setMaximumHeight(self._upper_margin+self._lower_margin + 25)  # todo: better formula
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, self._upper_margin, 0, self._lower_margin)
        self.layout.setSpacing(1)
        self.setLayout(self.layout)
        self._h = self._upper_margin+self._lower_margin + 25

    def refresh(self, days, start_date):
        self.start_date = start_date
        self.days = days
        for wid in self.bg_widgets:
            self.layout.removeWidget(wid)
            wid.deleteLater()
        self.bg_widgets.clear()
        for d in range(0, self.days):
            # day = datetime.datetime.now().date() + datetime.timedelta(days=d)
            wid = QWidget()
            self.bg_widgets.append(wid)
            self.layout.addWidget(wid)

    def unscaled_rect(self, _ev):
        return QRect(self.bg_widgets[_ev.begin].geometry().x(), self._upper_margin,
                     self.bg_widgets[_ev.end - 1].geometry().x() +
                     self.bg_widgets[_ev.end - 1].geometry().width() -
                     self.bg_widgets[_ev.begin].geometry().x(),
                     self.height() - (self._upper_margin+self._lower_margin))

    def rescale_height(self, n_cols):
        self._h = max(self._h, n_cols*25)
        if self.maximumHeight() != (self._upper_margin+self._lower_margin + self._h):
            self.setMaximumHeight(self._upper_margin+self._lower_margin + self._h)
        return self.width(), self._h

    def resizeEvent(self, event):
        event_widgets = self.collect_event_widgets()
        if self.bg_widgets:
            for ev in event_widgets:
                try:
                    end_idx = max(0, ev.end - 1)
                    ev.setGeometry(self.bg_widgets[ev.begin].geometry().x(), self._upper_margin,
                                   self.bg_widgets[end_idx].geometry().x() +
                                   self.bg_widgets[end_idx].geometry().width() -
                                   self.bg_widgets[ev.begin].geometry().x(),
                                   self.height() - (self._upper_margin+self._lower_margin))
                except RuntimeError as e:
                    self.log(e, level=logging.INFO)
                    pass
            CalendarHelper.scale_events([c for c in event_widgets if c.isVisible()],
                                        self.width(), self.height() - (self._upper_margin+self._lower_margin),
                                        0, 24, Qt.Horizontal,
                                        rect_func=self.unscaled_rect, col_rescale_func=self.rescale_height)

    def delete_event_callback(self):
        super().delete_event_callback()
        self._h = 25
        CalendarHelper.scale_events([c for c in self.collect_event_widgets() if c.isVisible()], self.width(),
                                    self.height() - (self._upper_margin+self._lower_margin), 0, 24, Qt.Horizontal,
                                    rect_func=self.unscaled_rect, col_rescale_func=self.rescale_height)

    def add_event(self, event: Union[Event, EventInstance], begin, end):
        self._h = 25
        super().add_event(event, begin, end)
        if isinstance(event, EventInstance):
            if event.root_event.id in self.cal_events and isinstance(self.cal_events[event.root_event.id], dict):
                self.cal_events[event.root_event.id][event.instance_id].date_change_request.connect(self.rescale_event_callback)
        else:
            self.cal_events[event.id].date_change_request.connect(self.rescale_event_callback)

    def rescale_event_callback(self, new_start_date, new_end_date):
        self.event_date_change_request.emit(self.sender(), new_start_date, new_end_date)

    def _event_got_moved(self, event: CalendarEventWidget, new_pos):
        new_pos.setY(event.y())
        new_pos.setX(min(max(new_pos.x(), 0), self.width()-5))
        event.move(new_pos)

    def _event_got_moved_end(self, event: CalendarEventWidget, new_pos):
        new_start = math.floor((new_pos.x()/self.width()) * self.days)
        day_offset = new_start-event.begin
        self.event_date_change_request.emit(event,
                                            event.event.start + timedelta(days=day_offset),
                                            event.event.end + timedelta(days=day_offset)
                                            )

    def paintEvent(self, event: QPaintEvent) -> None:
        if self.days is None:
            return
        painter = QPainter(self)
        for d in range(0, self.days):
            painter.setFont(QFont('Calibri',
                                  min(self.bg_widgets[d].width() / 8, 16)
                                  )
                            )
            day = (self.start_date + timedelta(days=d))
            if day == datetime.date.today():
                painter.setPen(QPen(QColor(250, 170, 0)))
            elif day.weekday() == 6:  # SUNDAY
                painter.setPen(QPen(QColor(255, 0, 0)))
            elif day.weekday() == 5:  # SATURDAY
                painter.setPen(QPen(QColor(255, 100, 100)))
            else:
                painter.setPen(QPen(QColor(255, 255, 255)))
            painter.drawText(QRect(
                self.bg_widgets[d].geometry().x(),
                0,  # TODO:REMOVE MAGIC NUMBER
                self.bg_widgets[d].geometry().width(),
                min(self.bg_widgets[d].geometry().height(), 20)), Qt.AlignCenter, day.strftime('%a, %d.%m.'))  # TODO:REMOVE MAGIC NUMBER