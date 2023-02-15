
from PyQt5.QtCore import QSize
from PyQt5.QtGui import QFont, QResizeEvent, QIcon
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QGridLayout

from helpers.tools import PathManager
from plugins.weather.iconsets import IconSet
from plugins.weather.weather_data_types import WeatherDescription, WeatherCode, Temperature
from plugins.weather.weather_plugin import WeatherReport
from helpers.widget_helpers import TextLabel
from widgets.tool_widgets.widget import Widget
from helpers.viz_helper import TemperatureGradient


class DailyWeatherWidget(Widget):

    WEATHER_ICONS = {}

    def __init__(self):
        super(DailyWeatherWidget, self).__init__()
        self.start_date = None
        self.days = None
        self.setMaximumHeight(50)  # todo: better formula
        self.v_lay = QVBoxLayout()
        # self.setStyleSheet('background-color: rgba(255,80,80,80)')
        self.v_lay.setContentsMargins(0, 0, 0, 0)
        self.v_lay.setSpacing(0)
        self.loc_label = QLabel()
        self.loc_label.setFont(QFont('Calibri', 12))
        self.loc_label.setStyleSheet('QLabel{color: white;}')
        self.weather_grid = QWidget(self)
        # self.weather_grid.setStyleSheet('background-color: rgb(0, 200, 0, 200')
        self.weather_grid_layout = QGridLayout(self.weather_grid)
        self.weather_grid_layout.setContentsMargins(0, 0, 0, 0)
        self.weather_grid_layout.setSpacing(0)
        self.weather_grid.setLayout(self.weather_grid_layout)
        self.v_lay.addWidget(self.loc_label)
        self.v_lay.addWidget(self.weather_grid)
        self.setLayout(self.v_lay)
        self.daily_widgets = []

    @staticmethod
    def get_weather_icon(weather_code: WeatherCode):
        if weather_code is not None and weather_code not in DailyWeatherWidget.WEATHER_ICONS:
            DailyWeatherWidget.WEATHER_ICONS[weather_code] = DailyWeatherWidget.create_weather_icon(weather_code)
        return DailyWeatherWidget.WEATHER_ICONS.get(weather_code, QIcon())


    @staticmethod
    def create_weather_icon(weather_code: WeatherCode, icon_set=IconSet.WEATHER_UNDERGOUND):
        return QIcon(PathManager.get_weather_icon_set_path(
            icon_set['folder'],
             f"{icon_set['data'][weather_code]}.svg")).\
            pixmap(QSize(32, 32))

    def refresh(self, days, start_date):
        self.days = days
        self.start_date = start_date

    def resizeEvent(self, event: QResizeEvent) -> None:
        pass

    def set_weather(self, weather_data: WeatherReport):
        if weather_data is not None:
            self.loc_label.setText(weather_data.get_location_name())

            for i, w in enumerate(self.daily_widgets):
                self.weather_grid_layout.removeWidget(w)
                w.deleteLater()
                # self.log_warn(f'deleting widget {w}, {w.children()}')

            self.daily_widgets = [QWidget() for _ in range(self.days)]
            for date, report in weather_data.get_daily_report().items():
                offset = date.date() - self.start_date
                if 0 <= offset.days < self.days:
                    wid = self.daily_widgets[offset.days]
                    lay = QHBoxLayout()
                    lay.setContentsMargins(0, 0, 0, 0)
                    lay.setSpacing(0)
                    wid.setLayout(lay)

                    icon_lb = QLabel()
                    # icon_lb.setAlignment(Qt.AlignHCenter | Qt.AlignVCenter)
                    # self.log_warn(date, report.data[WeatherDescription].get_code()['value'],
                    #               report.data[Temperature].get_temperature()['value'], "°C", offset.days)
                    icon_lb.setPixmap(self.get_weather_icon(report.data[WeatherDescription].get_code()['value']))
                    icon_lb.setToolTip(report.data[WeatherDescription].get_code()['value'].name)
                    wid.layout().addWidget(icon_lb)
                    temperatures = report.data[Temperature].get_temperature()
                    try:
                        # temperature_text = f"{temperatures[0]['min']['value']:.0f}"\
                        #                    f"°{temperatures[0]['min']['units']} <br> "\
                        #                    f"{temperatures[1]['max']['value']:.0f}"\
                        #                    f"°{temperatures[1]['max']['units']}"
                        # t_lb = QLabel(self)
                        # t_lb.setText(f'<p style="color:#ffffff;background-color:#ff0000;'
                        #             f';display: inline;">{temperature_text}</p>')
                        #wid.layout().addWidget(t_lb)


                        vlay = QVBoxLayout(self)
                        vlay.setContentsMargins(0, 0, 0, 0)
                        vlay.setSpacing(0)
                        if type(temperatures) == dict:
                            temp = temperatures['value']
                            lb = TextLabel(f'{temp:.0f} °C', self,
                                           color=TemperatureGradient.get_color_for_temperature(temp))
                            vlay.addWidget(lb)
                        else:
                            min_temp = temperatures[0]['min']['value']
                            max_temp = temperatures[1]['max']['value']
                            lb1 = TextLabel(f"{min_temp:.0f}"
                                            f"°{temperatures[0]['min']['units']}", self,
                                            color=TemperatureGradient.get_color_for_temperature(min_temp))
                            lb2 = TextLabel(f"{max_temp:.0f}"
                                            f"°{temperatures[1]['max']['units']}", self,
                                            color=TemperatureGradient.get_color_for_temperature(max_temp))

                            vlay.addWidget(lb1)
                            vlay.addWidget(lb2)
                        wid.layout().addLayout(vlay)

                    except KeyError or IndexError as e:
                        self.log_warn(e)

                    # desc_lb = QLabel(f"{report.data[WeatherDescription].get_code()['value'].name}")
                    # desc_lb.setStyleSheet('color: white;')
                    # wid.layout().addWidget(desc_lb)
                    #self.daily_widgets[offset.days] = wid

            for i, w in enumerate(self.daily_widgets):
                self.weather_grid_layout.addWidget(w, 0, i)
