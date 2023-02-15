from PyQt5.QtCore import Qt
from PyQt5.QtGui import QCloseEvent, QIcon, QPaintEvent, QPainter, QBrush, QColor
from PyQt5.QtWidgets import QMessageBox, QAbstractButton, QDialogButtonBox, QDialog, QWidget, QHBoxLayout, QVBoxLayout, \
    QToolButton, QLabel, QStyle, QSizePolicy, QLayout

from helpers import styles
from helpers.tools import PathManager
from widgets.tool_widgets.widget import Widget


class CustomWindow(Widget):
    def __init__(self, parent, flags):
        super().__init__(parent, flags=Qt.Window)
        self._title = ''
        self.setMinimumSize(100, 100)
        self.setStyleSheet(styles.get_style('darkblue'))
        self.setWindowFlag(Qt.FramelessWindowHint)
        self._central_widget = QWidget(self)
        self._central_layout = QHBoxLayout()
        self._central_layout.setContentsMargins(5, 5, 5, 5)
        self._layout = QVBoxLayout()
        self._title_bar = TitleBar(self, self._title, flags=flags)
        self._layout.addWidget(self._title_bar)
        self._layout.addLayout(self._central_layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._central_layout.addWidget(self._central_widget)
        super().setLayout(self._layout)

    def setWindowTitle(self, title: str) -> None:
        self._title_bar.setWindowTitle(title)

    def setWindowIcon(self, icon: QIcon) -> None:
        self._title_bar.set_icon(icon)

    def setLayout(self, layout: QLayout) -> None:
        self._central_widget.setLayout(layout)


class CustomMessageBox(QDialog):
    def __init__(self, *args):
        super().__init__()
        title = args[1]
        diag = InlineMessageBox(self, *args)
        self.setStyleSheet(styles.get_style('darkblue'))
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.central_layout = QHBoxLayout()
        self.central_layout.setContentsMargins(5, 5, 5, 5)
        self.old_lay = self.layout()
        self._layout = QVBoxLayout()
        self.title = TitleBar(self, title, flags=Qt.WindowCloseButtonHint)
        self._layout.addWidget(self.title)
        # self.setStyleSheet('QLabel{color:white;}')
        self._layout.addLayout(self.central_layout)
        # self._layout.addLayout(self.old_lay)
        self.setLayout(self._layout)
        self._layout.setContentsMargins(0, 0, 0, 0)
        # self._layout.addStretch(-1)
        self.central_layout.addWidget(diag)
        self.ret = 0

    def setWindowIcon(self, icon: QIcon) -> None:
        super().setWindowIcon(icon)
        self.title.set_icon(icon)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)  # QPen(QColor(255,255,255,190)))
        painter.setBrush(QBrush(QColor(30,30,30, 190)))
        painter.drawRect(0, self.title.height(), self.width(), self.height()-self.title.height())

    def exec(self) -> int:
        super().exec()
        return self.ret


"""
    https://github.com/chenzhutian/myClientPyQt/blob/master/titleBar.py#L100
"""


