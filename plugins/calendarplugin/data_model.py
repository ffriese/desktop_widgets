from datetime import datetime, date
from enum import Enum
from typing import Union, List, Dict, Any

import dateutil.rrule
from PyQt5.QtGui import QColor
from dateutil.tz import tzlocal


class CalendarAccessRole(Enum):
    OWNER = 'OWNER'
    READER = 'READER'
    WRITER = 'WRITER'
    FREE_BUSY_READER = 'FREE_BUSY_READER'


class Alarm:
    def __init__(self, alarm_time: datetime, trigger: str, description: str, action: str):
        self.trigger = trigger
        self.alarm_time = alarm_time
        self.description = description
        self.action = action


class Calendar:
    def __init__(self, calendar_id: str, name: str, access_role: CalendarAccessRole,
                 fg_color: QColor,
                 bg_color: QColor,
                 data: dict,
                 primary: bool = False):
        self.id = calendar_id
        self.name = name
        self.access_role = access_role
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.bg_color.setAlpha(200)
        self.data = data
        self.primary = primary

    def __repr__(self):
        return f"Calendar({self.__dict__})"


class Event:
    def __init__(self,
                 event_id: Union[str, None],
                 title: str,
                 start: Union[datetime, date],
                 end: Union[datetime, date],
                 location: str,
                 description: str,
                 all_day: bool,
                 calendar: Calendar,
                 data: dict,
                 timezone: str = None,
                 fg_color: QColor = None,
                 bg_color: QColor = None,
                 recurring_event_id: str = None,
                 recurrence: dateutil.rrule.rrule = None,
                 exdates: List[datetime] = None,
                 synchronized: bool = True,
                 alarm: Alarm = None,
                 subcomponents: Dict[str, "Event"] = None,
                 instances: List["EventInstance"] = None
                 ):
        self.id = event_id
        self.title = title
        self.description = description
        self.location = location
        self.data = data
        self.calendar = calendar
        self.all_day = all_day
        self.start = start
        self.end = end
        self.timezone = timezone
        self.recurring_event_id = recurring_event_id
        self.recurrence = recurrence
        self.exdates = exdates
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.alarm = alarm
        self.subcomponents = subcomponents if subcomponents else {}
        self.instances = instances
        self._synchronized = synchronized

    def get_fg_color(self):
        if self.fg_color is not None:
            return self.fg_color
        else:
            return self.calendar.fg_color

    def get_bg_color(self):
        if self.bg_color is not None:
            return self.bg_color
        else:
            return self.calendar.bg_color

    def is_recurring(self):
        return self.recurring_event_id is not None

    def is_synchronized(self):
        return self._synchronized

    def mark_desynchronized(self):
        self.data['synchronized'] = False
        self._synchronized = False

    def get_unique_id(self):
        return f'{self.id}#{self.start.strftime("%Y%m%dT%H%M%SZ")}'

    def set_start_time(self, start_time: datetime):
        self.start = start_time.astimezone(tzlocal())

    def set_end_time(self, end_time: datetime):
        self.end = end_time.astimezone(tzlocal())


class EventInstance:
    def __init__(self, root_event: Event, instance: Event):
        self.root_event = root_event
        self.instance = instance
        self.instance_id = instance.recurring_event_id


class Todo:
    def __init__(self,
                 todo_id: Union[str, None],
                 title: str,
                 data: dict,
                 start: Union[datetime, date],
                 due: Union[datetime, date],
                 **kwargs):
        self.id = todo_id
        self.title = title
        self.start = start
        self.due = due
        self.data = data
        for k, v in kwargs.items():
            setattr(self, k, v)


class CalendarData:
    def __init__(self, calendars: Dict[str, Calendar], events: Dict[str, Union[Event, List[EventInstance]]],
                 colors: Dict[Any, Dict[str, QColor]],
                 todos: Dict[str, Todo] = None, account_name: str = None):
        self.account_name = account_name
        self.calendars = calendars
        self.events = events
        self.todos = todos if todos else []
        self.colors = colors

    def get_calendars(self):
        return self.calendars

    def get_events(self):
        return self.events


class CalendarSyncException(Exception):
    pass