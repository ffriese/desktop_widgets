"""
gladly adapted from https://stackoverflow.com/a/59258957
authors:
 - musicamante https://stackoverflow.com/users/2001654/musicamante
 - Nav https://stackoverflow.com/users/453673/nav


"""


import sys

from PyQt5.QtGui import QFont, QPainterPath, QTransform, QRegion, QCursor
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QSizePolicy, QGraphicsOpacityEffect, QStyle, QApplication, QLabel, \
    QTableView, QPushButton, QComboBox, QLineEdit, QVBoxLayout, QToolButton
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QPropertyAnimation, QEvent, QPoint, QRectF, QRect, QSize


class QToaster(QWidget):
    closed = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super(QToaster, self).__init__(*args, **kwargs)
        QHBoxLayout(self)

        self.setSizePolicy(QSizePolicy.Maximum,
                           QSizePolicy.Maximum)

        self.setStyleSheet('''
            QToaster {
                border: 1px solid white;
                border-radius: 15px;
                background-color: red;
            }
        ''')
        # alternatively:
        # self.setAutoFillBackground(True)
        #self.setFrameShape(self.Box)
        self.setWindowFlags(Qt.WindowStaysOnTopHint)

        self.timer = QTimer(singleShot=True, timeout=self.hide)

        if self.parent():
            self.opacityEffect = QGraphicsOpacityEffect(opacity=0)
            self.setGraphicsEffect(self.opacityEffect)
            self.opacityAni = QPropertyAnimation(self.opacityEffect, b'opacity')
            # we have a parent, install an eventFilter so that when it's resized
            # the notification will be correctly moved to the right corner
            self.parent().installEventFilter(self)
        else:
            # there's no parent, use the window opacity property, assuming that
            # the window manager supports it; if it doesn't, this won'd do
            # anything (besides making the hiding a bit longer by half a second)
            self.opacityAni = QPropertyAnimation(self, b'windowOpacity')
        self.opacityAni.setStartValue(0.)
        self.opacityAni.setEndValue(0.9)
        self.opacityAni.setDuration(2000)
        self.opacityAni.finished.connect(self.checkClosed)

        self.corner = Qt.TopLeftCorner
        self.margin = 10

    def checkClosed(self):
        # if we have been fading out, we're closing the notification
        if self.opacityAni.direction() == self.opacityAni.Backward:
            self.close()

    def restore(self):
        # this is a "helper function", that can be called from mouseEnterEvent
        # and when the parent widget is resized. We will not close the
        # notification if the mouse is in or the parent is resized
        self.timer.stop()
        # also, stop the animation if it's fading out...
        self.opacityAni.stop()
        # ...and restore the opacity
        if self.parent():
            self.opacityEffect.setOpacity(1)
        else:
            self.setWindowOpacity(1)

    def hide(self):
        # start hiding
        self.opacityAni.setDirection(self.opacityAni.Backward)
        self.opacityAni.setDuration(2000)
        self.opacityAni.start()

    def eventFilter(self, source, event):
        if source == self.parent() and event.type() == QEvent.Resize:
            self.opacityAni.stop()
            parentRect = self.parent().rect()
            geo = self.geometry()
            if self.corner == Qt.TopLeftCorner:
                geo.moveTopLeft(
                    parentRect.topLeft() + QPoint(self.margin, self.margin))
            elif self.corner == Qt.TopRightCorner:
                geo.moveTopRight(
                    parentRect.topRight() + QPoint(-self.margin, self.margin))
            elif self.corner == Qt.BottomRightCorner:
                geo.moveBottomRight(
                    parentRect.bottomRight() + QPoint(-self.margin, -self.margin))
            else:
                geo.moveBottomLeft(
                    parentRect.bottomLeft() + QPoint(self.margin, -self.margin))
            self.setGeometry(geo)
            self.restore()
            self.timer.start()
        return super(QToaster, self).eventFilter(source, event)

    def enterEvent(self, event):
        self.restore()

    def leaveEvent(self, event):
        self.timer.start()

    def closeEvent(self, event):
        # we don't need the notification anymore, delete it!
        self.deleteLater()

    def resizeEvent(self, event):
        super(QToaster, self).resizeEvent(event)
        # if you don't set a stylesheet, you don't need any of the following!
        if not self.parent():
            # there's no parent, so we need to update the mask
            path = QPainterPath()
            path.addRoundedRect(QRectF(self.rect()).translated(-.5, -.5), 4, 4)
            self.setMask(QRegion(path.toFillPolygon(QTransform()).toPolygon()))
        else:
            self.clearMask()

    @staticmethod
    def showMessage(parent, message,
                    icon=QStyle.SP_MessageBoxInformation,
                    corner=Qt.TopLeftCorner, margin=10, closable=True,
                    timeout=5000, desktop=False, parentWindow=True):

        if parent and parentWindow:
            parent = parent.window()

        if not parent or desktop:
            self = QToaster(None)
            self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint |
                Qt.BypassWindowManagerHint)
            # This is a dirty hack!
            # parentless objects are garbage collected, so the widget will be
            # deleted as soon as the function that calls it returns, but if an
            # object is referenced to *any* other object it will not, at least
            # for PyQt (I didn't test it to a deeper level)
            self.__self = self

            currentScreen = QApplication.primaryScreen()
            if parent and parent.window().geometry().size().isValid():
                # the notification is to be shown on the desktop, but there is a
                # parent that is (theoretically) visible and mapped, we'll try to
                # use its geometry as a reference to guess which desktop shows
                # most of its area; if the parent is not a top level window, use
                # that as a reference
                reference = parent.window().geometry()
            else:
                # the parent has not been mapped yet, let's use the cursor as a
                # reference for the screen
                reference = QRect(
                    QCursor.pos() - QPoint(1, 1),
                    QSize(3, 3))
            maxArea = 0
            for screen in QApplication.screens():
                intersected = screen.geometry().intersected(reference)
                area = intersected.width() * intersected.height()
                if area > maxArea:
                    maxArea = area
                    currentScreen = screen
            parentRect = currentScreen.availableGeometry()
        else:
            self = QToaster(parent)
            parentRect = parent.rect()

        self.timer.setInterval(timeout)

        # use Qt standard icon pixmaps; see:
        # https://doc.qt.io/qt-5/qstyle.html#StandardPixmap-enum
        if isinstance(icon, QStyle.StandardPixmap):
            labelIcon = QLabel()
            self.layout().addWidget(labelIcon)
            icon = self.style().standardIcon(icon)
            size = self.style().pixelMetric(QStyle.PM_SmallIconSize)
            labelIcon.setPixmap(icon.pixmap(size))

        self.label = QLabel(message)
        self.label.setFont(QFont('Calibri', 20, 200))
        self.label.setStyleSheet('font-color: white; color:white')

        self.layout().addWidget(self.label)

        if closable:
            self.closeButton = QToolButton()
            self.layout().addWidget(self.closeButton)
            closeIcon = self.style().standardIcon(
                QStyle.SP_TitleBarCloseButton)
            self.closeButton.setIcon(closeIcon)
            self.closeButton.setAutoRaise(True)
            self.closeButton.clicked.connect(self.close)

        self.timer.start()

        # raise the widget and adjust its size to the minimum
        self.raise_()
        # self.adjustSize()

        self.corner = corner
        self.margin = margin

        geo = self.geometry()
        # now the widget should have the correct size hints, let's move it to the
        # right place
        if corner == Qt.TopLeftCorner:
            geo.moveTopLeft(
                parentRect.topLeft() + QPoint(margin, margin))
        elif corner == Qt.TopRightCorner:
            geo.moveTopRight(
                parentRect.topRight() + QPoint(-margin, margin))
        elif corner == Qt.BottomRightCorner:
            geo.moveBottomRight(
                parentRect.bottomRight() + QPoint(-margin, -margin))
        else:
            geo.moveBottomLeft(
                parentRect.bottomLeft() + QPoint(margin, -margin))

        self.setGeometry(geo)
        self.show()
        self.opacityAni.start()