class TitleBar(Widget):
    maxNormal = False

    def __init__(self, parent: QWidget, title='NO TITLE', icon: QIcon = None,
                 flags: Qt.WindowFlags =
                 Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint | Qt.WindowCloseButtonHint
                 ):
        super().__init__(parent)
        self.iconLabel = QLabel(self)
        self.iconLabel.setAttribute(Qt.WA_TranslucentBackground)
        self.titleLabel = QLabel(self)
        if icon is not None:
            self.iconLabel.setPixmap(icon.scaled(20, 20))
        self.titleLabel.setText(title)
        self.titleLabel.setAttribute(Qt.WA_TranslucentBackground)

        self.h_box = QHBoxLayout(self)
        self.h_box.addWidget(self.iconLabel)
        self.h_box.addWidget(self.titleLabel)

        if flags is not None and flags & Qt.WindowMaximizeButtonHint:
            self.minimize = QToolButton(self)
            self.minimize.setIcon(QIcon(PathManager.get_icon_path('ui_minimize.png')))
            self.minimize.setMinimumHeight(20)
            self.minimize.clicked.connect(self.on_minimize_clicked)
            self.h_box.addWidget(self.minimize)
        if flags is not None and flags & Qt.WindowMaximizeButtonHint:
            self.maximize = QToolButton(self)
            self.maximize.setIcon(QIcon(PathManager.get_icon_path('ui_maximize.png')))
            self.maximize.setMinimumHeight(20)
            self.maximize.clicked.connect(self.on_maximize_clicked)
            self.h_box.addWidget(self.maximize)
        if flags is not None and flags & Qt.WindowCloseButtonHint:
            self.close = QToolButton(self)
            self.close.setIcon(QIcon(PathManager.get_icon_path('ui_close.png')))
            self.close.setMinimumHeight(20)
            self.close.clicked.connect(self.parent().close)
            self.h_box.addWidget(self.close)

        self.h_box.insertStretch(2, 500)
        self.h_box.setContentsMargins(2, 2, 2, 2)
        self.h_box.setSpacing(0)

        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setStyleSheet("QLabel{color:white ;font-size:12px;font-weight:bold;}")
        self.start_pos = None
        self.click_pos = None

    def setWindowTitle(self, title: str) -> None:
        self.titleLabel.setText(title)

    def on_minimize_clicked(self):
        self.parentWidget().showMinimized()

    def on_maximize_clicked(self):
        if self.maxNormal:
            self.parentWidget().showNormal()
            self.maxNormal = not self.maxNormal
            self.maximize.setIcon(self.maxPix)
        else:
            self.parentWidget().showMaximized()
            self.maxNormal = not self.maxNormal
            self.maximize.setIcon(self.restorePix)

    def set_icon(self, icon: QIcon):
        self.iconLabel.setPixmap(icon.pixmap(20,20))
        self.titleLabel.setStyleSheet("margin-left:3px;")

    def mousePressEvent(self, e):
        self.start_pos = e.globalPos()
        self.click_pos = self.mapToParent(e.pos())
        # self.clickPos = e.pos()

    def mouseMoveEvent(self, e):
        if self.maxNormal:
            return
        self.parentWidget().move(e.globalPos() - self.click_pos)
        # self.move(e.globalPos() - self.clickPos)

    # def mouseDoubleClickEvent(self, e):
    #     if (e.button() == Qt.LeftButton and e.y() <= self.height()):
    #         if not self.maxNormal:
    #             self.parentWidget().showMaximized()
    #             self.maxNormal = not self.maxNormal
    #             self.maximize.setIcon(self.restorePix)
    #         else:
    #             self.parentWidget().showNormal()
    #             self.maxNormal = not self.maxNormal
    #             self.maximize.setIcon(self.maxPix)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(20, 20, 20, 190)))
        painter.drawRect(self.rect())


class InlineMessageBox(QMessageBox):
    def __init__(self, parent, *args):
        super().__init__(*args)
        self.msg_box = parent
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlag(Qt.Widget)
        self.setStyleSheet('QPushButton::hover{background-color: rgb(50, 50, 230}')
        self.buttonClicked.connect(self.evaluate)
        for child in self.children():
            try:
                child.setAttribute(Qt.WA_TranslucentBackground)
            except AttributeError:
                pass

    def evaluate(self, clicked_button: QAbstractButton):
        button_role = self.findChild(QDialogButtonBox).buttonRole(clicked_button)
        if button_role == QMessageBox.YesRole:
            # print(self, 'YES')
            self.msg_box.ret = QMessageBox.Yes
        elif button_role == QMessageBox.NoRole:
            # print(self, 'NO')
            self.msg_box.ret = QMessageBox.No
        else:
            pass
            # print(self, button_role)
        self.msg_box.close()

    def closeEvent(self, event: QCloseEvent) -> None:
        # print('close event')
        self.msg_box.closeEvent(event)
        self.msg_box.close()
