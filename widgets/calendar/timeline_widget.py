from datetime import datetime
from typing import List, Dict, Union

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QResizeEvent
from PyQt5.QtWidgets import QApplication

from plugins.calendarplugin.calendar_plugin import Event, EventInstance
from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.tool_widgets.widget import Widget


class TimelineWidget(Widget):
    event_removed = pyqtSignal(str, object)  # id, Event
    event_edit_request = pyqtSignal(CalendarEventWidget)
    event_delete_request = pyqtSignal(CalendarEventWidget)

    def __init__(self):
        super(TimelineWidget, self).__init__()
        self.cal_events = dict()  # type: Dict[str, Union[CalendarEventWidget, Dict[str, CalendarEventWidget]]]
        self.layout = None
        self.calendar_filter = []
        self.visible = True

    def set_filter(self, calender_filter: List[str]):
        self.calendar_filter = calender_filter
        if self.visible:
            for widget in self.collect_event_widgets():
                widget.setVisible(widget.event_instance().calendar.name not in self.calendar_filter)
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def add_event(self, event: Union[Event, EventInstance], begin, end):
        cal_event = CalendarEventWidget(parent=self, event=event, begin=begin, end=end)
        cal_event.delete_signal.connect(self.event_removed)
        cal_event.edit_request_signal.connect(self.edit_event_callback)
        cal_event.delete_request_signal.connect(self.delete_event_callback)
        if isinstance(event, EventInstance):
            cal_event.setVisible(event.instance.calendar.name not in self.calendar_filter)
            if event.root_event.id in self.cal_events and isinstance(self.cal_events[event.root_event.id], dict):
                self.cal_events[event.root_event.id][event.instance_id] = cal_event
            else:
                self.cal_events[event.root_event.id] = {event.instance_id: cal_event}
        else:
            cal_event.setVisible(event.calendar.name not in self.calendar_filter)
            self.cal_events[event.id] = cal_event
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def edit_event_callback(self):
        self.event_edit_request.emit(self.sender())

    def delete_event_callback(self):
        self.event_delete_request.emit(self.sender())

    def remove_event(self, event_id):
        self.log('trying to delete event', event_id)
        found = 0
        if event_id in self.cal_events:
            if isinstance(self.cal_events[event_id], dict):
                for rec_id in list(self.cal_events[event_id].keys()):
                    widget = self.cal_events[event_id].pop(rec_id)

                    self.log(f'found {widget.event_instance().title}')
                    found += 1
                    widget.deleteLater()
                self.cal_events.pop(event_id)
            else:
                widget = self.cal_events.pop(event_id)
                self.log(f'found {widget.event_instance().title}')
                found += 1
                widget.deleteLater()

            QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))
            self.log('removed', event_id)
        return found

    def collect_event_widgets(self):
        return [v for k, v in self.cal_events.items() if not isinstance(v, dict)] + \
               [v for d in self.cal_events.values() if isinstance(d, dict) for v in d.values()]

    def remove_all(self):
        for i in list(self.cal_events.keys()):
            if isinstance(self.cal_events[i], dict):
                for ei in list(self.cal_events[i].keys()):
                    self.cal_events[i].pop(ei).deleteLater()
                self.cal_events.pop(i)
            else:
                self.cal_events.pop(i).deleteLater()

    def set_events_visible(self, visible):
        self.visible = visible
        for widget in self.collect_event_widgets():
            widget.setVisible(visible and widget.event_instance().calendar.name not in self.calendar_filter)

    def _event_got_moved(self, event, new_pos):
        # print(self, event, new_pos)

        new_pos.setX(event.x())
        new_pos.setY(min(max(new_pos.y(), 0), self.height()-5))
        event.move(new_pos)

    def _event_got_moved_end(self, event: CalendarEventWidget, new_pos):
        pass

