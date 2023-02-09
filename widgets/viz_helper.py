from PyQt5.QtCore import QRect, QPointF, Qt
from PyQt5.QtGui import QPainterPath, QPainter, QBrush, QLinearGradient, QPen, QColor

from plugins.weather.weather_data_types import WeatherDataType, Precipitation, Temperature, PrecipitationType
from widgets.helper import SmoothPath


class ValueVisualization:

    def __init__(self, display_hour_start: int, display_hour_end: int):
        self.displayed_hours = display_hour_end - display_hour_start
        self.path = QPainterPath()
        self.range = (0, 1)

    def add_data_point(self, data_point: WeatherDataType, rect: QRect, y):
        raise NotImplementedError()

    def complete_path(self, painter: QPainter, rect: QRect):
        raise NotImplementedError()

    def scaled(self, value, x_offset, width):
        try:
            value_perc = value / (self.range[1] - self.range[0])
            scaled = (value_perc * width) + x_offset
            # print(f'scaling {value} to range {self.range} -> {value_perc}')
            return scaled
        except TypeError:
            return 0.0


class PrecipitationVisualization(ValueVisualization):
    def __init__(self, display_hour_start: int, display_hour_end: int):
        super().__init__(display_hour_start, display_hour_end)
        self.brush_data_points = []
        self.range = (0, 3.0)

    def get_brush(self, y_offset, height) -> QBrush:
        if self.brush_data_points:
            color = self.brush_data_points[0].color
            gradient = QLinearGradient(QPointF(0, y_offset), QPointF(0, y_offset + height))
            gradient.setColorAt(0, color)
            for brush_data in self.brush_data_points:
                percentage = (brush_data.y - y_offset) / height
                gradient.setColorAt(percentage, brush_data.color)
            color = self.brush_data_points[-1].color
            gradient.setColorAt(1, color)
            return QBrush(gradient)
        else:
            return Qt.NoBrush

    def get_path(self) -> QPainterPath:
        return self.path

    def add_data_point(self, data_point: Precipitation, rect: QRect, y):
        x = self.scaled(data_point.get_intensity()['value'], rect.x(), rect.width())
        point = QPointF(x, y)
        if data_point.get_probability()['value'] is not None:
            self.brush_data_points.append(BrushDataPoint.from_precipitation(data_point, y))
        if self.path.elementCount() == 0:
            self._start_path(point)
        else:
            self.path.lineTo(point)

    def add_brush_data_point(self):
        raise NotImplementedError()

    def _start_path(self, point: QPointF):
        self.path.moveTo(point)

    def complete_path(self, painter: QPainter, rect: QRect):
        if self.path.elementCount() < 1:
            return

        # if in last hour -> close day completely up to border, otherwise cut at last data-point
        if ((rect.y()+rect.height()) - self.path.elementAt(self.path.elementCount() - 1).y) < \
                (float(rect.height())/self.displayed_hours):
            # bottom right corner
            self.path.lineTo(QPointF(
                self.path.elementAt(self.path.elementCount() - 1).x,
                rect.y() +
                rect.height()))
            # bottom left corner
            self.path.lineTo(QPointF(rect.x()+1,
                                     rect.y() + rect.height()))
            self.path.lineTo(QPointF(rect.x(),
                                     rect.y() + rect.height()))
            self.path.lineTo(QPointF(rect.x(),
                                     rect.y() + rect.height()-1))
        else:
            # bottom left corner
            self.path.lineTo(QPointF(
                rect.x()+1,
                self.path.elementAt(self.path.elementCount() - 1).y
            ))
            self.path.lineTo(QPointF(
                rect.x(),
                self.path.elementAt(self.path.elementCount() - 1).y
            ))
            self.path.lineTo(QPointF(
                rect.x(),
                self.path.elementAt(self.path.elementCount() - 1).y-1
            ))
        # top left corner
        self.path.lineTo(QPointF(rect.x(),
                                 rect.y()))
        # top right corner
        self.path.lineTo(QPointF(rect.x(),
                                 self.path.elementAt(0).y))
        # close path
        self.path.lineTo(QPointF(self.path.elementAt(0).x,
                                 self.path.elementAt(0).y))
        # self.path.closeSubpath()
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.get_brush(rect.y(), rect.height()))
        painter.drawPath(SmoothPath.smooth_out(self.path))
        self.path = QPainterPath()
        self.brush_data_points.clear()


