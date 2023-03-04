import uuid
from datetime import datetime, timedelta

from PyQt5.QtGui import QColor

from plugins.calendarplugin.calendar_plugin import Event, Calendar, CalendarAccessRole


class CalendarPluginDataGenerator:

    @staticmethod
    def generate_event(**kwargs) -> Event:
        start = kwargs.get('start', datetime.now())
        return Event(title='bla',
                     event_id=str(uuid.uuid4()),
                     start=start,
                     end=kwargs.get('end', start + timedelta(hours=2)),
                     location='Here',
                     description='this and that',
                     all_day=False,
                     calendar=CalendarPluginDataGenerator.generate_calendar(),
                     data={}
                     )

    @staticmethod
    def generate_calendar() -> Calendar:
        return Calendar(calendar_id=str(uuid.uuid4()),
                        name='Some Calendar',
                        access_role=CalendarAccessRole.OWNER,
                        fg_color=QColor(255, 255, 255),
                        bg_color=QColor(50, 150, 50),
                        data={})
