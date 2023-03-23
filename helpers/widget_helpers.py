import math
from urllib.parse import quote

import requests
from PyQt5.QtCore import QPointF, Qt, pyqtSignal, QRect, QPoint, QRectF
from PyQt5.QtGui import QPainterPath, QPainter, QFont, QFontMetrics, QBrush, QTextOption, QColor, QPaintEvent
from PyQt5.QtWidgets import QWidget, QSizePolicy

from helpers.tools import LRUCache


class ResizeHelper:
    @staticmethod
    def get_resize_section(geom: QRect, point: QPoint):
        def horizontal(_geom: QRect, _point: QPoint):
            if _geom.x() <= _point.x() <= _geom.x() + _geom.width() / 2:
                return Qt.LeftSection
            elif _geom.x() + _geom.width() / 2 < _point.x() <= _geom.x() + _geom.width():
                return Qt.RightSection
            raise ValueError('Point is not in Rectangle!')

        def vertical(_geom: QRect, _point: QPoint):
            if _geom.y() <= _point.y() <= _geom.y() + _geom.height() / 2:
                return Qt.TopSection
            elif _geom.y() + _geom.height() / 2 < _point.y() <= _geom.y() + _geom.height():
                return Qt.BottomSection
            raise ValueError('Point is not in Rectangle!')

        sections = {
            Qt.LeftSection: {
                Qt.BottomSection: Qt.BottomLeftSection,
                Qt.TopSection: Qt.TopLeftSection
            },
            Qt.RightSection: {
                Qt.BottomSection: Qt.BottomRightSection,
                Qt.TopSection: Qt.TopRightSection
            }
        }
        return sections[horizontal(geom, point)][vertical(geom, point)]


##################################################
#  Smooth Path, gladly adapted from              #
#  https://stackoverflow.com/questions/40764011  #
##################################################

class SmoothPath:

    @staticmethod
    def distance(pt1: QPointF, pt2: QPointF) -> float:

        hd = (pt1.x() - pt2.x()) * (pt1.x() - pt2.x())
        vd = (pt1.y() - pt2.y()) * (pt1.y() - pt2.y())
        return math.sqrt(hd + vd)

    @staticmethod
    def get_line_start(pt1: QPointF, pt2: QPointF) -> QPointF:
        rat = 10.0 / SmoothPath.distance(pt1, pt2)
        if rat > 0.5:
            rat = 0.5
        x = (1.0 - rat) * pt1.x() + rat * pt2.x()
        y = (1.0 - rat) * pt1.y() + rat * pt2.y()
        return QPointF(x, y)

    @staticmethod
    def get_line_end(pt1: QPointF, pt2: QPointF) -> QPointF:
        rat = 10.0 / SmoothPath.distance(pt1, pt2)
        if rat > 0.5:
            rat = 0.5

        x = rat * pt1.x() + (1.0 - rat)*pt2.x()
        y = rat * pt1.y() + (1.0 - rat)*pt2.y()
        return QPointF(x, y)

    @staticmethod
    def smooth_out(path: QPainterPath):
        points = []
        for i in range(path.elementCount()):
            p = QPointF(path.elementAt(i).x, path.elementAt(i).y)
            points.append(p)

        # Don't proceed if we only have 3 or fewer points.
        if len(points) < 3:
            return path
        path = QPainterPath()
        for i in range(len(points)-1):
            pt1 = SmoothPath.get_line_start(points[i], points[i + 1])
            if i == 0:
                path.moveTo(pt1)
            else:
                path.quadTo(points[i], pt1)

            pt2 = SmoothPath.get_line_end(points[i], points[i + 1])
            path.lineTo(pt2)
        return path

#############################################
#  SideGrip, gladly adapted from            #
#  https://stackoverflow.com/a/62812752     #
#############################################


