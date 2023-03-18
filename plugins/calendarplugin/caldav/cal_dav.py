import copy
import datetime
import uuid
from typing import Dict, Any, Union, List

import requests.exceptions
import urllib3.exceptions
from PyQt5.QtGui import QColor
from caldav import Principal
from caldav.lib.error import AuthorizationError
from dateutil.tz import tzlocal

from requests.exceptions import SSLError

from credentials import CalDAVCredentials, CredentialsNotValidException, CredentialType
from helpers.settings_storage import SettingsStorage
from helpers.tools import time_method
from plugins.calendarplugin.caldav.conversions import CalDavConversions
from plugins.calendarplugin.caldav.caldav_calendar import CalDavCalendar
from plugins.calendarplugin.calendar_plugin import CalendarPlugin, Calendar, Event, CalendarData, EventInstance
import caldav


class CalDavPlugin(CalendarPlugin):

    def __init__(self):
        super().__init__()
        self.client = None
        self.principal: Principal = None
        self.caldav_calendars: Dict[str, CalDavCalendar] = SettingsStorage.load_or_default('caldav_cals', {})

        urllib3.warnings.simplefilter('ignore', urllib3.exceptions.InsecureRequestWarning)

    def setup(self):
        pass

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

    def get_calendars(self, force_refresh=False):
        if not self._connect():
            return None
        for cal in self.principal.calendars():
            cal_id = str(cal.url)
            if cal_id not in self.caldav_calendars:
                new_calendar = CalDavCalendar(cal)
                new_calendar.fetch_properties()
                self.caldav_calendars[cal_id] = new_calendar
            elif force_refresh:
                self.caldav_calendars[cal_id].fetch_properties()

        SettingsStorage.save(self.caldav_calendars, 'caldav_cals')

    def sync_calendars(self):
        self.log_info('SYNC_CALENDARS!')
        if not self.caldav_calendars:
            self.get_calendars()
        try:
            for cal in self.caldav_calendars.values():
                self.log_info(f'syncing {cal.id()}')
                cal.sync_metadata()

            SettingsStorage.save(self.caldav_calendars, 'caldav_cals')
        except Exception as e:
            self.log_error(e)

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             cache_mode=CalendarPlugin.CacheMode.FORCE_REFRESH, *args, **kwargs) -> Union[CalendarData, None]:
        self.log_info('GOT TO MAIN METHOD', cache_mode, args, kwargs)
        if cache_mode == CalendarPlugin.CacheMode.FORCE_REFRESH or not self.caldav_calendars:
            self.sync_calendars()
        elif cache_mode == CalendarPlugin.CacheMode.REFRESH_LATER:
            self.log_info('REFRESHING_LATER...')
            self.currently_updating = False
            self.update_async(days_in_future=days_in_future, days_in_past=days_in_past, *args, **kwargs,
                              cache_mode=CalendarPlugin.CacheMode.FORCE_REFRESH)
        return CalendarData(
            events=self.expand_events(start=datetime.datetime.now().replace(tzinfo=tzlocal()) -
                                      datetime.timedelta(days=days_in_past),
                                      end=datetime.datetime.now().replace(tzinfo=tzlocal()) +
                                      datetime.timedelta(days=days_in_future)),
            calendars={c_id: c.calendar for c_id, c in self.caldav_calendars.items()},
            colors=self.get_event_colors()
        )

    def quit(self):
        pass

    def create_event(self, event: Event,
                     days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        self.log_warn('CREATE EVENT', event)
        try:
            event_to_create = CalDavConversions.caldav_event_from_event(
                event, self.caldav_calendars[event.calendar.id].caldav_cal)
            raw_created_event = event_to_create.save()
            self.caldav_calendars[event.calendar.id].register_update(raw_created_event.url)
            self.save_data()
            return CalDavConversions.expand_caldav_event(raw_created_event, event, days_in_future, days_in_past)
        except Exception as e:
            print(e)
            event.id = f'non-sync{uuid.uuid4()}'
            event.data['id'] = event.id
            event.mark_desynchronized()
            return event

    def delete_event(self, event: Event) -> bool:
        self.log('trying to delete %r' % event)
        try:
            event_to_delete = CalDavConversions.caldav_event_from_event(
                event, self.caldav_calendars[event.calendar.id].caldav_cal)
            event_to_delete.delete()
            self.caldav_calendars[event.calendar.id].register_delete(event_to_delete)
            self.save_data()
            return True
        except Exception as e:
            self.log_warn(e)
            return True

    # todo: move back to generic implementation, as this code is not plugin-specific
    def delete_event_instance(self, instance: EventInstance,
                              days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        self.log(f'trying to delete {instance.root_event.id} instance: {instance.instance_id}')
        root_event = instance.root_event

        # remove from exceptions if necessary
        if instance.instance_id in root_event.subcomponents:
            root_event.subcomponents.pop(instance.instance_id)
        # create exdate
        exdate = datetime.datetime.strptime(instance.instance_id, '%Y%m%dT%H%M%SZ').replace(tzinfo=tzlocal())
        if root_event.exdates:
            root_event.exdates.append(exdate)
        else:
            root_event.exdates = [exdate]
        # update root event
        return self.update_event(root_event, days_in_future=days_in_future, days_in_past=days_in_past)

    def restore_excluded_date(self, root_event: Event, excluded_date: datetime.datetime,
                              days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        if excluded_date in root_event.exdates:
            root_event.exdates.remove(excluded_date)
            return self.update_event(root_event, days_in_future=days_in_future, days_in_past=days_in_past)

    def update_event(self, event: Event,
                     days_in_future: int, days_in_past: int,
                     moved_from_calendar: Union[Calendar, None] = None) -> Union[Event, List[EventInstance]]:
        try:

            if moved_from_calendar is not None:
                # create copy of event to move to new calendar
                # (original event, including old id, is still necessary for proper deletion)
                new_event = copy.deepcopy(event)
                # remove event id, will be re-generated before saving
                new_event.id = None
                for e in new_event.subcomponents.values():
                    e.id = None
            else:
                new_event = event

            # 1) 'update, or copy to new calendar'
            edited_event = CalDavConversions.caldav_event_from_event(
                new_event, self.caldav_calendars[event.calendar.id].caldav_cal)
            raw_edited_event = edited_event.save()
            self.caldav_calendars[event.calendar.id].register_update(raw_edited_event.url)

            if moved_from_calendar is not None:
                # 2) delete from old calendar
                ev_2_del = CalDavConversions.caldav_event_from_event(
                    event, self.caldav_calendars[moved_from_calendar.id].caldav_cal)
                ev_2_del.delete()
                self.caldav_calendars[moved_from_calendar.id].register_delete(ev_2_del)

            self.save_data()
            return CalDavConversions.expand_caldav_event(raw_edited_event, event, days_in_future, days_in_past)

        except caldav.error.NotFoundError as nfe:
            raise nfe
        except Exception as e:
            self.log_warn(e)
            if moved_from_calendar is not None:
                event.calendar = moved_from_calendar
            event.mark_desynchronized()
            return event

    def save_data(self):
        SettingsStorage.save(self.caldav_calendars, 'caldav_cals')

    @time_method
    def expand_events(self, start: datetime.datetime, end: datetime.datetime) -> \
            Dict[str, Union[Event, List[EventInstance]]]:

        event_list = {}

        for c_id, cal in self.caldav_calendars.items():
            event_list.update(CalDavConversions.expand_events(cal.events, cal.ical_events, start, end))
        return event_list
