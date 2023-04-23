import unittest
from datetime import datetime, timedelta

import dateutil.rrule

from plugins.calendarplugin.caldav.conversions import CalDavConversions
from tests.plugin_tests.calendar.data_generator import CalendarPluginDataGenerator
from tests.widget_tests import base
from tests.helper import h_float_to_hms
from widgets.calendar.multi_day_view import MultiDayView


class TestMultiDayWidget(unittest.TestCase):
    app = base.papp

    def setUp(self) -> None:
        print('SET UP Multiday WIDGET')
        self.m_wid = MultiDayView()
        self.m_wid.setStyleSheet('background-color:black')
        self.m_wid.setWindowTitle("Test MultiDayWidget")
        size = (500, 700)
        self.m_wid.resize(*size)
        self.m_wid.refresh(5, datetime.now().date(), 0, 24)
        self.m_wid.show()

    def tearDown(self) -> None:
        self.app.quit()

    def test_event_added(self):
        today = datetime.now()
        ranges = [(0, 23), (1.25, 14.34), (4, 20), (20, 21)]
        for ev_range in ranges:
            event = CalendarPluginDataGenerator.generate_event(
                    start=today.replace(**h_float_to_hms(ev_range[0])),
                    end=today.replace(**h_float_to_hms(ev_range[1]))
                )
            self.m_wid.add_event(event)
            base._processPendingEvents(self.app, 0.2)
        self.assertEqual(sum([len(w.cal_events) for w in self.m_wid.day_widgets]), len(ranges))

        self.m_wid.add_event(CalendarPluginDataGenerator.generate_event(title='NEWLY GEN',
                                                                        start=today+timedelta(days=1)))

    def test_repeat(self):

        self.assertEqual(sum([len(w.cal_events) for w in self.m_wid.day_widgets]), 0)
        today = datetime.now().replace(microsecond=0, second=0)
        repeat = CalendarPluginDataGenerator.generate_event(title="repeat",
                                                            start=today+timedelta(days=2))
        count = 3
        repeat.recurrence = dateutil.rrule.rrule(count=count, freq=dateutil.rrule.DAILY)
        ical_list = CalDavConversions.ical_object_list_from_event(repeat)
        ical_object = CalDavConversions.ical_from_iev(ical_list)
        events = CalDavConversions.expand_event(repeat, ical_object, today.date(), today.date()+timedelta(days=5))
        self.assertEqual(len(events), count)
        for ev in events:
            self.m_wid.add_event(ev)

        self.assertEqual(sum([len(w.cal_events) for w in self.m_wid.day_widgets]), 3)
        # if False:
        #     while self.m_wid.isVisible():
        #         base._processPendingEvents(self.app, 0.2)

