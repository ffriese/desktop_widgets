import json
import logging
from json.decoder import JSONDecodeError

from PyQt5.QtCore import pyqtSignal, Qt, QUrl, QUrlQuery
from PyQt5.QtGui import QIcon, QKeyEvent
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWidgets import QPushButton, QVBoxLayout

from helpers import styles
from widgets.base import BaseWidget
from widgets.helper import PathManager
from widgets.tool_widgets.dialogs.custom_dialog import CustomWindow


class LocationPicker(CustomWindow):

    location_picked = pyqtSignal(dict)

    def __init__(self, parent: BaseWidget, service_name: str, api_key: str, location=None, city=None):
        # noinspection PyTypeChecker
        super().__init__(parent=parent, flags=Qt.WindowCloseButtonHint)
        self.service_name = service_name
        self.log_info(api_key)
        self.api_key = api_key
        self.web_view = QWebEngineView()
        self.setStyleSheet(styles.get_style('darkblue'))
        self.setWindowTitle('Pick Location')
        self.setWindowIcon(QIcon(PathManager.get_icon_path('weather_location.png')))
        self.accept_button = QPushButton('Select New Location')
        self.accept_button.clicked.connect(self.accepted)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.addWidget(self.web_view)
        self.layout.addWidget(self.accept_button)
        self.initialized = False

        self.loc = location if location is not None else {}
        self.city = city
        self.page = LocWebPage(self.loc)
        self.web_view.setPage(self.page)

        # def loaded():
        #     print('i am initialized')
        #     self.initialized = True
        #     # self.web_view.page().runJavaScript(f"console.log('page loaded \"{self.web_view.page().url().url()}\"')")

        # self.web_view.page().loadFinished.connect(loaded)
        if service_name == 'MapQuest':
            self.url = QUrl.fromLocalFile(PathManager.get_html_path('mapquest.html'))
        else:
            self.url = QUrl.fromLocalFile(PathManager.get_html_path('geocode.html'))
        # print(self.url)

        self.query = QUrlQuery()
        if self.city:
            self.query.addQueryItem('city', self.city)
        for key in ['lat', 'long']:
            if key in self.loc.keys():
                self.query.addQueryItem(key, str(self.loc[key]))
        self.query.addQueryItem('apiKey', self.api_key)
        self.url.setQuery(self.query)
        self.web_view.page().load(self.url)
        self.web_view.setFocus()
        self.resize(500, 500)

    def accepted(self):
        self.location_picked.emit(self.page.get_loc())
        self.close()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in [Qt.Key_Enter, Qt.Key_Return]:
            self.accepted()
        else:
            pass
            # print(event.key())


class LocWebPage(QWebEnginePage):
    UPDATE_PREFIX = '__DATA_UPDATE__'

    def __init__(self, loc: dict):
        super(LocWebPage, self).__init__()
        self.loc = loc

    def get_loc(self):
        # print('GETTING LOC', self.loc)
        return self.loc

    def javaScriptConsoleMessage(self, level: int, msg: str, p_int: int, cur_url: str):
        if msg.startswith(self.UPDATE_PREFIX):
            try:
                data = json.loads(msg.replace(self.UPDATE_PREFIX, ''))
                for key, value in data.items():
                    setattr(self, key, value)
                    # print(f'{self} updated {key}: {getattr(self, key)}')

            except JSONDecodeError:
                logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg=msg)
        else:
            logging.getLogger(self.__class__.__name__).log(level=logging.ERROR, msg=msg)

    def javaScriptAlert(self, url: QUrl, message: str):
        # print(url.path(), url.url(), self.__dict__)
        super().javaScriptAlert(url, message)