class TemperatureVisualization(ValueVisualization):
    def __init__(self, display_hour_start: int, display_hour_end: int):
        super().__init__(display_hour_start, display_hour_end)
        self.range = (-10, 30)

    def get_pen(self, x_offset, width) -> QPen:
        temp_grad = TemperatureGradient(QPointF(x_offset, 50),
                                        QPointF(x_offset + width, 50),
                                        self.range[0],
                                        self.range[1])
        return QPen(QBrush(temp_grad), 2)

    def get_path(self) -> QPainterPath:
        return self.path

    def add_data_point(self, data_point: Temperature, rect: QRect, y):
        x = self.scaled(data_point.get_temperature()['value'], rect.x(), rect.width())
        point = QPointF(x, y)
        if self.path.elementCount() == 0:
            self.start_path(point, rect)
        else:
            self.path.lineTo(point)

    def add_brush_data_point(self):
        raise NotImplementedError()

    def start_path(self, point: QPointF, rect: QRect):
        if abs(point.y() - rect.y()) < float(rect.height())/self.displayed_hours:
            self.path.moveTo(QPointF(
                point.x(),
                rect.y()
            ))
            self.path.lineTo(point)
        else:
            self.path.moveTo(point)

    def complete_path(self, painter: QPainter, rect: QRect):
        if self.path.elementCount() < 1:
            return
        # if in last hour -> close day completely up to border, otherwise cut at last data-point
        if ((rect.y()+rect.height()) - self.path.elementAt(self.path.elementCount() - 1).y) < \
                (float(rect.height())/self.displayed_hours):
            self.path.lineTo(QPointF(
                self.path.elementAt(self.path.elementCount() - 1).x,
                rect.y() +
                rect.height()))
        else:
            self.path.lineTo(QPointF(
                self.path.elementAt(self.path.elementCount() - 1).x,
                self.path.elementAt(self.path.elementCount() - 1).y+1
            ))

        painter.setPen(self.get_pen(rect.x(), rect.width()))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(SmoothPath.smooth_out(self.path))
        self.path = QPainterPath()


class BrushDataPoint:
    def __init__(self, color, y):
        self.color = color
        self.y = y

    @classmethod
    def from_type(cls, weather_data: WeatherDataType, y) -> "BrushDataPoint":
        if type(weather_data) == Precipitation:
            # noinspection PyTypeChecker
            return cls.from_precipitation(weather_data, y)
        return cls(QColor(255, 255, 255, 255), y)

    @classmethod
    def from_precipitation(cls, precipitation: Precipitation, y) -> "BrushDataPoint":
        color = cls.precipitation_type_to_color(precipitation.get_type()['value'])
        transparency = (precipitation.get_probability()['value'] / 100.0) * 255.0
        color.setAlpha(transparency)
        return BrushDataPoint(color, y)

    @staticmethod
    def precipitation_type_to_color(precipitation_type: PrecipitationType):
        return {
            PrecipitationType.NONE: QColor(3, 98, 252, 255),
            PrecipitationType.RAIN: QColor(3, 98, 252, 255),
            PrecipitationType.SNOW: QColor(255, 255, 252, 255),
            PrecipitationType.ICE_PELLETS: QColor(50, 198, 252, 255),
            PrecipitationType.FREEZING_RAIN: QColor(103, 0, 252, 255)
        }[precipitation_type]


class TemperatureGradient(QLinearGradient):
    TEMP_COLORS = {
        -20: QColor(103, 62, 241),  # deep blue
        0: QColor(79, 135, 240),  # cyan1
        8: QColor(69, 170, 243),  # cyan2
        13: QColor(8, 230, 242),  # light green
        18: QColor(127, 244, 2),  # greenish
        22: QColor(215, 235, 0),  # yellow
        27: QColor(244, 170, 0),  # orange
        30: QColor(241, 87, 18),  # deep red
        40: QColor(247, 1, 113)   # pink
    }

    def __init__(self, start_point, end_point, min_temp=0, max_temp=40):
        super().__init__(start_point, end_point)
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.re_init()

    def re_init(self):
        self.setColorAt(0.0, self.TEMP_COLORS[min(self.TEMP_COLORS.keys())])
        self.setColorAt(1.0, self.TEMP_COLORS[max(self.TEMP_COLORS.keys())])
        for temp, color in self.TEMP_COLORS.items():
            if self.min_temp <= temp <= self.max_temp:
                percentage = temp / (self.max_temp - self.min_temp)
                self.setColorAt(percentage, color)

    @staticmethod
    def get_color_for_temperature(temp: float):
        temp = int(temp)
        min_temp = min(TemperatureGradient.TEMP_COLORS.keys())
        max_temp = max(TemperatureGradient.TEMP_COLORS.keys())
        for t, color in TemperatureGradient.TEMP_COLORS.items():
            if temp >= t > min_temp:
                min_temp = t
            if temp <= t < max_temp:
                max_temp = t
        diff = max_temp - min_temp
        if diff == 0:
            return TemperatureGradient.TEMP_COLORS[min_temp]
        perc = (temp-min_temp) / diff
        min_col = TemperatureGradient.TEMP_COLORS[min_temp]
        max_col = TemperatureGradient.TEMP_COLORS[max_temp]

        def interpolate(low, high, percentage: float):
            rng = high-low
            return (percentage * rng) + low

        return QColor(*[interpolate(getattr(min_col, c)(), getattr(max_col, c)(), perc)
                        for c in ['red', 'green', 'blue']])
