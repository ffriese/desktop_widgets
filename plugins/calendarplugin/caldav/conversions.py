import datetime
import re
import uuid

import caldav
import icalendar
import pytz
from PyQt5.QtCore import QTimeZone
from PyQt5.QtGui import QColor
from dateutil import rrule
from vobject.icalendar import RecurringComponent

from plugins.calendarplugin.calendar_plugin import Event, Calendar, Alarm, CalendarAccessRole, Todo


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
    VALARM = 'valarm'
    COLOR = 'ffcolor'




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
    def ical_from_iev(cls, ev: icalendar.Event) -> icalendar.Calendar:
        c = icalendar.Calendar()
        c.add_component(ev)
        return c

    @classmethod
    def ical_to_caldav_event(cls, client: caldav.DAVClient,
                             event: icalendar.Event,
                             calendar: caldav.Calendar) -> caldav.Event:
        return caldav.Event(client, data=cls.ical_from_iev(event),
                            url=calendar.canonical_url + event.get('UID') + '.ics',
                            parent=calendar, id=event.get('UID'))

    @classmethod
    def ical_event_from_event(cls, event: Event) -> icalendar.Event:

        ical = icalendar.Event()
        ical.add(cls.UID, event.id if event.id is not None else str(uuid.uuid1()))
        ical.add(cls.DTSTART, event.start if not event.all_day else event.start.date())
        ical.add(cls.DTEND, event.end if not event.all_day else event.end.date())
        ical.add(cls.SUMMARY, event.title)
        if event.bg_color is not None:
            ical.add(cls.COLOR, event.bg_color.name())
        ical.add(cls.LOCATION, event.location)
        ical.add(cls.DESCRIPTION, event.description)
        if event.recurrence:
            rec_str = re.sub('.*\n?RRULE:', '', str(event.recurrence))
            ical.add(cls.RRULE, icalendar.vRecur.from_ical(rec_str))
        return ical

    @classmethod
    def event_from_vevent(cls, ev: RecurringComponent, calendar: Calendar,
                          recurrence_id: str = None, rruleset: rrule.rruleset = None) -> Event:

        all_day = not isinstance(ev.dtstart.value, datetime.datetime)
        start = ev.dtstart.value if not all_day else datetime.datetime.combine(ev.dtstart.value,
                                                                               datetime.datetime.min.time())
        end = ev.dtend.value if not all_day else datetime.datetime.combine(ev.dtend.value,
                                                                           datetime.datetime.min.time())

        alarm = None
        if cls.VALARM in ev.contents:
            valarm = ev.valarm
            trigger = valarm.trigger.value
            action = valarm.action.value
            desc = valarm.description.value
            alarmtime = start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) + trigger
            alarm = Alarm(alarmtime, trigger, desc, action)
            # self.log(f'{trigger}, {alarmtime} {action}, {desc}')

        recurrence = None
        if recurrence_id is not None:
            recurrence = rrule.rrulestr(str(rruleset._rrule[0]))
        return Event(event_id=ev.uid.value if cls.UID in ev.contents else '',
                     title=ev.summary.value if cls.SUMMARY in ev.contents else '',
                     start=start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())),
                     end=end.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())),
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
                     synchronized=True,
                     alarm=alarm
                     )

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
                alarmtime = due.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) + trigger
                # self.log(f'TODO-ALARM: {trigger}, {alarmtime} {action}, {desc}')
        else:
            due = None

        return Todo(todo_id=td.uid.value if cls.UID in td.contents else '',
                    title=td.summary.value if cls.SUMMARY in td.contents else '',
                    start=start.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) if start else
                    None,
                    due=due.astimezone(pytz.timezone(QTimeZone.systemTimeZoneId().data().decode())) if due else None,
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