class SideGrip(QWidget):
    resizing = pyqtSignal(object)
    resizing_end = pyqtSignal()
    resized = pyqtSignal(object)

    def __init__(self, parent, edge):
        QWidget.__init__(self, parent)
        self.has_been_resized = False
        if edge == Qt.LeftEdge:
            self.setCursor(Qt.SizeHorCursor)
            self.resizeFunc = self.resize_left
            self.setMaximumWidth(3)
        elif edge == Qt.TopEdge:
            self.setCursor(Qt.SizeVerCursor)
            self.resizeFunc = self.resize_top
            self.setMaximumHeight(3)
        elif edge == Qt.RightEdge:
            self.setCursor(Qt.SizeHorCursor)
            self.resizeFunc = self.resize_right
            self.setMaximumWidth(3)
        else:
            self.setCursor(Qt.SizeVerCursor)
            self.resizeFunc = self.resize_bottom
            self.setMaximumHeight(3)
        self.mousePos = None

    def resize_left(self, delta):
        width = max(10, self.parent().width() - delta.x())
        geo = self.parent().geometry()
        geo.setLeft(max((geo.right() - width), 0))
        self.parent().setGeometry(geo)
        self.has_been_resized = True

    def resize_top(self, delta):
        height = max(5, self.parent().height() - delta.y())
        geo = self.parent().geometry()
        geo.setTop(max(geo.bottom() - height, 0))
        self.parent().setGeometry(geo)
        self.has_been_resized = True

    def resize_right(self, delta):
        width = max(10, self.parent().width() + delta.x())
        width = min(self.parent().parent().width()-self.parent().x(), width)
        self.parent().resize(max(width, self.parent().minimumWidth()), self.parent().height())
        self.has_been_resized = True

    def resize_bottom(self, delta):
        height = max(5, self.parent().height() + delta.y())
        height = min(self.parent().parent().height()-self.parent().y(), height)
        self.parent().resize(self.parent().width(), max(height, self.parent().minimumHeight()))
        self.has_been_resized = True

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.mousePos = event.pos()
            self.resizing.emit(self.parent().geometry())

    def mouseMoveEvent(self, event):
        if self.mousePos is not None:
            delta = event.pos() - self.mousePos
            self.resizeFunc(delta)
            self.resizing.emit(self.parent().geometry())

    def mouseReleaseEvent(self, event):
        self.mousePos = None
        if self.has_been_resized:
            self.resized.emit(self.parent().geometry())
            self.has_been_resized = False
        else:
            self.resizing_end.emit()


class CalendarHelper:

    #############################################
    #  Scaling conflicting events in column,    #
    #  gladly adapted from                      #
    #  https://stackoverflow.com/a/62812752     #
    #############################################

    @classmethod
    def scale_events(cls, cal_events, col_width, col_height,
                     start_hour, end_hour,
                     direction=Qt.Vertical,
                     rect_func=None, col_rescale_func=None):
        # Based on algorithm described here: http://stackoverflow.com/questions/11311410
        columns = []
        last_event_ending = None
        events = sorted(cal_events, key=lambda x: (x.begin, x.end))
        # print([e.summary for e in events])
        for event in events:
            # Check if a new event group needs to be started
            if last_event_ending is not None and event.begin >= last_event_ending:
                # The latest event is later than any of the event in the
                #   current group. There is no overlap. Output the current
                #   event group and start a new event group.
                cls.pack_events(columns, col_width, col_height, start_hour, end_hour,
                                direction, rect_func, col_rescale_func)
                columns = []  # This starts new event group.
                last_event_ending = None
            # Try to place the event inside the existing columns
            placed = False
            for i in range(len(columns)):
                col = columns[i]
                if not cls.collides_with(col[-1], event):
                    col.append(event)
                    placed = True
                    break

            # It was not possible to place the event. Add a new column
            #  for the current event group.
            if not placed:
                columns.append([event])

            # Remember the latest event end time of the current group.
            #  This is later used to determine if a new group starts.
            if last_event_ending is None or event.end > last_event_ending:
                last_event_ending = event.end
        if len(columns) > 0:
            cls.pack_events(columns, col_width, col_height, start_hour, end_hour, direction,
                            rect_func, col_rescale_func)

    @classmethod
    def pack_events(cls, columns, col_width, col_height,
                    start_hour, end_hour,
                    direction, rect_func=None, col_rescale_func=None):
        number_of_columns = len(columns)
        hour_height = (col_height / (end_hour-start_hour))
        if col_rescale_func is not None:
            col_width, col_height = col_rescale_func(number_of_columns)
        for i in range(number_of_columns):
            current_column = columns[i]
            for j in range(len(current_column)):
                event = current_column[j]  # type: QWidget
                event_column_span = cls.expand_event(event, i, columns)
                if direction == Qt.Vertical:
                    left_offset_percentage = (i / number_of_columns)  # percent
                    width = col_width * event_column_span / number_of_columns-1
                    start_y = int(max(0, event.begin-start_hour) * hour_height)
                    event_height = min(int((event.end - max(event.begin, start_hour)) * hour_height), col_height - start_y)
                    event.setGeometry(int(col_width * left_offset_percentage),
                                      start_y,
                                      int(width),
                                      event_height
                                      # int((event.end - event.begin) * hour_height)
                                      )
                elif direction == Qt.Horizontal:
                    if rect_func is not None:
                        rect = rect_func(event)  # type: QRect
                        top_offset_percentage = (i / number_of_columns)
                        height = int(col_height * event_column_span / number_of_columns-1)
                        rect.setTop(int(col_height * top_offset_percentage + rect.top()))
                        rect.setHeight(height)
                        event.setGeometry(rect)

    @classmethod
    def collides_with(cls, a, b):
        return a.end > b.begin and a.begin < b.end

    @classmethod
    def expand_event(cls, event, col_idx, columns):
        event_column_span = 0
        for i in range(col_idx, len(columns)):
            current_column = columns[i]
            for j in range(len(current_column)):
                other_event = current_column[j]
                if other_event == event:
                    continue
                if cls.collides_with(event, other_event):
                    return event_column_span
            event_column_span += 1
        return event_column_span


