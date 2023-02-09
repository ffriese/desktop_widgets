from collections import defaultdict
from datetime import datetime
from enum import Enum
from typing import List, Dict, Type, Any, Callable


class WeatherParameters(Enum):
    pass


class PrecipitationType(Enum):
    NONE = 'NONE'
    SNOW = 'SNOW'
    RAIN = 'RAIN'
    HAIL = 'HAIL'
    ICE_PELLETS = 'ICE_PELLETS'
    FREEZING_RAIN = 'FREEZING_RAIN'


class WeatherCode(Enum):
    FREEZING_RAIN_HEAVY = 'FREEZING_RAIN_HEAVY'
    FREEZING_RAIN = 'FREEZING_RAIN'
    FREEZING_RAIN_LIGHT = 'FREEZING_RAIN_LIGHT'
    FREEZING_DRIZZLE = 'FREEZING_DRIZZLE'
    ICE_PELLETS_HEAVY = 'ICE_PELLETS_HEAVY'
    ICE_PELLETS = 'ICE_PELLETS'
    ICE_PELLETS_LIGHT = 'ICE_PELLETS_LIGHT'
    SNOW_HEAVY = 'SNOW_HEAVY'
    SNOW = 'SNOW'
    SNOW_LIGHT = 'SNOW_LIGHT'
    FLURRIES = 'FLURRIES'
    THUNDERSTORM = 'THUNDERSTORM'
    RAIN_HEAVY = 'RAIN_HEAVY'
    RAIN = 'RAIN'
    RAIN_LIGHT = 'RAIN_LIGHT'
    DRIZZLE = 'DRIZZLE'
    FOG_LIGHT = 'FOG_LIGHT'
    FOG = 'FOG'
    CLOUDY = 'CLOUDY'
    MOSTLY_CLOUDY = 'MOSTLY_CLOUDY'
    PARTLY_CLOUDY = 'PARTLY_CLOUDY'
    MOSTLY_CLEAR = 'MOSTLY_CLEAR'
    CLEAR = 'CLEAR'


class WeatherDataType:
    _PREFIX_ = '__PARAM__'
    # _INTERPOLATION_ = defaultdict(lambda a, b: WeatherDataType._interpolate_std(a,b))

    def __init__(self, **params: Dict[str, Any]):
        for key, value in params.items():
            setattr(self, f'{self._PREFIX_}{key}', value)

    def _get_param(self, param: WeatherParameters, default=None):
        return getattr(self, f'{self._PREFIX_}{param.name}', {'value': default})

    def __repr__(self):
        data = {k.replace(self._PREFIX_, ""): v for k, v in self.__dict__.items() if k.startswith(self._PREFIX_)}
        return f'{self.__class__.__name__}({data}) '

    @staticmethod
    def _interpolate(w1: "WeatherDataType", w2: "WeatherDataType",
                     params: Dict[WeatherParameters, Callable[[Any, Any], Any]]):
        new_values = {k.name: {
            # 'units': w1._get_param(k)['units'],
            'value': v(w1._get_param(k)['value'], w2._get_param(k)['value'])
            } for k, v in params.items()}
        return w1.__class__(**new_values)

    @staticmethod
    def _interpolate_std(v1, v2):
        if v1 is not None and v2 is not None:
            return float(v1 + v2) / 2.0
        else:
            return None

    @classmethod
    def interpolate(cls, w1: "WeatherDataType", w2: "WeatherDataType") -> "WeatherDataType":
        raise NotImplementedError()
        # print(w1.__class__, cls._INTERPOLATION_)
        # interpolated = cls._interpolate(w1, w2, cls._INTERPOLATION_)
        # return interpolated


class Temperature(WeatherDataType):
    def get_temperature(self):
        return self._get_param(TemperatureParameters.TEMPERATURE)

    def get_feels_like(self):
        return self._get_param(TemperatureParameters.FEELS_LIKE)

    @classmethod
    def interpolate(cls, t1: "Temperature", t2: "Temperature") -> "Temperature":
        interpolated = cls._interpolate(t1, t2, {
            TemperatureParameters.TEMPERATURE: cls._interpolate_std,
            TemperatureParameters.FEELS_LIKE: cls._interpolate_std
        })
        return interpolated


