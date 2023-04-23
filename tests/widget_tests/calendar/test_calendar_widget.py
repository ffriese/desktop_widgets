import unittest
from collections import OrderedDict
from datetime import datetime, timedelta
from random import random
from typing import Union, List
from unittest.mock import MagicMock

from dateutil.tz import tzlocal

from plugins.calendarplugin.calendar_plugin import CalendarPlugin
from plugins.calendarplugin.data_model import Event, EventInstance, CalendarData, CalendarSyncException
from plugins.weather.weather_data_types import SingleReport, Temperature, WeatherDescription, Wind, WeatherCode, \
    Precipitation, PrecipitationType, SunTime
from plugins.weather.weather_plugin import WeatherPlugin, WeatherReport
from tests.plugin_tests.calendar.data_generator import CalendarPluginDataGenerator
from tests.helper import MockPlugin
from tests.widget_tests import base
from widgets import CalendarWidget


class MockWeatherPlugin(WeatherPlugin):

    def setup(self):
        pass

    def set_location(self, location):
        pass

    def _get_temp(self, ts):
        return SingleReport(timestamp=ts, data={
                Temperature: Temperature(FEELS_LIKE={'value': random()*30.0},
                                         TEMPERATURE={'value': random()*30.0}),
                WeatherDescription: WeatherDescription(CODE={'value': WeatherCode.CLEAR}),
                Wind: Wind(GUST={'value': random()*30.0}, SPEED={'value': random()*30.0}),
                Precipitation: Precipitation(TYPE={'value': PrecipitationType.RAIN},
                                             INTENSITY={'value': random()*2.0},
                                             PROBABILITY={'value': random()*100.0} ),
                SunTime: SunTime(RISE={'value': datetime.combine(ts.date(),
                                                                 datetime(hour=6+int(random()*3),
                                                                          minute=int(random()*60),
                                                                          day=ts.day,
                                                                          year=ts.year,
                                                                          month=ts.month,
                                                                          second=0).time()
                                                                 )},
                                 SET={'value': datetime.combine(ts.date(),
                                                                 datetime(hour=16 + int(random() * 5),
                                                                          minute=int(random() * 60),
                                                                          day=ts.day,
                                                                          year=ts.year,
                                                                          month=ts.month,
                                                                          second=0).time()
                                                                 )}

                                 )
            })

    def update_synchronously(self, *args, **kwargs) -> Union[WeatherReport, None]:
        now = datetime.now().replace(microsecond=0, second=0, minute=0).astimezone(tzlocal())
        report = WeatherReport(
            now=OrderedDict({now: self._get_temp(now)}),
            minutely=OrderedDict({ts: self._get_temp(ts) for ts in [now+timedelta(minutes=x) for x in range(120)]}),
            hourly=OrderedDict({ts: self._get_temp(ts) for ts in [now+timedelta(hours=x) for x in range(24*5)]}),
            daily=OrderedDict({ts: self._get_temp(ts) for ts in [now+timedelta(days=x) for x in range(8)]}),
            updated=datetime.now()
        )
        return report


class TestCalendarWidget(unittest.TestCase):
    app = base.papp

    def setUp(self) -> None:
        print('SET UP Multiday WIDGET')
        self.wid = CalendarWidget()
        self.wid.setStyleSheet('background-color:rgba(20,20,20,100)')
        self.wid.setWindowTitle("Test MultiDayWidget")
        size = (500, 700)
        self.wid.resize(*size)
        self.wid.view.refresh(self.wid.days, self.wid.start_date, self.wid.start_hour, self.wid.end_hour)
        self.plugin = MockPlugin('MOCKPLUGIN')
        self.plugin.delete_cache()
        self.wid.cal_plugin = self.plugin
        self.wid.check_notifications = lambda *args: None
        self.wid.register_plugin(MockWeatherPlugin, 'weather_plugin')
        self.wid.show()
        self.calendar = CalendarPluginDataGenerator.generate_calendar()
        self.wid.calendar_plugin_lookup[self.calendar.id] = self.plugin
        self.wid.calendar_data[self.plugin.__class__.__name__] = CalendarData(
            calendars={self.calendar.id: self.calendar}, events={},
            colors=self.plugin.get_event_colors())

    def tearDown(self) -> None:
        self.plugin.delete_cache()
        self.app.quit()

    def test_event_added(self):
        event = CalendarPluginDataGenerator.generate_event(calendar=self.calendar)
        self.wid.handle_new_event(event)

    def test_non_synced(self):

        self.plugin._create_synced_event = MagicMock(side_effect=CalendarSyncException())
        unsynced_event = CalendarPluginDataGenerator.\
            generate_event(title='Test Event', calendar=self.calendar)
        self.wid.handle_new_event(self.plugin.create_event(unsynced_event, days_in_past=0, days_in_future=5))
        self.wid.async_update_weather()
        if False:
            while self.wid.isVisible():
                base._processPendingEvents(self.app, 0.2)

