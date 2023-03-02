from __future__ import print_function

import logging
import uuid
from typing import Union, List, Dict, Any

from dateutil import parser as dateutil_parser
from dateutil.tz import tzlocal
import datetime

from PyQt5.QtGui import QColor
from googleapiclient.errors import HttpError
from httplib2 import ServerNotFoundError

from credentials import GoogleCredentials
from plugins.calendarplugin.calendar_plugin import CalendarPlugin, Event, CalendarData, Calendar, CalendarAccessRole


class GoogleCalendarPlugin(CalendarPlugin):
    _colors = {}

    def __init__(self):
        super().__init__()
        self.log_warn('This Plugin is Deprecated and might not work correctly')

    def setup(self):
        self.get_event_colors()
        self.log('init....', level=logging.DEBUG)
        try:
            GoogleCredentials.get_service()
            self.log('connection established. credentials appear valid', level=logging.DEBUG)
            return True
        except Exception as e:
            self.log('Connection Error: %r' % e, level=logging.WARN)
            return False

    def quit(self):
        pass

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             allow_cache=False, *args, **kwargs) -> Union[CalendarData, None]:
        try:
            self.log_debug('... get calendars ...')
            calendars = self._get_calendars()
            self.log('... get colors ...', level=logging.DEBUG)
            colors = self.get_event_colors()
            if calendars is not None:
                events = []
                for calendar in calendars:
                    self.log(f'... get events for {calendar.name} ...', level=logging.DEBUG)
                    cal_events = self._get_events(calendar, days_in_future, days_in_past=days_in_past)
                    events.extend(cal_events)

                return CalendarData(calendars={c.id: c for c in calendars},
                                    events={e.id: e for e in events},
                                    colors=colors)
            else:
                return None
        except ServerNotFoundError as e:
            self.log_error(e)
            return None
        except ConnectionAbortedError as e:
            self.log_error(e)
            return None
        except HttpError as e:
            self.log_error(e)
            return None
        except TimeoutError as e:
            self.log_error(e)
            return None

    """
         THE EXTERNALLY VISIBLE EVENT-MANAGEMENT-METHODS
    """
    def create_event(self, event: Event) -> Union[Event, None]:
        created_event_data = self._create_event(self._dict_from_event(event), event.calendar.id)
        return self._event_from_dict(created_event_data, event.calendar, self._colors)

    def update_event(self, event: Event, moved_from_calendar: Union[Calendar, None] = None) -> Union[Event, None]:

        if moved_from_calendar is not None:
            move_to_calendar_id = event.calendar.id
            calendar_id = moved_from_calendar.id
        else:
            move_to_calendar_id = None
            calendar_id = event.calendar.id
        updated_event = self._update_event(self._dict_from_event(event), calendar_id=calendar_id,
                                           move_to_calendar_id=move_to_calendar_id)
        return self._event_from_dict(updated_event, event.calendar, self._colors)

    def delete_event(self, event: Event) -> bool:
        event.data['id'] = event.id
        event.data['calendar_id'] = event.calendar.id
        return self._delete_event(event.data)

    """
     THE INTERNAL METHODS TO MANAGE THE GOOGLE CALENDAR API WITH THEIR DICT-SYNTAX
    """
    def _create_event(self, event: dict, calendar_id: str = 'primary') -> Union[dict, None]:
        self.log_info('trying to create event', event)
        try:
            # raise ConnectionError()
            event = GoogleCredentials.get_service().events().insert(calendarId=calendar_id, body=event).execute()
        except (ConnectionError, ServerNotFoundError) as e:
            event['id'] = f'non-sync{uuid.uuid4()}'
            event['synchronized'] = False
            self.log_warn(f'err:"{e}"')
            self.log_warn(f'event: "{event}"')

        return event

    def _update_event(self, event: dict, calendar_id='primary', move_to_calendar_id=None) -> Union[dict, None]:
        if 'sequence' in event.keys():
            event['sequence'] += 1
        try:
            # raise ConnectionError()
            updated_event = GoogleCredentials.get_service().events().patch(
                calendarId=calendar_id, eventId=event['id'], body=event).execute()
            if move_to_calendar_id is not None:
                updated_event = GoogleCredentials.get_service().\
                    events().move(calendarId=calendar_id, eventId=event['id'],
                                  destination=move_to_calendar_id).execute()
            return updated_event
        except (ConnectionError, ServerNotFoundError) as e:
            self.log_error(f' le error err:"{e}"')
            if move_to_calendar_id is not None:
                event['calendar_id'] = move_to_calendar_id
            event['synchronized'] = False
            return event

    def _delete_event(self, event: dict) -> bool:
        self.log('trying to delete %r' % event)
        try:
            # raise ConnectionError()
            GoogleCredentials.get_service().events().delete(calendarId=event['calendar_id'], eventId=event['id']).execute()
            self.log('successfully deleted event ', event['id'])
            return True
        except Exception as e:
            self.log(type(e), e, level=logging.ERROR)
            return False

    """
        All kinds of helper functions
    """

    @staticmethod
    def _calendar_from_dict(calendar: dict, primary: bool = False) -> Calendar:
        return Calendar(calendar_id=calendar.get('id', None),
                        name=calendar.get('summary', None),
                        access_role=GoogleCalendarPlugin._parse_access_role(calendar.get('accessRole', 'reader')),
                        fg_color=QColor(calendar.get('foregroundColor', '#000000')),
                        bg_color=QColor(calendar.get('backgroundColor', '#ffffff')),
                        data=calendar,
                        primary=primary)

    @staticmethod
    def _event_from_dict(event: dict, calendar: Calendar, _colors: Dict[Any, Dict[str, QColor]] = None) -> Event:
        kwargs = {
            key: event.get(key, '') for key in ['location', 'description']
        }
        start = dateutil_parser.parse(
            event['start'].get('dateTime', event['start'].get('date'))).astimezone(tzlocal())
        end = dateutil_parser.parse(
            event['end'].get('dateTime', event['end'].get('date'))).astimezone(tzlocal())

        # 'recurrence': [
        #    'RRULE:FREQ=DAILY;COUNT=2'
        # ],
        # 'attendees': [
        #    {'email': 'lpage@example.com'},
        #    {'email': 'sbrin@example.com'},
        # ],
        # 'reminders': {
        #    'useDefault': False,
        #    'overrides': [
        #        {'method': 'email', 'minutes': 24 * 60},
        #        {'method': 'popup', 'minutes': 10},
        #    ],
        # }
        if _colors is not None:
            event_colors = _colors.get(event.get('colorId', None))
        else:
            event_colors = {}

        return Event(event_id=event.get('id', None),
                     title=event.get('summary', None),
                     start=start,
                     end=end,
                     all_day='date' in event['start'].keys() and event['start']['date'] is not None,
                     calendar=calendar,
                     fg_color=event_colors.get('fg_color', None),
                     bg_color=event_colors.get('bg_color', None),
                     data=event,
                     timezone=event['start'].get('timeZone', None),
                     recurring_event_id=event.get('recurringEventId', None),
                     recurrence=event.get('recurrence', None),
                     synchronized=event.get('synchronized', True),
                     **kwargs)

    def _parse_event_color_id(self, color_id) -> QColor:
        return self._get_colors()[color_id]

    @staticmethod
    def _color_id_from_color(color):
        for color_id, colors in GoogleCalendarPlugin._colors.items():
            if color_id is not None and colors['bg_color'].name() == color.name():
                return color_id
        return None

    @staticmethod
    def _dict_from_event(event: Event) -> dict:
        if event.id is not None:
            event.data['id'] = event.id
        event.data['summary'] = event.title
        event.data['location'] = event.location
        event.data['description'] = event.description

        if event.bg_color is None:
            event.data.pop('colorId', None)
        else:
            event.data['colorId'] = GoogleCalendarPlugin._color_id_from_color(event.bg_color)

        if 'start' not in event.data.keys():
            event.data['start'] = {}
            event.data['end'] = {}
        if event.all_day:
            event.data['start']['date'] = event.start.date().isoformat()
            event.data['start']['dateTime'] = None
            event.data['end']['date'] = event.end.date().isoformat()
            event.data['end']['dateTime'] = None
        else:
            event.data['start']['dateTime'] = event.start.astimezone(tzlocal()).isoformat()
            event.data['start']['date'] = None
            event.data['end']['dateTime'] = event.end.astimezone(tzlocal()).isoformat()
            event.data['end']['date'] = None
            if event.timezone is not None:
                event.data['start']['timeZone'] = event.timezone
                event.data['end']['timeZone'] = event.timezone
        return event.data

    @staticmethod
    def _parse_access_role(access_role_str) -> CalendarAccessRole:
        try:
            return {
                'owner': CalendarAccessRole.OWNER,
                'reader': CalendarAccessRole.READER,
                'writer': CalendarAccessRole.WRITER,
                'freeBusyReader': CalendarAccessRole.FREE_BUSY_READER
            }[access_role_str]
        except KeyError:
            return CalendarAccessRole.READER

    def _get_calendars(self) -> Union[List[Calendar], None]:
        try:
            primary = GoogleCredentials.get_service().calendars().get(calendarId='primary').execute()
            received_calendars = GoogleCredentials.get_service().calendarList().list().execute()
            calendars = []
            # make sure primary calendar is first
            for cal in received_calendars['items']:
                if cal.get('summary', 'NO_SUMMARY') == primary.get('summary', 'PRIMARY_CALENDAR'):
                    calendars.append(self._calendar_from_dict(cal, primary=True))
            for cal in received_calendars['items']:
                if cal.get('summary', 'NO_SUMMARY') != primary.get('summary', 'PRIMARY_CALENDAR'):
                    calendars.append(self._calendar_from_dict(cal))
            return calendars
        except ServerNotFoundError as e:
            self.log('Connection Aborted Error: %r' % e)
            return None
        except ConnectionAbortedError as e:
            self.log('Connection Aborted Error: %r' % e)
            return None

    def _get_events(self, calendar: Calendar, days_in_future=7, days_in_past=1):
        start_time = (datetime.datetime.utcnow().date() -
                     datetime.timedelta(days=days_in_past)).isoformat() + 'T00:00:00.000000Z'
        end_time = (datetime.datetime.utcnow().date() +
                    datetime.timedelta(days=days_in_future)).isoformat() + 'T00:00:00.000000Z'
        # now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        events_result = GoogleCredentials.get_service().events().list(
            calendarId=calendar.id,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime').execute()
        _evs = events_result.get('items', [])
        evs = []
        for ev in _evs:
            event = GoogleCalendarPlugin._custom_event_interpretations(ev, calendar)
            if event is not None:
                evs.append(self._event_from_dict(event, calendar, GoogleCalendarPlugin._colors))
        return evs

    def get_recurring_event(self, event: Event):
        rec_event = self._get_recurring_event(event.data['recurringEventId'], event.calendar.id)
        return self._event_from_dict(rec_event, event.calendar, GoogleCalendarPlugin._colors)

    def _get_recurring_event(self, recurring_event_id: str, calendar_id: str):
        event = GoogleCredentials.get_service().events().get(calendarId=calendar_id,
                                                             eventId=recurring_event_id).execute()
        return event

    def _get_actual_colors(self) -> Dict[Any, Dict[str, QColor]]:
        colors = GoogleCredentials.get_service().color_picker().get().execute()['event']
        logging.log(f'colors:"{colors}"')
        for color_id in colors.keys():
            colors[color_id] = {
                'fg_color': QColor(colors[color_id]['foreground']),
                'bg_color': QColor(colors[color_id]['background']),
            }
        colors[None] = {}
        GoogleCalendarPlugin._colors = colors
        return colors

    def get_event_colors(self) -> Dict[Any, Dict[str, QColor]]:
        bg_colors = {
            1:  "#7986cb",  # Lavender
            2:  "#33b679",  # Sage
            3:  "#8e24aa",  # Grape
            4:  "#e67c73",  # Flamingo
            5:  "#f6c026",  # Banana
            6:  "#f5511d",  # Tangerine
            7:  "#039be5",  # Peacock
            8:  "#616161",  # Graphite
            9:  "#3f51b5",  # Blueberry
            10: "#0b8043",  # Basil
            11: "#d60000"   # Tomato
        }
        ret = {str(k): {'fg_color': QColor('#f1f1f1'), 'bg_color': QColor(v)} for k, v in bg_colors.items()}
        ret[None] = {}
        GoogleCalendarPlugin._colors = ret
        return ret