class W(QWidget):
    def __init__(self):
        QWidget.__init__(self)
        layout = QVBoxLayout(self)

        toasterLayout = QHBoxLayout()
        layout.addLayout(toasterLayout)

        self.textEdit = QLineEdit('Ciao!')
        toasterLayout.addWidget(self.textEdit)

        self.cornerCombo = QComboBox()
        toasterLayout.addWidget(self.cornerCombo)
        for pos in ('TopLeft', 'TopRight', 'BottomRight', 'BottomLeft'):
            corner = getattr(Qt, '{}Corner'.format(pos))
            self.cornerCombo.addItem(pos, corner)

        self.windowBtn = QPushButton('Show window toaster')
        toasterLayout.addWidget(self.windowBtn)
        self.windowBtn.clicked.connect(self.showToaster)

        self.screenBtn = QPushButton('Show desktop toaster')
        toasterLayout.addWidget(self.screenBtn)
        self.screenBtn.clicked.connect(self.showToaster)

        # a random widget for the window
        layout.addWidget(QTableView())

    def showToaster(self):
        if self.sender() == self.windowBtn:
            parent = self
            desktop = False
        else:
            parent = None
            desktop = True
        corner = Qt.Corner(self.cornerCombo.currentData())
        QToaster.showMessage(
            parent, self.textEdit.text(), corner=corner, desktop=desktop)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = W()
    w.show()
    sys.exit(app.exec_())