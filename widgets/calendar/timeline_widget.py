from datetime import datetime
from typing import List, Dict

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QWidget, QApplication

from plugins.calendarplugin.calendar_plugin import Event
from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.tool_widgets.widget import Widget


class TimelineWidget(Widget):
    event_removed = pyqtSignal(str, object)  # id, Event
    event_edit_request = pyqtSignal(CalendarEventWidget)
    event_delete_request = pyqtSignal(CalendarEventWidget)

    def __init__(self):
        super(TimelineWidget, self).__init__()
        self.cal_events = dict()  # type: Dict[str, CalendarEventWidget]
        self.layout = None
        self.calendar_filter = []
        self.visible = True

    def set_filter(self, calender_filter: List[str]):
        self.calendar_filter = calender_filter
        if self.visible:
            for widget in self.cal_events.values():
                widget.setVisible(widget.event.calendar.name not in self.calendar_filter)
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def add_event(self, event: Event, begin, end):
        cal_event = CalendarEventWidget(parent=self, event=event, begin=begin, end=end)
        cal_event.delete_signal.connect(self.event_removed)
        cal_event.edit_request_signal.connect(self.edit_event_callback)
        cal_event.delete_request_signal.connect(self.delete_event_callback)
        cal_event.setVisible(event.calendar.name not in self.calendar_filter)
        self.cal_events[event.id] = cal_event
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def edit_event_callback(self):
        self.event_edit_request.emit(self.sender())

    def delete_event_callback(self):
        self.event_delete_request.emit(self.sender())

    def remove_event(self, event_id):
        self.log('trying to delete event', event_id)
        try:
            ev = self.cal_events.pop(event_id, None)
            if ev is not None:
                self.log(f'found ev {ev}')
                title = ev.event.title
                ev.deleteLater()
                QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))
                self.log('removed', event_id, title)
                return 1
        except Exception as e:
            self.log(e)
            self.log_error(e)
        return 0

    def remove_all(self):
        for i in list(self.cal_events.keys()):
            self.cal_events.pop(i).deleteLater()

    def set_events_visible(self, visible):
        self.visible = visible
        for widget in self.cal_events.values():
            widget.setVisible(visible and widget.event.calendar.name not in self.calendar_filter)

    def _event_got_moved(self, event, new_pos):
        # print(self, event, new_pos)

        new_pos.setX(event.x())
        new_pos.setY(min(max(new_pos.y(), 0), self.height()-5))
        event.move(new_pos)

    def _event_got_moved_end(self, event: CalendarEventWidget, new_pos):
        pass

