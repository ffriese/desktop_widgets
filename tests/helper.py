import math
from typing import Dict, Union, List

from plugins.calendarplugin.calendar_plugin import CalendarPlugin
from plugins.calendarplugin.data_model import CalendarData, Event, EventInstance


def h_float_to_hms(h_float: float) -> Dict[str, int]:
    h = math.floor(h_float)
    m = math.floor((h_float - h) * 60.0)
    s = (((h_float - h) * 60.0) - m) * 60.0
    return {'hour': int(h), 'minute': int(m), 'second': int(s)}


class MockPlugin(CalendarPlugin):

    def update_synchronously(self,
                             days_in_future: int, days_in_past: int,
                             *args, **kwargs) -> Union[CalendarData, None]:
        pass

    def quit(self):
        pass

    def setup(self):
        pass

    def _create_synced_event(self, event: Event,
                             days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        event._synchronized = True
        event.data['synchronized'] = True
        return event

    def _delete_synced_event(self, event: Event) -> bool:
        event._synchronized = True
        event.data['synchronized'] = True
        return True

    def _update_synced_event(self, event: Event,
                             days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        event._synchronized = True
        event.data['synchronized'] = True
        return event