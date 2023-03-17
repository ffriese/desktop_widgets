import copy
from datetime import datetime, date
from enum import Enum
from typing import Union, List, Dict, Any

import dateutil.rrule
from PyQt5.QtGui import QColor
from dateutil.tz import tzlocal

from plugins.base import BasePlugin


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


class CalendarPlugin(BasePlugin):
    COLORS = {
            1: "#7986cb",  # Lavender
            2: "#33b679",  # Sage
            3: "#8e24aa",  # Grape
            4: "#e67c73",  # Flamingo
            5: "#f6c026",  # Banana
            6: "#f5511d",  # Tangerine
            7: "#039be5",  # Peacock
            8: "#616161",  # Graphite
            9: "#3f51b5",  # Blueberry
            10: "#0b8043",  # Basil
            11: "#d60000"  # Tomato
        }

    COLOR_DICT = {
        None: {},
        **{str(k): {'fg_color': QColor('#f1f1f1'), 'bg_color': QColor(v)} for k, v in COLORS.items()}
    }

    class CacheMode(Enum):
        FORCE_REFRESH = 1,
        REFRESH_LATER = 2,
        ALLOW_CACHE = 3

    def update_async(self, days_in_future: int = None, days_in_past: int = None,
                     cache_mode=CacheMode.FORCE_REFRESH, *args, **kwargs) -> None:
        if days_in_future is None:
            self.log_warn('days_in_future missing! should not happen unless after inserting credentials')
            days_in_future = 12
        if days_in_past is None:
            self.log_warn('days_in_past missing! should not happen unless after inserting credentials')
            days_in_past = 2
        self.log_info(self, 'async', cache_mode)
        super().update_async(cache_mode=cache_mode, days_in_future=days_in_future, days_in_past=days_in_past,
                             *args, **kwargs)

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             *args, **kwargs) -> Union[CalendarData, None]:
        raise NotImplementedError()

    def quit(self):
        raise NotImplementedError()

    def setup(self):
        raise NotImplementedError()

    def create_event(self, event: Event,
                     days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        raise NotImplementedError()

    def delete_event(self, event: Event) -> bool:
        raise NotImplementedError()

    def delete_event_instance(self, instance: EventInstance,
                              days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        raise NotImplementedError()

    def update_event(self, event: Event,
                     days_in_future: int, days_in_past: int,
                     moved_from_calendar: Union[Calendar, None] = None,
                     ) -> Union[Event, List[EventInstance]]:
        raise NotImplementedError()

    @classmethod
    def get_event_colors(cls) -> Dict[Any, Dict[str, QColor]]:
        return cls.COLOR_DICT


class CalendarOfflineCache:
    def __init__(self):
        self.deleted_events = []
        self.created_events = []
        self.updated_events = {}

    def add_offline_creation(self, event: Event):
        pass

    def add_offline_deletion(self, event: Event):
        pass

    def add_offline_update(self, event: Event):
        pass

    def unroll_offline_cache(self, events: List[Event]) -> List[Event]:
        new_events = list(events)
        for created in self.created_events:
            new_events.append(created)
        for updated_id in self.updated_events.keys():
            pass
        new_events = [e for e in new_events if e.id not in self.deleted_events]
        return new_events

    def _prepare_for_sync(self, event: Event, created_offline=False):
        new_event = copy.deepcopy(event)
        new_event.data.pop('synchronized')
        if created_offline:
            temp_id = new_event.data.pop('id')
            new_event.id = None
        return new_event

    def __repr__(self):
        return f"CalendarOfflineCache(new:{self.created_events}, update:{self.updated_events}, del:{self.deleted_events})"

    # @time_method
    # def try_to_apply_cache(self, plugin: CalendarPlugin):
    #     events_to_display = []
    #     events_to_remove = []
    #     try:
    #         plugin.log_info('got myself some data-cache:', self.__repr__())
    #         created = list(self.created_events)
    #         for new_event in created:
    #             plugin.log_info('new offline event: ', new_event.data)
    #             ne = copy.deepcopy(new_event)
    #             temp_id = ne.data.pop('id')
    #             ne.data.pop('synchronized')
    #             ne.id = None
    #             synced = plugin.create_event(ne,
    #                                          days_in_future=12,
    #                                          days_in_past=1
    #                                          )
    #             if synced.is_synchronized():
    #                 self.created_events.remove(new_event)
    #                 plugin.log_info('successfully created ', new_event.data)
    #                 # self.display_new_event(synced)
    #                 events_to_display.append(synced)
    #                 if temp_id in self.updated_events.keys():
    #
    #                     plugin.log_info(f"moving {temp_id} to {synced.id}")
    #                     newly_synced = self.updated_events.pop('temp_id')
    #                     self.updated_events[synced.id] = newly_synced
    #                 else:
    #                     plugin.log_info(f"{temp_id} not found in update cache")
    #             else:
    #                 plugin.log_info('could not create. kept in cache', new_event)
    #                 # self.display_new_event(new_event)
    #                 events_to_display.append(new_event)
    #
    #         for update_id in list(self.updated_events.keys()):
    #             if update_id.startswith("non-sync"):
    #                 if update_id in self.created_events:
    #                     plugin.log_warn(f'updates for {update_id} are ignored as the main event is not synced')
    #                     continue
    #                 else:
    #                     plugin.log_error(
    #                         f"{update_id} is an unknown un-synced event. this should not have happened. removing...")
    #                     self.updated_events.pop(update_id)
    #                     continue
    #             updated = self.updated_events[update_id]
    #             last_change = updated[-1]
    #             upd_event = last_change['new_data']
    #             ne = copy.deepcopy(upd_event)
    #             ne.data.pop('synchronized')
    #             moved_from = None if updated[0]['old_calendar'] == upd_event.calendar else updated[0]['old_calendar']
    #             synced = plugin.update_event(ne, moved_from_calendar=moved_from,
    #                                          days_in_future=12, days_in_past=1)
    #             if synced.is_synchronized():
    #                 self.updated_events.pop(update_id)
    #                 plugin.log_info('successfully updated ', upd_event.data)
    #                 # self.display_new_event(synced)
    #                 events_to_display.append(synced)
    #             else:
    #                 plugin.log_info('could not update. kept in cache', upd_event)
    #                 # self.display_new_event(upd_event)
    #                 events_to_display.append(upd_event)
    #
    #         for deleted in list(self.deleted_events):
    #             plugin.log_info('DELETED EVENT: ', deleted.data)
    #
    #             if plugin.delete_event(deleted):
    #                 plugin.log_info('successfully deleted')
    #                 # self.event_cache['delete'].remove(deleted)
    #
    #             else:
    #                 plugin.log_info('could not delete. kept in cache', deleted.data)
    #                 # self.view.remove_event(deleted.id)
    #                 events_to_remove.append(deleted.id)
    #         # self.__data__['event_cache'] = self.event_cache
    #         # self._save_data()
    #         plugin.log_info('got myself some cache:', self.__repr__())
    #
    #     except KeyError:
    #         plugin.log_warn('no event cache yet. might get initialized in the future...')
    #     return events_to_display, events_to_remove
