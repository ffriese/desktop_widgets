import json
import random
import unittest

from PyQt5.QtCore import Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QMainWindow

from tests.widget_tests import base
from widgets.tool_widgets import LocationPicker
from widgets.tool_widgets.location_picker import LocWebPage


class TestLocationPicker(unittest.TestCase):
    app = base.papp

    @staticmethod
    def get_random_loc():
        return {
            'loc':
                    {
                        'lat': (random.random()*180.0)-90.0,
                        'long':  (random.random()*360.0)-180.0
                    }
                }

    def setUp(self) -> None:
        print('SET UP LOCATION PICKER')
        self.main = QMainWindow()
        self.location = self.get_random_loc()['loc']
        print(f'default loc set to {self.location}')
        # noinspection PyTypeChecker
        self.loc = LocationPicker(self.main, service_name='MapQuest',
                                  api_key='', #MapQuestCredentials.get_api_key(),
                                  location=self.location)
        self.loc.setWindowTitle("Test LocationPicker")
        self.loaded = False
        self.emitted_loc = None
        self.loc.location_picked.connect(self.accept_event)

    def tearDown(self) -> None:
        print('TEAR DOWN')
        self.main.close()

    def accept_event(self, loc):
        self.emitted_loc = loc
        print('Got', loc)

    def test_location_emit(self):
        QTest.mouseClick(self.loc.accept_button, Qt.LeftButton)
        self.assertEqual(self.emitted_loc, self.location, 'default location is emitted after submit-button-click')
        self.loc.show()
        inj = self.get_random_loc()
        print(f'injecting {inj["loc"]}')
        escaped_inj_str = json.dumps(inj).replace('"', '\\"')
        inj_js = f'console.log("{LocWebPage.UPDATE_PREFIX}{escaped_inj_str}")'
        self.loc.page.runJavaScript(inj_js)
        base._processPendingEvents(self.app, timeout=1.0)
        QTest.mouseClick(self.loc.accept_button, Qt.LeftButton)
        base._processPendingEvents(self.app, timeout=1.0)
        self.assertEqual(self.emitted_loc, inj['loc'], 'injected location is emitted after submit-button-click')

