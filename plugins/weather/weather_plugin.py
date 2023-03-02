import copy
import logging
import bisect
from datetime import datetime, timedelta
from typing import Union
try:
    from typing import OrderedDict
except ImportError:
    from typing import MutableMapping
    OrderedDict = MutableMapping
from collections import OrderedDict as OrdDict

from dateutil.tz import tzlocal

from plugins.base import BasePlugin
from plugins.weather.weather_data_types import SingleReport


class DailyWeather:
    def __init__(self):
        self.measures = {}


class WeatherReport:
    def __init__(self,
                 now: OrderedDict[datetime, SingleReport] = None,
                 minutely: OrderedDict[datetime, SingleReport] = None,
                 hourly: OrderedDict[datetime, SingleReport] = None,
                 daily: OrderedDict[datetime, SingleReport] = None,
                 location: str = None,
                 updated: datetime = None):
        self._now = now if now else {}
        self._minutely = minutely if minutely else {}
        self._hourly = hourly if hourly else {}
        self._daily = daily if daily else {}
        self._location = location
        self._merged = None
        self._updated = updated

    def get_location_name(self) -> str:
        return self._location

    def get_merged_report(self) -> OrderedDict[datetime, SingleReport]:
        if self._merged is None:
            self._merged = self._merge(self._minutely, self._hourly)
        return self._merged

    def get_daily_report(self) -> OrderedDict[datetime, SingleReport]:
        return self._daily

    def _merge(self, minutely: OrderedDict[datetime, SingleReport], hourly: OrderedDict[datetime, SingleReport]):
        times = copy.deepcopy(minutely)
        interpolated_hours = []
        for i, report in enumerate(hourly.values()):
            report.timestamp += timedelta(minutes=30)
            if i < (len(hourly.values()) - 1) and report.timestamp.hour == 23:
                interpolated = copy.deepcopy(report)
                interpolated.timestamp += timedelta(minutes=29)
                for k in interpolated.data.keys():
                    this = interpolated.data[k]
                    other = hourly[list(hourly.values())[i + 1].timestamp].data[k]
                    try:
                        interpolated.data[k] = k.interpolate(this,
                                                             other)

                    except NotImplementedError as ne:
                        logging.getLogger(self.__class__.__name__).log(level=logging.ERROR,
                                                                       msg=f'Could not interpolate {k} {ne}')
                    except TypeError as te:
                        logging.getLogger(self.__class__.__name__).log(level=logging.ERROR,
                                                                       msg=f'Could not interpolate {k} {te}')
                interpolated2 = copy.deepcopy(interpolated)
                interpolated2.timestamp += timedelta(minutes=2)
                interpolated_hours.append(interpolated)
                interpolated_hours.append(interpolated2)
        for h in interpolated_hours:
            hourly[h.timestamp] = h

        for h in hourly.values():
            time = h.timestamp
            if time in times.keys():
                for hk in h.data.keys():
                    if hk not in times[time].data.keys():
                        times[time].data[hk] = h.data[hk]
            else:
                times[time] = h
        merged = OrdDict(sorted(times.items(), key=lambda x: x[0]))
        return merged

    def get_report_from(self, start: datetime, end: datetime) -> OrderedDict[datetime, SingleReport]:
        start = start.astimezone(tzlocal())
        end = end.astimezone(tzlocal())
        items = [(k, v) for k, v in self.get_merged_report().items() if v is not None]
        keys = [k for k, v in items]
        start_idx = bisect.bisect_left(keys, start)
        end_idx = bisect.bisect_right(keys, end)
        d = OrdDict(items[start_idx:end_idx])
        return d


class WeatherPlugin(BasePlugin):

    def update_synchronously(self, *args, **kwargs) -> Union[WeatherReport, None]:
        raise NotImplementedError()

    def setup(self):
        raise NotImplementedError()

    def set_location(self, location):
        raise NotImplementedError()
