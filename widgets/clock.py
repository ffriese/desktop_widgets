from widgets.base import BaseWidget
from PyQt5.QtGui import QPen, QPainter, QColor, QFont, QFontMetrics, QResizeEvent
from PyQt5.QtCore import QTime, QRect
from PyQt5.QtWidgets import QApplication


class ClockWidget(BaseWidget):
    def __init__(self):
        super(ClockWidget, self).__init__()
        self.background_color = QColor(255, 0, 0, 190)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.repaint)
        self.timer.start()
        self.color_pick_action.setText('Select Color')
        self.point_size = 1
        self.draw_border = False
        self.font_rect = QRect(0, 0, 0, 0)

        self.font_picker.currentFontChanged.connect(self.preview_font)

    def start(self):
        super(ClockWidget, self).start()
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def moveEvent(self, event):
        super(ClockWidget, self).moveEvent(event)
        self.draw_border = True

    def resizeEvent(self, event):
        super(ClockWidget, self).resizeEvent(event)
        self.draw_border = True
        font = self.fg_font
        font.setPointSize(self.point_size)
        font.setBold(True)
        fm = QFontMetrics(font)
        time_str = '88:88'
        margin = self.border_margin

        rect = QRect(margin, margin, self.width() - (margin * 2), self.height() - (margin * 2))
        font_rect = fm.tightBoundingRect(time_str)
        self.font_rect = QRect(7, 7, font_rect.width() + abs(font_rect.x()), font_rect.height())
        while self.font_rect.width() < rect.width() and self.font_rect.height() <= rect.height():
            font.setPointSize(font.pointSize() + 1)
            fm = QFontMetrics(font)
            font_rect = fm.tightBoundingRect(time_str)
            self.font_rect = QRect(7, 7, font_rect.width() + abs(font_rect.x()), font_rect.height())
            # self.debug('%r | %r <-> %r' % (font_rect, self.font_rect, rect))
            # self.debug('pointsize: %d, fw: %d, rw: %d' % (font.pointSize(), font_rect.width(), rect.width()))
        while self.font_rect.width() > rect.width() or self.font_rect.height() > rect.height():
            font.setPointSize(font.pointSize() - 1)
            fm = QFontMetrics(font)
            font_rect = fm.tightBoundingRect(time_str)
            self.font_rect = QRect(7, 7, font_rect.width() + abs(font_rect.x()), font_rect.height())
            # self.debug('%r | %r <-> %r' % (font_rect, self.font_rect, rect))
        self.point_size = font.pointSize()
        # self.debug('set pointsize to %d' % font.pointSize())

    def font_changed(self):
        QApplication.sendEvent(self, QResizeEvent(self.size(), self.size()))

    def preview_font(self, font):
        self.log('Preview: %r' % font)

    def paintEvent(self, event):
        painter = QPainter(self)
        pen = QPen(self.background_color)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(0, 0, 0, 0))
        margin = self.border_margin
        font = self.fg_font
        font.setPointSize(self.point_size)
        font.setBold(True)
        painter.setFont(font)
        time_str = QTime.currentTime().toString()
        time_str = time_str[:-3]
        rect = QRect(margin, margin, self.width()-(margin*2), self.height()-(margin*2))
        if self.draw_border:
            painter.drawRect(rect)
            self.draw_border = False
        painter.drawText(margin+(rect.width()-self.font_rect.width())/2,
                         margin+rect.height()-(rect.height()-self.font_rect.height())/2,
                         time_str)
