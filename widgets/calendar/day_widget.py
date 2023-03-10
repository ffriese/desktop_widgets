from datetime import datetime, timedelta

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QApplication

from plugins.calendarplugin.calendar_plugin import Event, EventInstance
from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.calendar.timeline_widget import TimelineWidget
from helpers.widget_helpers import CalendarHelper


class DayWidget(TimelineWidget):
    event_time_change_request = pyqtSignal(CalendarEventWidget, datetime, datetime)

    def __init__(self, day: datetime.date, start_hour: int, end_hour: int):
        super(DayWidget, self).__init__()
        self.day = day
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.widgets = []
        self.layout = QVBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(1)

        for h in range(self.start_hour, self.end_hour):
            wid = QWidget()
            # if self.day.weekday() > 4:  # weekend
            #    wid.setStyleSheet('background-color: rgba(20,00,20,190)')
            # else:
            #    wid.setStyleSheet('background-color: rgba(0,0,0,190)')
            self.layout.addWidget(wid)
            self.widgets.append(wid)
        self.setLayout(self.layout)

    def hours_displayed(self):
        return self.end_hour - self.start_hour

    def hour_height(self):
        return self.height() / self.hours_displayed()

    def change_hours(self, start_hour, end_hour):
        self.start_hour = start_hour
        self.end_hour = end_hour
        while self.hours_displayed() > len(self.widgets):
            wid = QWidget()
            self.layout.addWidget(wid)
            self.widgets.append(wid)
        while self.hours_displayed() < len(self.widgets):
            wid = self.widgets.pop(0)
            self.layout.removeWidget(wid)
            wid.deleteLater()

        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def move_event_widget_to_position(self, event_widget: CalendarEventWidget):
        try:
            if event_widget.end < self.start_hour or event_widget.begin > self.end_hour:
                event_widget.setVisible(False)
                event_widget.setProperty('hiddenFromRange', True)
            else:
                if event_widget.property('hiddenFromRange'):
                    event_widget.setVisible(True)
                start_y = int(max(0, event_widget.begin - self.start_hour) * self.hour_height())
                height = min(int((event_widget.end - max(event_widget.begin, self.start_hour)) * self.hour_height()),
                             self.height() - start_y)
                event_widget.setGeometry(0,
                                         start_y,
                                         self.width(),
                                         height
                                         )
        except RuntimeError:
            pass

    def resizeEvent(self, resizeEvent):
        event_widgets = self.collect_event_widgets()
        for ev in event_widgets:
            self.move_event_widget_to_position(ev)

        CalendarHelper.scale_events([c for c in event_widgets if c.isVisible()], self.width(), self.height(),
                                    self.start_hour, self.end_hour)

    def add_event(self, event: Event, begin, end):
        super().add_event(event, begin, end)
        if isinstance(event, EventInstance):
            if event.root_event.id in self.cal_events and isinstance(self.cal_events[event.root_event.id], dict):
                self.cal_events[event.root_event.id][event.instance_id].time_change_request.connect(
                    self.rescale_event_callback)
        else:
            self.cal_events[event.id].time_change_request.connect(self.rescale_event_callback)

    def rescale_event_callback(self, new_start, new_end):
        self.event_time_change_request.emit(self.sender(), new_start, new_end)

    def _event_got_moved(self, event_widget: CalendarEventWidget, new_pos):

        new_pos.setX(event_widget.x())
        new_pos.setY(min(max(new_pos.y(), 0), self.height() - 5))
        event_widget.move(new_pos)

    def _event_got_moved_end(self, event_widget: CalendarEventWidget, new_pos):
        new_start = ((new_pos.y() / self.height()) * self.hours_displayed()) + self.start_hour
        hour_offset = new_start - event_widget.begin
        hour_offset = event_widget.round_time(hour_offset, round_min=5.0)
        self.event_time_change_request.emit(event_widget,
                                            event_widget.event_instance().start + timedelta(hours=hour_offset),
                                            event_widget.event_instance().end + timedelta(hours=hour_offset))
