import datetime
from typing import List, Dict, Union

import requests
from PyQt5.QtGui import QColor
from dateutil.tz import tzlocal
from icalendar import Calendar as iCalendar

from helpers.settings_storage import SettingsStorage
from plugins.calendarplugin.caldav.conversions import CalDavConversions
from plugins.calendarplugin.calendar_plugin import CalendarPlugin, Calendar, EventInstance, Event, \
    CalendarData


class ReadOnlyWebCalPlugin(CalendarPlugin):

    def __init__(self):
        super().__init__()

    def quit(self):
        pass

    def setup(self):
        pass

    def create_event(self, event: Event, days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        pass

    def delete_event(self, event: Event) -> bool:
        pass

    def delete_event_instance(self, instance: EventInstance, days_in_future: int,
                              days_in_past: int) -> Union[Event, List[EventInstance]]:
        pass

    def update_event(self, event: Event, days_in_future: int, days_in_past: int,
                     moved_from_calendar: Union[Calendar, None] = None) -> Union[Event, List[EventInstance]]:
        pass

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             *args, **kwargs) -> Union[CalendarData, None]:
        raise NotImplementedError('Not Implemented')


class WebCalPluginInstance(ReadOnlyWebCalPlugin):

    def __init__(self, url: str, name: str, fg_color: QColor = None, bg_color: QColor = None):
        super().__init__()
        self.url = url
        self.name = name
        self.fg_color = fg_color
        self.bg_color = bg_color

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

        if cache_mode == CalendarPlugin.CacheMode.FORCE_REFRESH:
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
                            events=CalDavConversions.expand_events(
                                self.events, self.ical_events,
                                start=datetime.datetime.now().replace(tzinfo=tzlocal()) -
                                datetime.timedelta(days=days_in_past),
                                end=datetime.datetime.now().replace(tzinfo=tzlocal()) +
                                datetime.timedelta(days=days_in_future)),
                            colors=self.get_event_colors())
