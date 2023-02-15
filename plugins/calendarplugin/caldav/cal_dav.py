import datetime
import re
import uuid
from typing import Dict, Any, Union, List, Optional

import dateutil.rrule
import recurring_ical_events
import requests.exceptions
import urllib3.exceptions
import vobject
from PyQt5.QtCore import QTimeZone
from PyQt5.QtGui import QColor

import pytz
from caldav.lib.error import AuthorizationError

from requests.exceptions import SSLError

from credentials import CalDAVCredentials, CredentialsNotValidException, CredentialType
from plugins.calendarplugin.calendar_plugin import CalendarPlugin, Event, Calendar, CalendarData, CalendarAccessRole, \
    Todo, Alarm
import caldav
import icalendar


class CalDavPlugin(CalendarPlugin):

    def __init__(self):
        super().__init__()
        self.client = None
        self.principal = None
        self._calendars: Dict[str, caldav.Calendar] = {}
        urllib3.warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)

    def setup(self):
        self.get_event_colors()

    def _connect(self, ssl_verify=True) -> bool:
        try:
            self.client = caldav.DAVClient(CalDAVCredentials.get_url(),
                                           ssl_verify_cert=CalDAVCredentials.get_ssl_verify() if ssl_verify else False,
                                           username=CalDAVCredentials.get_username(),
                                           password=CalDAVCredentials.get_password())
            self.log_info('client created successfully')
            self.principal = self.client.principal()
            self.log_info(f'connection established successfully')
            return True
        except requests.exceptions.RequestException as e:
            self.client = None
            self.principal = None
            self.log_warn('Connection failed. returning None', exception=e)
            return False
        except urllib3.exceptions.HTTPError as e:
            self.client = None
            self.principal = None
            self.log_warn('Connection failed. returning None', exception=e)
            return False
        except ConnectionError as e:
            self.client = None
            self.principal = None
            self.log_warn('Connection failed. returning None', exception=e)
            return False
        except SSLError as ssl_e:
            self.client = None
            self.principal = None
            self.log_warn('SSL Verification Error', exception=ssl_e)
            return self._connect(CalDAVCredentials.get_ssl_verify(accept_only=False))
        except AuthorizationError as e:
            self.client = None
            self.principal = None
            self.log_warn('Authorization Error:', exception=e)
            raise CredentialsNotValidException(CalDAVCredentials, CredentialType.PASSWORD)

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             allow_cache=False, *args, **kwargs) -> Union[CalendarData, None]:
        self.log_info('connect...')
        if not self._connect():
            return None
        self.log_info('CONNECTED')
        calendars = self._get_calendars()
        self.log_info('... get colors ...')
        colors = self.get_event_colors()
        self.log_info('GET ALL CALENDARS')
        if calendars is not None:
            events = []
            for calendar in calendars:
                try:
                    self.log_info(f'... get events for {calendar.name} ...')
                    cal_events = self._get_events(calendar, days_in_future, days_in_past=days_in_past)
                    events.extend(cal_events)
                    cal_todos = {}  # self._get_tasks(calendar)
                except requests.exceptions.RequestException as e:
                    self.log_error(e, exception=e)
                    return None
            return CalendarData(calendars={c.id: c for c in calendars},
                                events={ev.get_unique_instance_id(): ev for ev in events},
                                todos={td.id: td for td in cal_todos},
                                colors=colors)

    def _create_event(self, event: icalendar.Event, calendar_id: str) -> vobject.icalendar.RecurringComponent:
        self.log_info('trying to create event', event)
        try:
            calendar = self._get_calendar(calendar_id)
            ret = calendar.save_event(self._ical_from_iev(event).to_ical())
            return ret.vobject_instance.vevent

        except Exception as e:
            raise ConnectionError(e)

    @staticmethod
    def _ical_from_iev(ev: icalendar.Event) -> icalendar.Calendar:
        c = icalendar.Calendar()
        c.add_component(ev)
        return c

    def _ical_to_caldav_event(self, event: icalendar.Event, calendar: caldav.Calendar) -> caldav.Event:
        return caldav.Event(self.client, data=self._ical_from_iev(event),
                            url=calendar.canonical_url + event.get('UID') + '.ics',
                            parent=calendar, id=event.get('UID'))

    def _update_event(self, event: icalendar.Event, calendar_id,
                      move_to_calendar_id=None) -> vobject.icalendar.RecurringComponent:
        self.log_info('trying to update event', event)
        try:
            if move_to_calendar_id is not None:
                old_calendar = self._get_calendar(calendar_id)
                new_calendar = self._get_calendar(move_to_calendar_id)
                # 1) 'copy to new calendar'
                edited_event = self._ical_to_caldav_event(event, new_calendar)
                ret = edited_event.save()
                # 2) delete from old calendar
                ev_2_del = self._ical_to_caldav_event(event, old_calendar)
                ev_2_del.delete()
            else:
                calendar = self._get_calendar(calendar_id)
                edited_event = self._ical_to_caldav_event(event, calendar)
                # ev2 = calendar.event_by_uid(event.get('UID'))
                # ev2.vobject_instance.vevent = vobject.readOne(event.to_ical().decode())
                # ret = ev2.save()
                ret = edited_event.save()

            updated_event = ret.vobject_instance.vevent
            return updated_event
        except caldav.error.NotFoundError as nfe:
            raise nfe
        except Exception as e:
            raise ConnectionError(e)

    def _delete_event(self, event: icalendar.Event, calendar_id: str) -> bool:
        self.log('trying to delete %r' % event)
        try:
            calendar = self._get_calendar(calendar_id)
            event_to_delete = self._ical_to_caldav_event(event, calendar)
            event_to_delete.delete()
            # ev2 = calendar.event_by_uid(event.get('UID'))
            # ret = ev2.delete()
            return True
        except Exception as e:
            self.log_warn(e)
            return True

    def _get_calendar(self, calendar_id: str) -> Optional[caldav.Calendar]:

        calendar = self._calendars.get(calendar_id, None)
        if calendar is None:
            for cal in self.client.principal().calendars():

                self.log_info(f'get props for {cal}')
                cal_id = self._calendar_from_cal_dav_cal(cal).id
                if cal_id == calendar_id:
                    return cal
        else:
            return calendar
        raise Exception(f'CALENDAR {calendar_id} not found!')

    def _get_tasks(self, calendar: Calendar):
        assert calendar.id in self._calendars
        if not self._connect():
            return None
        todos = self._calendars[calendar.id].todos()
        return [self._todo_from_vtodo(td.vobject_instance.vtodo, calendar) for td in todos]

    def _get_calendars(self) -> Union[List[Calendar], None]:
        if not self._connect():
            return None

        calendars = []
        self.log_info('get calendars from principal...')
        _cals: List[caldav.Calendar] = self.principal.calendars()
        self.log_info('...done')

        for _cal in _cals:
            self.log_info(f'get props for {_cal}')
            calendar = self._calendar_from_cal_dav_cal(_cal)
            calendars.append(calendar)

            self._calendars[calendar.id] = _cal
        return calendars

    def _get_events(self, calendar: Calendar, days_in_future=7, days_in_past=1):
        assert calendar.id in self._calendars
        start_time = (datetime.datetime.utcnow().date() -
                      datetime.timedelta(days=days_in_past))
        end_time = (datetime.datetime.utcnow().date() +
                    datetime.timedelta(days=days_in_future))
        # now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        print('SEARCHING FOR ', start_time, end_time)
        event_result = self._calendars[calendar.id].date_search(start=start_time,
                                                                end=end_time)
        events = []
        for ev in event_result:
            events.extend(self._events_from_vevent(ev, calendar, days_in_future, days_in_past))
        return events

    def _events_from_vevent(self, ev, calendar: Calendar, days_in_future=7, days_in_past=1):
        events = []
        if ev.vobject_instance.vevent.rruleset:
            self.log_info(f"FOUND RECURRING EVENT: {ev.vobject_instance.vevent.summary}")
            all_day = not isinstance(ev.vobject_instance.vevent.dtstart.value, datetime.datetime)
            recurring_ical_events.of(ev.icalendar_instance)
            if all_day:
                time_instances = recurring_ical_events.of(ev.icalendar_instance) \
                    .between(datetime.datetime.now() - datetime.timedelta(days=days_in_past),
                             datetime.datetime.now() + datetime.timedelta(days=days_in_future))
            else:
                time_instances = recurring_ical_events.of(ev.icalendar_instance) \
                    .between(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_in_past),
                             datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days_in_future))
            self.log_info(f"INSTANCES: {time_instances}")
            for time_instance in time_instances:
                event = self._event_from_vevent(vobject.readOne(time_instance.to_ical().decode()), calendar,
                                                recurrence_id=str(time_instance.get('DTSTART').dt),
                                                rruleset=ev.vobject_instance.vevent.rruleset)
                # duration = event.end - event.start
                # event.set_start_time(time_instance)
                # event.set_end_time(time_instance + duration)
                events.append(event)
        else:
            event = self._event_from_vevent(ev.vobject_instance.vevent, calendar)
            events.append(event)
        return events

    def _ical_event_from_event(self, event: Event) -> icalendar.Event:

        ical = icalendar.Event()
        ical.add('uid', event.id if event.id is not None else str(uuid.uuid1()))
        ical.add('dtstart', event.start if not event.all_day else event.start.date())
        ical.add('dtend', event.end if not event.all_day else event.end.date())
        ical.add('summary', event.title)
        if event.bg_color is not None:
            ical.add('ffcolor', event.bg_color.name())
        ical.add('location', event.location)
        ical.add('description', event.description)
        if event.recurrence:
            rec_str = re.sub('.*\n?RRULE:', '', str(event.recurrence))
            ical.add('rrule', icalendar.vRecur.from_ical(rec_str))
        return ical

    def _todo_from_vtodo(self, td: vobject.icalendar.RecurringComponent, calendar: Calendar) -> Todo:

        if hasattr(td, 'dtstart') and td.dtstart:
            all_day = not isinstance(td.dtstart.value, datetime.datetime)
            start = td.dtstart.value if not all_day else datetime.datetime.combine(td.dtstart.value,
                                                                                   datetime.datetime.min.time())
        else:
            all_day = False
            start = None
        if td.due:
            all_day = not isinstance(td.due.value, datetime.datetime)
            due = td.due.value if not all_day else datetime.datetime.combine(td.due.value,
                                                                             datetime.datetime.min.time())
            if 'valarm' in td.contents:
                alarm = td.valarm
                trigger = alarm.trigger.value
                action = alarm.action.value
                desc = alarm.description.value
                alarmtime = due.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) + trigger
                self.log(f'TODO-ALARM: {trigger}, {alarmtime} {action}, {desc}')
        else:
            due = None

        return Todo(todo_id=td.uid.value if 'uid' in td.contents else '',
                    title=td.summary.value if 'summary' in td.contents else '',
                    start=start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) if start else
                    None,
                    due=due.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) if due else None,
                    description=td.description.value if 'description' in td.contents else '',
                    location=td.location.value if 'location' in td.contents else '',
                    categories=[c for c in td.categories.value] if 'categories' in td.contents else [],
                    percent_complete=td.percent_complete.value if 'percent-complete' in td.contents else 0,
                    all_day=all_day,
                    calendar=calendar,
                    fg_color=None,
                    bg_color=QColor(td.ffcolor.value) if 'ffcolor' in td.contents else None,
                    data={'id': td.uid.value, 'synchronized': True},
                    timezone=None,
                    recurring_event_id=None,
                    recurrence=None,
                    synchronized=True
                    )

    def _event_from_vevent(self, ev: vobject.icalendar.RecurringComponent, calendar: Calendar,
                           recurrence_id: str = None, rruleset: dateutil.rrule.rruleset = None) -> Event:

        all_day = not isinstance(ev.dtstart.value, datetime.datetime)
        start = ev.dtstart.value if not all_day else datetime.datetime.combine(ev.dtstart.value,
                                                                               datetime.datetime.min.time())
        end = ev.dtend.value if not all_day else datetime.datetime.combine(ev.dtend.value,
                                                                           datetime.datetime.min.time())

        alarm = None
        if 'valarm' in ev.contents:
            valarm = ev.valarm
            trigger = valarm.trigger.value
            action = valarm.action.value
            desc = valarm.description.value
            alarmtime = start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) + trigger
            alarm = Alarm(alarmtime, trigger, desc, action)
            # self.log(f'{trigger}, {alarmtime} {action}, {desc}')

        recurrence = None
        if recurrence_id is not None:
            recurrence = dateutil.rrule.rrulestr(str(rruleset._rrule[0]))
        return Event(event_id=ev.uid.value if 'uid' in ev.contents else '',
                     title=ev.summary.value if 'summary' in ev.contents else '',
                     start=start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())),
                     end=end.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())),
                     description=ev.description.value if 'description' in ev.contents else '',
                     location=ev.location.value if 'location' in ev.contents else '',
                     all_day=all_day,
                     calendar=calendar,
                     fg_color=None,
                     bg_color=QColor(ev.ffcolor.value) if 'ffcolor' in ev.contents else None,
                     data={'id': ev.uid.value, 'synchronized': True},
                     timezone=None,
                     recurring_event_id=recurrence_id,
                     recurrence=recurrence,
                     synchronized=True,
                     alarm=alarm
                     )

    @staticmethod
    def _calendar_from_cal_dav_cal(cal: caldav.Calendar) -> Calendar:
        cal_id = str(cal.url)
        # cal_name = data.get('displayname', None)
        # cal_sync_token = data.get('sync-token', None)
        props = cal.get_properties([caldav.dav.DisplayName(),
                                    caldav.elements.ical.CalendarColor(),
                                    caldav.elements.cdav.CalendarDescription()])
        print('get display name')
        cal_name = props[caldav.dav.DisplayName().tag]
        print('getcal color')
        cal_color = props[caldav.elements.ical.CalendarColor().tag][:7]
        print('get description')
        primary = props[caldav.elements.cdav.CalendarDescription().tag] == 'primary'
        # print('get display name')
        # cal_name = cal.get_property(caldav.dav.DisplayName())
        # print('getcal color')
        # cal_color = cal.get_property(caldav.elements.ical.CalendarColor())[:7]
        # print('get description')
        # primary = cal.get_property(caldav.elements.cdav.CalendarDescription()) == 'primary'
        return Calendar(calendar_id=cal_id, name=cal_name,
                        primary=primary,
                        fg_color=QColor('#ffffff'),
                        bg_color=QColor(cal_color),
                        access_role=CalendarAccessRole.OWNER,
                        data={'url': str(cal.url)}
                        )

    def quit(self):
        pass

    def create_event(self, event: Event):
        self.log_warn('CREATE EVENT', event)
        try:
            created_event_data = self._create_event(self._ical_event_from_event(event), event.calendar.id)
            return self._event_from_vevent(created_event_data, event.calendar)
        except ConnectionError:
            event.id = f'non-sync{uuid.uuid4()}'
            event.data['id'] = event.id
            event.mark_desynchronized()
            return event

    def delete_event(self, event: Event) -> bool:

        return self._delete_event(self._ical_event_from_event(event), event.calendar.id)

    def update_event(self, event: Event, moved_from_calendar: Union[Calendar, None] = None) -> Union[Event, None]:
        if moved_from_calendar is not None:
            move_to_calendar_id = event.calendar.id
            calendar_id = moved_from_calendar.id
        else:
            move_to_calendar_id = None
            calendar_id = event.calendar.id
        try:
            updated_event = self._update_event(self._ical_event_from_event(event), calendar_id=calendar_id,
                                               move_to_calendar_id=move_to_calendar_id)
            return self._event_from_vevent(updated_event, event.calendar)
        except ConnectionError:
            if moved_from_calendar is not None:
                event.calendar = moved_from_calendar
            event.mark_desynchronized()
            return event

    def get_event_colors(self) -> Dict[Any, Dict[str, QColor]]:
        bg_colors = {
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
        ret = {str(k): {'fg_color': QColor('#f1f1f1'), 'bg_color': QColor(v)} for k, v in bg_colors.items()}
        ret[None] = {}
        CalDavPlugin._colors = ret
        return ret