class TextSizeHelper:
    cache = LRUCache(max_len=500)

    @staticmethod
    def draw_text_in_rect(painter: QPainter, text: str, rect: QRect, font: QFont, flags: int):
        key = f"{font.style()}_{font.rawName()}_{rect.width()}_{rect.height()}_{text}"
        if key in TextSizeHelper.cache.keys():
            point_size = TextSizeHelper.cache[key]
            font.setPointSizeF(point_size)
            painter.setFont(font)
        else:
            font_bound_rect = painter.fontMetrics().boundingRect(rect, flags, text)
            while rect.width() < font_bound_rect.width() or rect.height() < font_bound_rect.height():
                font.setPointSizeF(font.pointSizeF() * 0.95)
                painter.setFont(font)
                font_bound_rect = painter.fontMetrics().boundingRect(rect, flags, text)
            TextSizeHelper.cache[key] = font.pointSizeF()
        painter.drawText(rect, flags, text)

    @staticmethod
    def draw_text2(painter: QPainter, font: QFont, text: str, color: QColor, rect: QRectF,
                   align: Qt.Alignment = Qt.AlignLeft, angle=0.0):
        painter.save()
        painter.setFont(font)
        fm = QFontMetrics(painter.font())
        sx = rect.width() * 1.0 / fm.width(text)
        sy = rect.height() * 1.0 / fm.height()
        painter.setPen(color)
        painter.setBrush(QBrush(color))
        painter.translate(rect.center())
        sc = min(sx, sy)
        painter.scale(sc, sc)
        painter.translate(-rect.center())
        option = QTextOption()
        option.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
        option.setWrapMode(QTextOption.WordWrap)
        painter.drawText(rect, text, option)
        painter.restore()


class TextLabel(QWidget):
    def __init__(self, text: str, parent=None, font=None, color=Qt.white):
        super().__init__(parent)
        self.text = text
        self.font = font
        self.color = color
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def setFont(self, font: QFont):
        self.font = font

    def setColor(self, color: QColor):
        self.color = color

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        if self.font is None:
            self.font = painter.font()
        if self.color is None:
            self.color = painter.brush().color()

        # painter.setPen(Qt.red)
        # painter.setBrush(QBrush(Qt.red))
        # painter.drawRect(self.rect())

        painter.setPen(self.color)
        painter.setBrush(QBrush(self.color))
        # TextSizeHelper.draw_text_in_rect(painter, self.text, self.rect(), self.font, Qt.TextWordWrap)
        TextSizeHelper.draw_text2(painter, self.font, self.text, self.color, QRectF(self.rect()))


class MapImageHelper:
    __BASE64_MAP_IMAGES__ = {}

    @classmethod
    def get_map_image_base_64(cls, location_string, size=250, zoom=10):
        # return ""
        if location_string in cls.__BASE64_MAP_IMAGES__:
            return cls.__BASE64_MAP_IMAGES__[location_string]

        from credentials import MapQuestCredentials
        try:
            encoded = quote(location_string)
            response = requests.get(f"https://www.mapquestapi.com/staticmap/v5/map?key"
                                    f"={MapQuestCredentials.get_api_key()}"
                                    f"&center={encoded}"
                                    f"&size={size},{size}"
                                    f"&zoom={zoom}"
                                    f"&locations={encoded}",
                                    stream=True)
        except Exception as e:
            return
        if response.status_code == 200:

            import base64

            uri = ("data:" +
                   response.headers['Content-Type'] + ";" +
                   "base64," + base64.b64encode(response.content).decode("utf-8"))

            cls.__BASE64_MAP_IMAGES__[location_string] = f"<img src='{uri}'>"

        else:
            cls.__BASE64_MAP_IMAGES__[location_string] = ""

        return cls.__BASE64_MAP_IMAGES__[location_string]