class Precipitation(WeatherDataType):
    # def __init__(self, **params: Dict[str, Any]):
    #     super().__init__(**params)
    #     self._INTERPOLATION_[PrecipitationParameters.TYPE] = lambda p_1, p_2: p_1

    def get_probability(self):
        return self._get_param(PrecipitationParameters.PROBABILITY)

    def get_intensity(self):
        return self._get_param(PrecipitationParameters.INTENSITY, 0.0)

    def get_type(self):
        return self._get_param(PrecipitationParameters.TYPE)

    @classmethod
    def interpolate(cls, p1: "Precipitation", p2: "Precipitation") -> "Precipitation":
        interpolated = cls._interpolate(p1, p2, {
            PrecipitationParameters.PROBABILITY: cls._interpolate_std,
            PrecipitationParameters.INTENSITY: cls._interpolate_std,
            PrecipitationParameters.TYPE: lambda p_1, p_2: p_1
        })
        return interpolated


class Wind(WeatherDataType):
    def get_speed(self):
        return self._get_param(WindParameters.SPEED)

    def get_direction(self):
        return self._get_param(WindParameters.DIRECTION)

    def get_gust(self):
        return self._get_param(WindParameters.GUST)

    @classmethod
    def interpolate(cls, w1: "Wind", w2: "Wind") -> "Wind":
        interpolated = cls._interpolate(w1, w2, {
            WindParameters.SPEED: cls._interpolate_std,
            WindParameters.DIRECTION: cls._interpolate_std,
            WindParameters.GUST: cls._interpolate_std,
        })
        return interpolated


class Clouds(WeatherDataType):

    def get_cover(self):
        return self._get_param(CloudParameters.COVER)

    def get_ceiling(self):
        return self._get_param(CloudParameters.CEILING)

    @classmethod
    def interpolate(cls, c1: "Clouds", c2: "Clouds") -> "Clouds":
        interpolated = cls._interpolate(c1, c2, {
            CloudParameters.COVER: cls._interpolate_std,
            CloudParameters.CEILING: cls._interpolate_std
        })
        return interpolated


class SunTime(WeatherDataType):
    def get_sunset(self):
        return self._get_param(SunTimeParameters.SET)

    def get_sunrise(self):
        return self._get_param(SunTimeParameters.RISE)

    @classmethod
    def interpolate(cls, s1: "SunTime", s2: "SunTime") -> "SunTime":
        interpolated = cls._interpolate(s1, s2, {
            SunTimeParameters.SET: lambda p_1, p_2: p_1,
            SunTimeParameters.RISE: lambda p_1, p_2: p_1
        })
        return interpolated


class WeatherDescription(WeatherDataType):
    def get_code(self):
        return self._get_param(WeatherDescriptionParameters.CODE)

    @classmethod
    def interpolate(cls, w1: "WeatherDescription", w2: "WeatherDescription") -> "WeatherDescription":
        interpolated = cls._interpolate(w1, w2, {
            WeatherDescriptionParameters.CODE: lambda p_1, p_2: p_1
        })
        return interpolated


class TemperatureParameters(WeatherParameters):
    __OBJ_CLASS__ = Temperature
    TEMPERATURE = 'TEMPERATURE'
    FEELS_LIKE = 'TEMPERATURE_FEELS_LIKE'


class PrecipitationParameters(WeatherParameters):
    __OBJ_CLASS__ = Precipitation
    INTENSITY = 'PRECIPITATION_INTENSITY'
    PROBABILITY = 'PRECIPITATION_PROBABILITY'
    TYPE = 'PRECIPITATION_TYPE'


class WindParameters(WeatherParameters):
    __OBJ_CLASS__ = Wind
    DIRECTION = 'WIND_DIRECTION'
    SPEED = 'WIND_SPEED'
    GUST = 'WIND_GUST'


class CloudParameters(WeatherParameters):
    __OBJ_CLASS__ = Clouds
    BASE = 'CLOUD_BASE'
    COVER = 'CLOUD_COVER'
    CEILING = 'CEILING'


class SunTimeParameters(WeatherParameters):
    __OBJ_CLASS__ = SunTime
    RISE = 'SUNRISE'
    SET = 'SUNSET'
    HOURS = 'SUN_HOURS'


class WeatherDescriptionParameters(WeatherParameters):
    __OBJ_CLASS__ = WeatherDescription
    CODE = 'WEATHER_CODE'


class SingleReport:
    def __init__(self, timestamp: datetime, data: Dict[Type[WeatherDataType], WeatherDataType]):
        self.data = data
        self.timestamp = timestamp

    def __repr__(self):
        return f'{self.__class__.__name__}(ts: {self.timestamp}, data: {self.data})'
