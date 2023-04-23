from typing import Dict, List

import caldav
from PyQt5.QtGui import QColor
from caldav import CalendarObjectResource
from urllib3.exceptions import NewConnectionError

from plugins.calendarplugin.caldav.conversions import CalDavConversions, CalDavObjectUpdate
from plugins.calendarplugin.data_model import CalendarAccessRole, Calendar, Event


class CalDavCalendar:
    def __init__(self, cal: caldav.Calendar):
        self.caldav_cal = cal
        self.calendar = None
        self.sync_objects = None
        self.properties = {}
        self.events: Dict[str, Event] = {}
        self.ical_events: Dict[str, any] = {}

    def id(self):
        return str(self.caldav_cal.url)

    def add_objects_from_collection(self, objects):
        for caldav_object in objects:
            try:
                if caldav_object and caldav_object.vobject_instance:
                    if hasattr(caldav_object.vobject_instance, 'vevent'):  # check if event
                        # AT THIS POINT, WE DO NOT YET EXPAND OCCURRENCES, ONLY CREATE A SERIALIZABLE EVENT OBJECT
                        event = CalDavConversions.event_from_vobject_instance(caldav_object.vobject_instance,
                                                                              self.calendar)
                        self.events[event.id] = event
                        self.ical_events[event.id] = caldav_object.icalendar_instance
                    elif hasattr(caldav_object.vobject_instance, 'vtodo'):
                        print(f'GOT TODO: {caldav_object.vobject_instance.vtodo.summary.value}, discard for now')
                    elif hasattr(caldav_object.vobject_instance, 'vjournal'):
                        print(f'GOT JOURNAL: {caldav_object.vobject_instance.vjournal.summary.value}, discard for now')
                    else:
                        print(f'GOT VOBJECT: {caldav_object.vobject_instance}, discard for now')
                else:
                    # apparently we have no way to remove these orphaned objects from the server.
                    # just ignore them....
                    pass

            except AttributeError as e:
                print(f'{caldav_object} is weird: {caldav_object.vobject_instance} {e}')
                raise e

    def register_update(self, url):
        if self.sync_objects:
            self.sync_objects._objects_by_url[url] = CalendarObjectResource(url=url, client=self.caldav_cal.client)
            self.sync_objects._objects_by_url[url].load()
            self.add_objects_from_collection([self.sync_objects._objects_by_url[url]])

            self.sanitize_objects(from_dict=True)

    def register_delete(self, event):
        if self.sync_objects:
            self.sync_objects._objects_by_url.pop(event.url, None)
            ## TODO: CHECK IF THIS WORKS OUT FOR MOVED EVENTS!!!!!
            self.events.pop(event.id, None)
            self.ical_events.pop(event.id, None)
            self.sanitize_objects(from_dict=True)

    def sanitize_objects(self, from_dict=False):
        if not from_dict:
            # create dict first
            self.sync_objects._objects_by_url = {o.url: o for o in self.sync_objects}

        # make sure objects is a list, and not `dict.values`. necessary for pickle.dump
        self.sync_objects.objects = list(self.sync_objects._objects_by_url.values())

    def sync_metadata(self) -> CalDavObjectUpdate:
        try:
            if self.sync_objects is None:
                self.sync_objects = self.caldav_cal.objects(load_objects=False)
                self.sanitize_objects()
                print(f'self.objects: {type(self.sync_objects)}')
                events = self.caldav_cal.calendar_multiget([o.url for o in self.sync_objects.objects])
                # print(events)
                self.add_objects_from_collection(events)

                return CalDavObjectUpdate(self.sync_objects, [])
            else:
                ret = self.sync_objects.sync()
                self.sanitize_objects()
                print('sync done')
                updates = CalDavObjectUpdate(*ret)
                updated_events = self.caldav_cal.calendar_multiget([o.url for o in updates.updates])
                self.add_objects_from_collection(updated_events)
                for cd_event in updates.deletes:

                    print(f'GOT DELETE {cd_event}')
                    try:
                        uid = cd_event.url.path.replace(self.caldav_cal.url.path, '').replace('.ics', '')
                        self.events.pop(uid, None)
                        self.ical_events.pop(uid, None)
                        print(f'successfully deleted {uid}')
                    except AttributeError as e:
                        print(f'{cd_event} is weird: {cd_event.vobject_instance} {e}')
        except NewConnectionError as e:
            print(e)
        except ConnectionError as ce:
            print(ce)

    def fetch_properties(self):
        props = {"name": caldav.dav.DisplayName(),
                 "color": caldav.elements.ical.CalendarColor(),
                 "description": caldav.elements.cdav.CalendarDescription()
                 }
        print(f'fetching properties for {self.id()}')
        properties = self.caldav_cal.get_properties(props.values())
        self.properties = {name: properties[prop.tag] for name, prop in props.items()}
        print(f'{self.properties}')
        self.calendar = Calendar(calendar_id=self.id(), name=self.properties['name'],
                                 primary=self.properties['name'] == 'primary',
                                 fg_color=QColor('#ffffff'),
                                 bg_color=QColor(self.properties['color'][:7]),
                                 access_role=CalendarAccessRole.OWNER,
                                 data={'url': str(self.caldav_cal.url)}
                                 )