import unittest
from datetime import datetime

from PyQt5.QtWidgets import QMainWindow

from tests.plugin_tests.calendar.data_generator import CalendarPluginDataGenerator
from tests.widget_tests import base
from tests.helper import h_float_to_hms
from widgets.calendar.day_widget import DayWidget


class TestTimelineWidget(unittest.TestCase):
    app = base.papp

    def setUp(self) -> None:
        print('SET UP DAY WIDGET')
        self.main = QMainWindow()
        self.wid = DayWidget(datetime.now().date(), 0, 24)
        self.wid.setWindowTitle("Test DayWidget")
        size = (500, 700)
        self.wid.resize(*size)
        self.wid.show()

    def tearDown(self) -> None:
        self.main.close()

    def test_event_added(self):
        self.assertEqual(self.wid.cal_events.values().__len__(), 0)
        for ev_range in [(0, 23), (1.25, 14.34), (4, 20), (20, 21)]:
            today = datetime.now()
            event = CalendarPluginDataGenerator.generate_event(
                start=today.replace(**h_float_to_hms(ev_range[0])),
                end=today.replace(**h_float_to_hms(ev_range[1]))
            )
            frac_of_day = (ev_range[1]-ev_range[0]) / 24.0
            print(f'testing event {ev_range}')
            self.wid.add_event(event, begin=ev_range[0],
                               end=ev_range[1])
            base._processPendingEvents(self.app, 0.2)
            self.assertEqual(self.wid.cal_events.values().__len__(), 1)
            self.assertAlmostEqual(self.wid.cal_events[event.id].width(), self.wid.width(), delta=1)
            self.assertAlmostEqual(self.wid.cal_events[event.id].height(), self.wid.height()*frac_of_day,
                                   delta=1)
            self.wid.remove_event(event.id)
            print('removing event')
            self.wid.repaint()
            base._processPendingEvents(self.app, 0.2)
