
from PyQt5.QtCore import Qt, QPropertyAnimation, QRect, QEasingCurve, QPoint, pyqtSignal
from PyQt5.QtGui import QPaintEvent, QPainter, QColor, QPen, QCloseEvent
from PyQt5.QtWidgets import QMainWindow, QSystemTrayIcon, QVBoxLayout, QLabel, QFormLayout, QCheckBox, \
    QPushButton

from widgets.base import BaseWidget
from widgets.tool_widgets.dialogs.custom_dialog import CustomWindow


class OnboardingDialog(CustomWindow):

    widget_class_activated = pyqtSignal(object)

    tray_animation = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle('Welcome to Desktop Widgets')
        self.tray_icon = None
        self.layout = QVBoxLayout()
        self.layout.addWidget(QLabel('Would you like to activate some of these Widgets?'))
        self.form = QFormLayout()

        self.activate_button = QPushButton('Activate')
        self.activate_button.clicked.connect(self.activate_widgets)

        self.checkboxes = {}
        for widget_class in BaseWidget.__subclasses__():
            self.checkboxes[widget_class] = QCheckBox()
            self.form.addRow(widget_class.__name__, self.checkboxes[widget_class])

        self.layout.addLayout(self.form)
        self.layout.addWidget(self.activate_button)
        self.setLayout(self.layout)

    def activate_widgets(self):
        for widget_class, checkbox in self.checkboxes.items():
            if checkbox.isChecked():
                self.widget_class_activated.emit(widget_class)
        self.close()

    @classmethod
    def highlight_tray_icon(cls, tray_icon: QSystemTrayIcon, loop_count=5):

        tray_icon.showMessage('Activate your Widgets', 'Activate Widgets from the Tray-Icon')
        print('show highlight')
        # Get the position and size of the tray icon
        geometry = tray_icon.geometry()

        center = QPoint(int(geometry.x() + geometry.width() / 2), int(geometry.y() + geometry.height() / 2))
        sides = max(geometry.width(), geometry.height())
        x = int(center.x() - sides / 2)
        y = int(center.y() - sides / 2)
        if cls.tray_animation:
            cls.tray_animation.stop()
        cls.tray_animation = TrayIconAnimation(x, y, sides, sides, loop_count=loop_count)

    def closeEvent(self, close_event: QCloseEvent) -> None:
        self.tray_animation.animation.stop()
        self.tray_animation.deleteLater()
        super().closeEvent(close_event)


class TrayIconAnimation(QMainWindow):

    def __init__(self, x, y, width, height, loop_count=-1, duration=2000):
        super().__init__(None, Qt.WindowStaysOnTopHint)
        # Create a transparent window on top of the tray icon
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setGeometry(x, y, width, height)

        # Create an animated ellipse inside the transparent window
        self.animation = QPropertyAnimation(self, b'geometry')
        self.animation.setDuration(duration)
        self.animation.setLoopCount(loop_count)
        self.animation.setStartValue(QRect(x, y, width, height))
        self.animation.setEndValue(QRect(x + 10, y + 10, width - 20, height - 20))
        self.animation.setEasingCurve(QEasingCurve.OutQuad)
        self.animation.start()
        self.animation.finished.connect(self.close)

        self.show()

    def paintEvent(self, paintEvent: QPaintEvent) -> None:
        painter = QPainter(self)
        pen = QPen(QColor(255, 0, 0))
        pen.setWidth(2)
        painter.setPen(pen)

        painter.drawEllipse(self.rect())

