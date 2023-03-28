import datetime
import logging
import re
import uuid
from typing import List, Union, Dict, Tuple

from dateutil.tz import tzlocal
from tzlocal import get_localzone
import caldav
import icalendar
import pytz

import recurring_ical_events
import vobject
from PyQt5.QtGui import QColor
from dateutil import rrule
from vobject.icalendar import RecurringComponent

from plugins.calendarplugin.calendar_plugin import Event, Calendar, Alarm, CalendarAccessRole, Todo, EventInstance


class MockVobjectInstance:
    def __init__(self, vevents: List[RecurringComponent]):
        self.contents = {
            'vevent': vevents
        }


class CalDavObjectUpdate:
    def __init__(self, updates, deletes):
        self.updates = updates
        self.deletes = deletes

    def __str__(self):
        return f'new: {self.updates}, del: {self.deletes}'


class CalDavConversions:
    PERCENT_COMPLETE = 'percent-complete'
    CATEGORIES = 'categories'
    DTSTART = 'dtstart'
    DTEND = 'dtend'
    UID = 'uid'
    SUMMARY = 'summary'
    LOCATION = 'location'
    DESCRIPTION = 'description'
    RRULE = 'rrule'
    RECURRENCE_ID = 'recurrence-id'
    EXDATE = 'exdate'
    VALARM = 'valarm'
    ACTION = 'action'
    TRIGGER = 'trigger'
    COLOR = 'ffcolor'

    icalendar_import_fields = {
        'cal_name': ['X-WR-CALNAME'],
        'cal_id': ['X-WR-RELCALID'],
        'cal_desc': ['X-WR-CALDESC']
    }

    @classmethod
    def calendar_from_cal_dav_cal(cls, cal: caldav.Calendar) -> Calendar:
        cal_id = str(cal.url)
        props = cal.get_properties([caldav.dav.DisplayName(),
                                    caldav.elements.ical.CalendarColor(),
                                    caldav.elements.cdav.CalendarDescription()])
        cal_name = props[caldav.dav.DisplayName().tag]
        cal_color = props[caldav.elements.ical.CalendarColor().tag][:7]
        primary = props[caldav.elements.cdav.CalendarDescription().tag] == 'primary'
        return Calendar(calendar_id=cal_id, name=cal_name,
                        primary=primary,
                        fg_color=QColor('#ffffff'),
                        bg_color=QColor(cal_color),
                        access_role=CalendarAccessRole.OWNER,
                        data={'url': str(cal.url)}
                        )

    @classmethod
    def ical_from_iev(cls, evs: List[icalendar.Event]) -> icalendar.Calendar:
        c = icalendar.Calendar()
        for ev in evs:
            c.add_component(ev)
        return c

    @classmethod
    def caldav_event_from_event(cls, event: Event, caldav_calendar: caldav.Calendar):
        return cls.ical_event_objects_to_caldav_event(cls.ical_object_list_from_event(event), caldav_calendar)

    @classmethod
    def ical_event_objects_to_caldav_event(cls,
                                           event_objects: List[icalendar.Event],
                                           calendar: caldav.Calendar) -> caldav.Event:
        return caldav.Event(calendar.client, data=cls.ical_from_iev(event_objects),
                            url=calendar.canonical_url + event_objects[0].get('UID') + '.ics',
                            parent=calendar, id=event_objects[0].get('UID'))

    @classmethod
    def ical_object_list_from_event(cls, event: Event) -> List[icalendar.Event]:
        components = [cls.single_ical_event_from_event(event)]
        for sub in event.subcomponents.values():
            components.append(cls.single_ical_event_from_event(sub))
        return components

    @classmethod
    def single_ical_event_from_event(cls, event: Event) -> icalendar.Event:

        ical = icalendar.Event()
        local_tz = pytz.timezone(event.timezone) if event.timezone else get_localzone()
        ical.add(cls.UID, event.id if event.id is not None else str(uuid.uuid1()))
        ical.add(cls.DTSTART, event.start.astimezone(local_tz) if not event.all_day else event.start.date())
        ical.add(cls.DTEND, event.end.astimezone(local_tz) if not event.all_day else event.end.date())
        ical.add(cls.SUMMARY, event.title)
        if event.bg_color is not None:
            ical.add(cls.COLOR, event.bg_color.name())
        ical.add(cls.LOCATION, event.location)
        ical.add(cls.DESCRIPTION, event.description)
        if event.alarm:
            alarm = icalendar.Alarm()
            alarm.add(cls.ACTION, event.alarm.action)
            if event.alarm.description:
                alarm.add(cls.DESCRIPTION, event.alarm.description)
            alarm.add(cls.TRIGGER, event.alarm.trigger)
            alarm.get(cls.TRIGGER).params = icalendar.Parameters()  # weird compat issues
            ical.add_component(alarm)
        if event.recurrence:
            rec_str = re.sub('.*\n?RRULE:', '', str(event.recurrence))
            ical.add(cls.RRULE, icalendar.vRecur.from_ical(rec_str))
            if event.exdates:
                for exdate in event.exdates:
                    ical.add(cls.EXDATE, exdate.astimezone(local_tz))
        if event.recurring_event_id:
            ical.add(cls.RECURRENCE_ID,
                     datetime.datetime.strptime(event.recurring_event_id, '%Y%m%dT%H%M%SZ').astimezone(local_tz))
        return ical

    @classmethod
    def event_from_vobject_instance(cls, vobject_instance: vobject, calendar: Calendar) -> Event:
        vevent_list: List[RecurringComponent] = vobject_instance.contents['vevent']
        if isinstance(vevent_list, list):
            root_components = [vev for vev in vevent_list if cls.RECURRENCE_ID not in vev.contents]
            sub_components = [vev for vev in vevent_list if cls.RECURRENCE_ID in vev.contents]
            if not root_components:
                logging.log(level=logging.WARN,
                            msg=f'POTENTIALLY ERRONEOUS EVENT FOUND. NO COMPONENTS WITHOUT RECURRENCE ID!'
                                f' -> REMOVING REC-ID FROM FIRST "SUB"-COMPONENT. '
                                f' MAY PRODUCE UNPREDICTABLE ERRORS!')
                assert sub_components
                root_component = sub_components.pop(0)
                root_component.contents.pop(cls.RECURRENCE_ID)
            else:
                root_component = root_components[0]
            return CalDavConversions.event_from_recurring_component(
                root_component, calendar, rruleset=root_component.rruleset,
                subcomponents={
                    sub.contents[cls.RECURRENCE_ID][0].value.strftime('%Y%m%dT%H%M%SZ'):
                        CalDavConversions.event_from_recurring_component(
                            sub, calendar,
                            recurrence_id=sub.contents[cls.RECURRENCE_ID][0].value.strftime('%Y%m%dT%H%M%SZ'))
                    for sub in sub_components})
        else:
            return CalDavConversions.event_from_recurring_component(vobject_instance.vevent, calendar,
                                                                    vobject_instance.vevent.rruleset)

    @classmethod
    def event_from_recurring_component(cls, ev: RecurringComponent, calendar: Calendar,
                                       recurrence_id: str = None, rruleset: rrule.rruleset = None,
                                       subcomponents: Dict[str, Event] = None) -> Event:

        all_day = not isinstance(ev.dtstart.value, datetime.datetime)
        start = ev.dtstart.value if not all_day else datetime.datetime.combine(ev.dtstart.value,
                                                                               datetime.datetime.min.time())
        if hasattr(ev, 'dtend'):
            end = ev.dtend.value if not all_day else datetime.datetime.combine(ev.dtend.value,
                                                                               datetime.datetime.min.time())
        elif all_day:
            end = start
        else:
            print(f'WEIRD: {ev} has no dtend, but is not all-day.... DEFAULTING TO 1 HOUR DURATION!')
            end = start + datetime.timedelta(hours=1)

        alarm = None
        if cls.VALARM in ev.contents:
            valarm = ev.valarm
            trigger = valarm.trigger.value
            action = valarm.action.value
            desc = valarm.description.value if hasattr(valarm, 'description') else None
            alarmtime = start.astimezone(tzlocal()) + trigger
            alarm = Alarm(alarmtime, trigger, desc, action)
            # self.log(f'{trigger}, {alarmtime} {action}, {desc}')

        recurrence = None
        exdates = None
        if rruleset is not None:
            recurrence = rrule.rrulestr(str(rruleset._rrule[0]))
            exdates = [datetime.datetime(year=dt.year, month=dt.month, day=dt.day,
                                         hour=dt.hour, minute=dt.minute, second=dt.second) for dt in rruleset._exdate]
        return Event(event_id=ev.uid.value if cls.UID in ev.contents else '',
                     title=ev.summary.value if cls.SUMMARY in ev.contents else '',
                     start=start.astimezone(tzlocal()),
                     end=end.astimezone(tzlocal()),
                     description=ev.description.value if cls.DESCRIPTION in ev.contents else '',
                     location=ev.location.value if cls.LOCATION in ev.contents else '',
                     all_day=all_day,
                     calendar=calendar,
                     fg_color=None,
                     bg_color=QColor(ev.ffcolor.value) if cls.COLOR in ev.contents else None,
                     data={'id': ev.uid.value, 'synchronized': True},
                     timezone=None,
                     recurring_event_id=recurrence_id,
                     recurrence=recurrence,
                     exdates=exdates,
                     subcomponents=subcomponents,
                     synchronized=True,
                     alarm=alarm
                     )

    @classmethod
    def expand_ical_event(cls, ical_event: icalendar.Event, start, end):
        time_instances = recurring_ical_events.of(ical_event) \
            .between(start, end)
        return time_instances

    @classmethod
    def expand_event(cls, event: Event, ical_event: icalendar.Event, start, end) -> List[EventInstance]:
        return [EventInstance(root_event=event,
                              instance=cls.
                              event_from_recurring_component(
                                  vobject.readOne(instance.to_ical().decode()),
                                  recurrence_id=instance.get('RECURRENCE-ID').
                                      dt.strftime('%Y%m%dT%H%M%SZ') if instance.get('RECURRENCE-ID')
                                  else instance.get('DTSTART').
                                      dt.strftime('%Y%m%dT%H%M%SZ'),
                                  calendar=event.calendar)
                              ) for instance in cls.expand_ical_event(ical_event, start, end)]

    @classmethod
    def expand_events(cls, event_dict, ical_event_dict, start: datetime.datetime, end: datetime.datetime) -> \
            Dict[str, Union[Event, List[EventInstance]]]:
        event_list = {}
        for e_id, ev in event_dict.items():

            if ev.recurrence:
                instances = CalDavConversions.expand_event(ev, ical_event_dict[e_id], start, end)
                if instances:
                    event_list[e_id] = instances
            else:
                try:
                    if ev.start < end and ev.end > start:
                        event_list[e_id] = ev
                except TypeError as e:
                    print(ev.start, end, ev.end, start, e)
        return event_list


    @classmethod
    def expand_caldav_event(cls, raw_event: caldav.Event, event: Event,
                            days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        expandable_event = raw_event.vobject_instance.vevent
        if expandable_event.rruleset:
            root_event = cls.event_from_vobject_instance(raw_event.vobject_instance, event.calendar)
            return cls.expand_event(root_event, raw_event.icalendar_instance,
                                    start=datetime.datetime.now().replace(tzinfo=tzlocal()) -
                                    datetime.timedelta(days=days_in_past),
                                    end=datetime.datetime.now().replace(tzinfo=tzlocal()) +
                                    datetime.timedelta(days=days_in_future))
        else:
            return cls.event_from_recurring_component(expandable_event, event.calendar)

    @classmethod
    def load_all_from_ical_text(cls, ical_string: str, uri: str, calendar_id: str = None,
                                calendar_name: str = None, fg_color=None, bg_color=None) -> Tuple[Calendar,
                                                                                           Dict[str, Event],
                                                                                           Dict[str, icalendar.Calendar]]:
        cal = icalendar.Calendar.from_ical(ical_string)
        cal_data = {
            'cal_name': 'Calendar',
            'cal_id': calendar_id if calendar_id else uri
        }
        for field, accessors in cls.icalendar_import_fields.items():
            for accessor in accessors:
                if cal.get(accessor):
                    cal_data[field] = cal.get(accessor)
                    break

        calendar = Calendar(
            name=calendar_name if calendar_name else cal_data['cal_name'],
            calendar_id=cal_data['cal_id'],
            access_role=CalendarAccessRole.READER,
            fg_color=fg_color if fg_color else QColor(255, 255, 255),
            bg_color=bg_color if bg_color else QColor('#7986cb'),
            data={},
        )

        vevents = {}
        events = {}
        ical_events = {}
        for comp in vobject.readComponents(ical_string):
            for comp2 in comp.components():
                if isinstance(comp2, RecurringComponent):
                    if comp2.uid.value not in vevents:
                        vevents[comp2.uid.value] = []
                    vevents[comp2.uid.value].append(comp2)

        for uid, components in vevents.items():
            event = CalDavConversions.event_from_vobject_instance(MockVobjectInstance(components), calendar)
            ical = icalendar.Calendar()
            for e in [icalendar.Event.from_ical(c.serialize()) for c in components]:
                ical.add_component(e)

            events[uid] = event
            ical_events[uid] = ical

        return calendar, events, ical_events


    @classmethod
    def todo_from_vtodo(cls, td: RecurringComponent, calendar: Calendar) -> Todo:

        if hasattr(td, cls.DTSTART) and td.dtstart:
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
            if cls.VALARM in td.contents:
                alarm = td.valarm
                trigger = alarm.trigger.value
                action = alarm.action.value
                desc = alarm.description.value
                alarmtime = due.astimezone(tzlocal()) + trigger
                # self.log(f'TODO-ALARM: {trigger}, {alarmtime} {action}, {desc}')
        else:
            due = None

        return Todo(todo_id=td.uid.value if cls.UID in td.contents else '',
                    title=td.summary.value if cls.SUMMARY in td.contents else '',
                    start=start.astimezone(tzlocal()) if start else
                    None,
                    due=due.astimezone(tzlocal()) if due else None,
                    description=td.description.value if cls.DESCRIPTION in td.contents else '',
                    location=td.location.value if cls.LOCATION in td.contents else '',
                    categories=[c for c in td.categories.value] if cls.CATEGORIES in td.contents else [],
                    percent_complete=td.percent_complete.value if cls.PERCENT_COMPLETE in td.contents else 0,
                    all_day=all_day,
                    calendar=calendar,
                    fg_color=None,
                    bg_color=QColor(td.ffcolor.value) if cls.COLOR in td.contents else None,
                    data={'id': td.uid.value, 'synchronized': True},
                    timezone=None,
                    recurring_event_id=None,
                    recurrence=None,
                    synchronized=True
                    )
