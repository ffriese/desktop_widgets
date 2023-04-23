import datetime
from typing import List, Dict, Union, Callable

import requests
from PyQt5.QtGui import QColor
from dateutil.tz import tzlocal
from icalendar import Calendar as iCalendar

from helpers.settings_storage import SettingsStorage
from plugins.calendarplugin.caldav.conversions import CalDavConversions
from plugins.calendarplugin.calendar_plugin import CalendarPlugin
from plugins.calendarplugin.data_model import Calendar, Event, EventInstance, CalendarData


class ReadOnlyWebCalPlugin(CalendarPlugin):

    def __init__(self, cal_id: str):
        super().__init__(cal_id)

    def quit(self):
        pass

    def setup(self):
        pass

    def _create_synced_event(self, event: Event, days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        pass

    def _delete_synced_event(self, event: Event) -> bool:
        pass

    def _update_synced_event(self, event: Event, days_in_future: int, days_in_past: int,
                             moved_from_calendar: Union[Calendar, None] = None) -> Union[Event, List[EventInstance]]:
        pass

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             *args, **kwargs) -> Union[CalendarData, None]:
        raise NotImplementedError('Not Implemented')


class WebCalPluginInstance(ReadOnlyWebCalPlugin):

    def __init__(self, url: str, name: str, fg_color: QColor = None, bg_color: QColor = None,
                 event_filter: Callable[[Event], bool] = None):
        super().__init__(name)
        self.url = url
        self.name = name
        self.fg_color = fg_color
        self.bg_color = bg_color
        self.event_filter = event_filter

        self.calendar: Calendar
        self.events: Dict[str, Event]
        self.ical_events: Dict[str, iCalendar]
        self.calendar, self.events, self.ical_events = SettingsStorage.load_or_default(
            f'web_cal_{self.name}', (None, {}, {}))

    def get_data(self) -> str:
        return requests.get(self.url).text

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             cache_mode=CalendarPlugin.CacheMode.FORCE_REFRESH,
                             *args, **kwargs) -> Union[CalendarData, None]:
        self.log_info('GOT TO MAIN METHOD', cache_mode, args, kwargs)
        if cache_mode == CalendarPlugin.CacheMode.FORCE_REFRESH or not self.calendar:
            try:
                self.calendar, self.events, self.ical_events = CalDavConversions.load_all_from_ical_text(
                    ical_string=self.get_data(),
                    uri=self.url, calendar_name=self.name,
                    calendar_id=f'{self.url}_{self.name}',
                    fg_color=self.fg_color, bg_color=self.bg_color)
                SettingsStorage.save((self.calendar, self.events, self.ical_events), f'web_cal_{self.name}')
            except Exception as e:
                self.log_error(e)
                return None
        elif cache_mode == CalendarPlugin.CacheMode.REFRESH_LATER:
            self.log_info('REFRESHING_LATER...')
            self.currently_updating = False
            self.update_async(days_in_future=days_in_future, days_in_past=days_in_past, *args, **kwargs,
                              cache_mode=CalendarPlugin.CacheMode.FORCE_REFRESH)
        if not self.calendar:
            return None

        return CalendarData(calendars={self.calendar.id: self.calendar},
                            events=self.expand_filtered(days_in_future=days_in_future, days_in_past=days_in_past),
                            colors=self.get_event_colors())

    def filter_event(self, ev: Union[Event, List[EventInstance]]):
        if isinstance(ev, list):
            return [e for e in ev if self.event_filter(e.instance)]
        return ev if self.event_filter(ev) else None

    def expand_filtered(self, days_in_future, days_in_past):
        unfiltered = CalDavConversions.expand_events(
                                self.events, self.ical_events,
                                start=datetime.datetime.now().replace(tzinfo=tzlocal()) -
                                datetime.timedelta(days=days_in_past),
                                end=datetime.datetime.now().replace(tzinfo=tzlocal()) +
                                datetime.timedelta(days=days_in_future))
        if self.event_filter:
            filtered = {ev_id: self.filter_event(event) for ev_id, event in unfiltered.items()}

            return {e_id: ev for e_id, ev in filtered.items() if ev}
        return unfiltered




