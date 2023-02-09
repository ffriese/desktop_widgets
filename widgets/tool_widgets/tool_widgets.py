from PyQt5.QtCore import QUrl
from PyQt5.QtGui import QIcon
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEnginePage
from PyQt5.QtWidgets import QWidget, QVBoxLayout

from widgets.base import BaseWidget

from widgets.helper import PathManager
from widgets.tool_widgets.widget import Widget


class WebPage(QWebEnginePage):
    # adblocker = Filter(open('easylist.txt', encoding="utf8"))

    def __init__(self, *args):

        super().__init__(*args)
        self.profile().clearHttpCache()
        self.profile().clearAllVisitedLinks()

        # self.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:82.0) "
        #                                 "Gecko/20100101 Firefox/82.0")
        # self.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        #                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
        #                                 "Chrome/86.0.4240.193 Safari/537.36")
        # self.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        #                                 "AppleWebKit/537.36 (KHTML, like Gecko) "
        #                                 "Chrome/86.0.4240.193 Safari/537.36")
        self.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; WOW64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/80.0.3987.163 Safari/537.36")
        self.profile().setHttpUserAgent("Mozilla/5.0 (Windows NT 10.0; WOW64) "
                                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                                        "Chrome/80.0.3987.163 Safari/537.36")

        self.featurePermissionRequestCanceled.connect(self.feature_permission_request_cancelled)
        self.featurePermissionRequested.connect(self.feature_permission_requested)

    def feature_permission_requested(self, url: QUrl, feature: QWebEnginePage.Feature):
        print('FEATURE REQUEST:', url, feature)
        self.setFeaturePermission(url, feature, QWebEnginePage.PermissionGrantedByUser)

    def feature_permission_request_cancelled(self, url: QUrl, feature: QWebEnginePage.Feature):
        print('request canceled', url, feature)

    # def featurePermissionRequested(self, url: QUrl, feature: QWebEnginePage.Feature):
    #     print('REQUEST:', url, feature)
    #
    # def setFeaturePermission(self, url: QUrl,
    # feature: QWebEnginePage.Feature, policy: QWebEnginePage.PermissionPolicy):
    #     print(url, feature, policy)

    # def acceptNavigationRequest(self, url, request_type, is_main_frame):
    #     # url_string = url.toString()
    #     # resp = False
    #     resp = WebPage.adblocker.match(url.toString())
    #
    #     if resp:
    #         print("Blocking url --- " + url.toString())
    #         return False
    #
    #     return QWebEnginePage.acceptNavigationRequest(self, url, request_type, is_main_frame)

    def javaScriptConsoleMessage(self, level: int, msg: str, p_int: int, cur_url: str):
        print('JAVASCRIPT: ', msg)


