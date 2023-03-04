import copy
import json
import warnings
from collections import OrderedDict, defaultdict
from datetime import datetime, timedelta
from typing import Union

import dateutil.parser
from dateutil.tz import tzlocal

import requests

from credentials import ClimacellCredentials, CredentialsNotValidException, CredentialType, \
    MapQuestCredentials, ClimacellAPIv4Credentials
from plugins.base import APILimitExceededException, APIDeprecatedException
from plugins.weather.weather_data_types import TemperatureParameters, PrecipitationParameters, \
    WindParameters, PrecipitationType, SingleReport, CloudParameters, SunTimeParameters, \
    WeatherDescriptionParameters, WeatherCode
from plugins.weather.weather_plugin import WeatherPlugin, WeatherReport

REALTIME = "https://api.climacell.co/v3/weather/realtime"

NOW_CAST = "https://api.climacell.co/v3/weather/nowcast"
HOURLY = "https://api.climacell.co/v3/weather/forecast/hourly"
DAILY = "https://api.climacell.co/v3/weather/forecast/daily"

PREDEF_LOCS = {
    'HH': {'lat': 53.5510846, 'long': 9.9936819}
}

LOC = 'HH'


class ClimacellPlugin(WeatherPlugin):
    MAPPING = {
        'temp': TemperatureParameters.TEMPERATURE,
        'feels_like': TemperatureParameters.FEELS_LIKE,
        'precipitation': PrecipitationParameters.INTENSITY,
        'precipitation_probability': PrecipitationParameters.PROBABILITY,
        'precipitation_type': PrecipitationParameters.TYPE,
        'wind_speed': WindParameters.SPEED,
        'wind_direction': WindParameters.DIRECTION,
        'cloud_base': CloudParameters.BASE,
        'cloud_cover': CloudParameters.COVER,
        'cloud_ceiling': CloudParameters.CEILING,
        'sunrise': SunTimeParameters.RISE,
        'sunset': SunTimeParameters.SET,
        'weather_code': WeatherDescriptionParameters.CODE
    }
    CONVERSION_FUNCTIONS = {
        PrecipitationParameters.TYPE:
            lambda type_str: defaultdict(lambda: PrecipitationType.NONE, {
                'rain': PrecipitationType.RAIN,
                'snow': PrecipitationType.SNOW,
                'ice pellets': PrecipitationType.ICE_PELLETS,
                'freezing rain': PrecipitationType.FREEZING_RAIN,
                'none': PrecipitationType.NONE,
                None: PrecipitationType.NONE
            })[type_str],
        WeatherDescriptionParameters.CODE:
            lambda type_str: {
                'freezing_rain_heavy': WeatherCode.FREEZING_RAIN_HEAVY,
                'freezing_rain': WeatherCode.FREEZING_RAIN,
                'freezing_rain_light': WeatherCode.FREEZING_RAIN_LIGHT,
                'freezing_drizzle': WeatherCode.FREEZING_DRIZZLE,
                'ice_pellets_heavy': WeatherCode.ICE_PELLETS_HEAVY,
                'ice_pellets': WeatherCode.ICE_PELLETS,
                'ice_pellets_light': WeatherCode.ICE_PELLETS_LIGHT,
                'snow_heavy': WeatherCode.SNOW_HEAVY,
                'snow': WeatherCode.SNOW,
                'snow_light': WeatherCode.SNOW_LIGHT,
                'flurries': WeatherCode.FLURRIES,
                'tstorm': WeatherCode.THUNDERSTORM,
                'rain_heavy': WeatherCode.RAIN_HEAVY,
                'rain': WeatherCode.RAIN,
                'rain_light': WeatherCode.RAIN_LIGHT,
                'drizzle': WeatherCode.DRIZZLE,
                'fog_light': WeatherCode.FOG_LIGHT,
                'fog': WeatherCode.FOG,
                'cloudy': WeatherCode.CLOUDY,
                'mostly_cloudy': WeatherCode.MOSTLY_CLOUDY,
                'partly_cloudy': WeatherCode.PARTLY_CLOUDY,
                'mostly_clear': WeatherCode.MOSTLY_CLEAR,
                'clear': WeatherCode.CLEAR,
                None: None
            }[type_str],
        SunTimeParameters.RISE:
            lambda time_str:
            dateutil.parser.parse(time_str).
                astimezone(tzlocal()).replace(microsecond=0, second=0) if time_str is not None else None,
        SunTimeParameters.SET:
            lambda time_str:
            dateutil.parser.parse(time_str).
                astimezone(tzlocal()).replace(microsecond=0, second=0) if time_str is not None else None,

    }
    MAPPING_v4 = {
        'temperature': TemperatureParameters.TEMPERATURE,
        'feelsLike': TemperatureParameters.FEELS_LIKE,
        'precipitationIntensity': PrecipitationParameters.INTENSITY,
        'precipitationProbability': PrecipitationParameters.PROBABILITY,
        'precipitationType': PrecipitationParameters.TYPE,
        'windSpeed': WindParameters.SPEED,
        'windGust': WindParameters.GUST,
        'windDirection': WindParameters.DIRECTION,
        'cloudBase': CloudParameters.BASE,
        'cloudCover': CloudParameters.COVER,
        'cloudCeiling': CloudParameters.CEILING,
        'sunriseTime': SunTimeParameters.RISE,
        'sunsetTime': SunTimeParameters.SET,
        'weatherCode': WeatherDescriptionParameters.CODE
    }
    CONVERSION_FUNCTIONS_v4 = {
        PrecipitationParameters.TYPE:
            lambda type_str: defaultdict(lambda: PrecipitationType.NONE, {
                1: PrecipitationType.RAIN,
                2: PrecipitationType.SNOW,
                4: PrecipitationType.ICE_PELLETS,
                3: PrecipitationType.FREEZING_RAIN,
                0: PrecipitationType.NONE,
                None: PrecipitationType.NONE
            })[type_str],
        WeatherDescriptionParameters.CODE:
            lambda type_str: {
                6201: WeatherCode.FREEZING_RAIN_HEAVY,
                6001: WeatherCode.FREEZING_RAIN,
                6200: WeatherCode.FREEZING_RAIN_LIGHT,
                6000: WeatherCode.FREEZING_DRIZZLE,
                7101: WeatherCode.ICE_PELLETS_HEAVY,
                7000: WeatherCode.ICE_PELLETS,
                7102: WeatherCode.ICE_PELLETS_LIGHT,
                5101: WeatherCode.SNOW_HEAVY,
                5000: WeatherCode.SNOW,
                5100: WeatherCode.SNOW_LIGHT,
                5001: WeatherCode.FLURRIES,
                8000: WeatherCode.THUNDERSTORM,
                4201: WeatherCode.RAIN_HEAVY,
                4001: WeatherCode.RAIN,
                4200: WeatherCode.RAIN_LIGHT,
                4000: WeatherCode.DRIZZLE,
                2100: WeatherCode.FOG_LIGHT,
                2000: WeatherCode.FOG,
                1001: WeatherCode.CLOUDY,
                1102: WeatherCode.MOSTLY_CLOUDY,
                1101: WeatherCode.PARTLY_CLOUDY,
                1100: WeatherCode.MOSTLY_CLEAR,
                1000: WeatherCode.CLEAR,
                None: None
            }[type_str],
        SunTimeParameters.RISE:
            lambda time_str:
            dateutil.parser.parse(time_str).
                astimezone(tzlocal()).replace(microsecond=0, second=0) if time_str is not None else None,
        SunTimeParameters.SET:
            lambda time_str:
            dateutil.parser.parse(time_str).
                astimezone(tzlocal()).replace(microsecond=0, second=0) if time_str is not None else None,

    }

    def quit(self):
        pass

    def update_synchronously(self, *args) -> Union[WeatherReport, None]:
        # return None
        try:
            data = self._climacell_request_v4()['data']
            return WeatherReport(
                # now=self._get_reports_v4(data['timelines'][0]),
                minutely=self._get_reports_v4(data['timelines'], '5m'),
                hourly=self._get_reports_v4(data['timelines'], '1h'),
                daily=self._get_reports_v4(data['timelines'], '1d'),
                location=self._get_location(),
                updated=datetime.now()
            )
            # return WeatherReport(
            #     now=self._get_reports(self._realtime),
            #     minutely=self._get_reports(self._now_cast),
            #     hourly=self._get_reports(self._hourly),
            #     daily=self._get_reports(self._daily),
            #     location=self._get_location(),
            #     updated=datetime.now()
            # )
        except requests.ConnectionError:
            self.log_error('Connection Error. Returning None')
            return None
        except requests.RequestException as e:
            if json.loads(e.args[0])['message'] == 'You cannot consume this service':
                raise CredentialsNotValidException(ClimacellCredentials, CredentialType.API_KEY)
            if json.loads(e.args[0])['message'] == 'API rate limit exceeded':
                raise APILimitExceededException(f"LIMITS EXCEEDED: {self.remaining_requests}")
            if json.loads(e.args[0])['message'] == 'The request limit for this resource has been reached for the ' \
                                                   'current rate limit window. Wait and retry the operation, ' \
                                                   'or examine your API request volume.':
                raise APILimitExceededException(f"LIMITS EXCEEDED: {self.remaining_requests}")
            if json.loads(e.args[0])['message'] == 'v3 is permanently deprecated. Please upgrade to API v4':
                raise APIDeprecatedException(f"API v3 is permanently deprecated. Please upgrade to API v4")
            if json.loads(e.args[0])['message'] == 'There is no data for this time and location.':
                self.log_warn(f'No weather data for {self.lat}, {self.long}')
                return None
            self.log_error('request exception', e, e.response)
            raise e

    def __init__(self):
        super().__init__()
        self.remaining_requests = None
        self.lat = PREDEF_LOCS[LOC]['lat']
        self.long = PREDEF_LOCS[LOC]['long']
        self.location = None

    def setup(self):
        self.log('init...')

    def _realtime(self):
        return self._climacell_request(
            REALTIME,
            fields=','.join(['temp', 'feels_like',
                             'dewpoint', 'humidity',
                             'wind_speed', 'wind_direction', 'wind_gust',
                             'baro_pressure',
                             'pollen_tree', 'pollen_weed', 'pollen_grass',
                             'visibility',
                             'cloud_cover', 'cloud_base', 'cloud_ceiling',
                             'precipitation', 'precipitation_type',
                             'weather_code']
                            ))

    def _now_cast(self, time_delta: timedelta = None, time_step=1):
        if time_delta is None:
            time_delta = timedelta(minutes=360)
        end_time = f"{datetime.now(tzlocal()) + time_delta}"
        return self._climacell_request(
            NOW_CAST, time_delta, timestep=f"{time_step}",
            start_time='now', end_time=end_time,
            fields=','.join(['temp', 'feels_like',
                             'dewpoint', 'humidity',
                             'wind_speed', 'wind_direction', 'wind_gust',
                             'baro_pressure',
                             'pollen_tree', 'pollen_weed', 'pollen_grass',
                             'visibility',
                             'cloud_cover', 'cloud_base', 'cloud_ceiling',
                             'precipitation', 'precipitation_type',
                             'weather_code']
                            ))

    def _hourly(self, time_delta: timedelta = None):
        if time_delta is None:
            time_delta = timedelta(hours=108)
        end_time = f"{datetime.now(tzlocal()) + time_delta}"
        return self._climacell_request(
            HOURLY, time_delta,
            start_time='now', end_time=end_time,
            fields=','.join(['temp', 'feels_like',
                             'dewpoint', 'humidity',
                             'wind_speed', 'wind_direction', 'wind_gust',
                             'baro_pressure',
                             'pollen_tree', 'pollen_weed', 'pollen_grass',
                             'visibility',
                             'moon_phase',
                             'cloud_cover', 'cloud_base', 'cloud_ceiling',
                             'precipitation', 'precipitation_probability', 'precipitation_type',
                             'weather_code']
                            ))

    def _daily(self, time_delta: timedelta = None):
        if time_delta is None:
            time_delta = timedelta(days=14)
        end_time = f"{datetime.now(tzlocal()) + time_delta}"
        return self._climacell_request(
            DAILY, time_delta,
            start_time='now', end_time=end_time,
            fields=','.join(['temp', 'feels_like',
                             'humidity',
                             'wind_speed', 'wind_direction',
                             'baro_pressure',
                             'sunrise', 'sunset',
                             'visibility',
                             'precipitation_accumulation', 'precipitation', 'precipitation_probability',
                             'weather_code']
                            ))

    def _climacell_request_v4(self):
        url = 'https://data.climacell.co/v4/timelines'
        querystring = {
            'location': f'{self.lat},{self.long}',
            'fields': ['temperature', 'precipitationType', 'precipitationProbability', 'precipitationIntensity',
                       'windSpeed', 'windGust', 'cloudCover',
                       'weatherCode', 'sunsetTime', 'sunriseTime'],
            'apikey': ClimacellAPIv4Credentials.get_api_key(),
            'timesteps': ['5m', '1h', '1d']
        }
        response = requests.request("GET", url, params=querystring)
        try:
            lim_day = response.headers['x-ratelimit-limit-day']
            lim_hour = response.headers['x-ratelimit-limit-hour']
            rem_day = response.headers['x-ratelimit-remaining-day']
            rem_hour = response.headers['x-ratelimit-remaining-hour']
            self.remaining_requests = {
                'day': {'limit': lim_day, 'remaining': rem_day},
                'hour': {'limit': lim_hour, 'remaining': rem_hour}
            }
        except (KeyError, IndexError):
            if self.remaining_requests is None:
                self.remaining_requests = {
                    'day': {'limit': '?', 'remaining': '?'},
                    'hour': {'limit': '?', 'remaining': '?'}
                }
        if str(response.status_code)[0] != '2':   # success codes start with 2

            self.log_error(f'CODE {response.status_code}. resp:"{response.text}"')
            raise requests.RequestException(response.text)
        data = json.loads(response.text)
        # self.log_info(data)
        return data

    # noinspection PyProtectedMember
    def _climacell_request(self, url: str, time_delta: timedelta = None, **params):

        querystring = {"lat": f"{self.lat}",
                       "lon": f"{self.long}",
                       "unit_system": "si",
                       "fields": "temp,precipitation,weather_code",
                       "apikey": ClimacellCredentials.get_api_key()}
        querystring = {**querystring, **params}
        # try:
        response = requests.request("GET", url, params=querystring)
        # (response.content)
        try:
            lim_day = response.headers['x-ratelimit-limit-day'][1]
            lim_hour = response.headers['x-ratelimit-limit-hour'][1]
            rem_day = response.headers['x-ratelimit-remaining-day'][1]
            rem_hour = response.headers['x-ratelimit-remaining-hour'][1]
            self.remaining_requests = {
                'day': {'limit': lim_day, 'remaining': rem_day},
                'hour': {'limit': lim_hour, 'remaining': rem_hour}
            }
        except (KeyError, IndexError):
            if self.remaining_requests is None:
                self.remaining_requests = {
                    'day': {'limit': '?', 'remaining': '?'},
                    'hour': {'limit': '?', 'remaining': '?'}
                }
        if response.status_code != 200:
            self.log_error(f'resp:"{response.text}"')
            raise requests.RequestException(response.text)
        data = json.loads(response.text)

        if type(data) == dict:
            data = [data]

        for d in data:
            time_str = d['observation_time']['value']
            utc_time = dateutil.parser.parse(time_str)
            local_time = utc_time.astimezone(tzlocal()).replace(microsecond=0, second=0)
            d['observation_time']['value'] = local_time
        self.log(self.remaining_requests)
        return data
        # except requests.exceptions.ConnectionError as ce:
        #
        #     print('CONNECTION ERR:', type(ce), ce)
        #     return None
        # except IndexError as e:
        #     print('BIG BAD ERR:', type(e), e)
        #     return None

    def get_location(self):
        if self.location is None:
            self.location = self._get_location()
        return self.location

    def _parse_adress_components(self, results, search_types=None):
        if search_types is None:
            return results[0]['address_components'][0]['long_name']
        for search_type in search_types:
            for result in results:
                for component in result['address_components']:
                    # print(component['types'], component, search_type.issubset(component['types']))
                    if search_type.issubset(component['types']):
                        try:
                            return component['long_name']
                        except KeyError as e:
                            print(e, component)
        return None

    def _get_location(self):
        api_key = MapQuestCredentials.get_api_key()
        url = f'http://www.mapquestapi.com/geocoding/v1/reverse?key={api_key}&location={self.lat},{self.long}'
        try:
            response = requests.get(url, headers={'accept-language': 'DE'})
        except requests.exceptions.RequestException as exception:
            return ''

        if response.status_code != 200:
            raise requests.RequestException(response=response)
        self.log_info(response.text)

        result = json.loads(response.text)['results'][0]['locations'][0]
        self.log_info(result)
        quality = result.get('geocodeQuality')
        if quality in ['POINT', 'ADDRESS', 'STREET', 'NEIGHBORHOOD', 'CITY']:
            sub = result.get('adminArea5', quality)
        else:
            sub = result.get('adminArea3', quality)
        country = result.get('adminArea1', '')

        self.log_info(sub, country)
        return f'{sub}, {country}'

    def __get_location(self):
        warnings.warn('deprecated. use mapquest', DeprecationWarning, stacklevel=2)
        api_key = GoogleCredentials.get_api_key()
        url = f'https://maps.googleapis.com/maps/api/geocode/json?latlng={self.lat},{self.long}' \
              f'&key={api_key}'
        try:
            response = requests.get(url)
        except requests.exceptions.RequestException as exception:
            return ''
        result = json.loads(response.text)
        if result.get('error_message', '') == 'The provided API key is invalid.':
            raise CredentialsNotValidException(GoogleCredentials, CredentialType.API_KEY)
        country = self._parse_adress_components(result['results'], [{'country', 'political'}])
        city = self._parse_adress_components(result['results'], [{'locality'},
                                                                 {'administrative_area_level_2'},
                                                                 {'administrative_area_level_1'}])
        if country is not None:
            if city is not None:
                return f'{city}, {country}'
            return country
        try:
            plus_code = result['plus_code']['compound_code']
            return ' '.join(plus_code.split(' ')[1:])
        except KeyError:
            try:
                return self._parse_adress_components(result['results'])
            except IndexError:
                pass
            return f'Coordinates: {round(self.lat, 4)}, {round(self.long, 4)}'

    def _merge(self, nowcast, hourly):
        times = {d['observation_time']['value']: d for d in nowcast}
        interpolated_hours = []
        for i, d in enumerate(hourly):
            d['observation_time']['value'] += timedelta(minutes=30)
            if i < (len(hourly) - 1) and d['observation_time']['value'].hour == 23:
                interpolated = copy.deepcopy(d)
                interpolated['observation_time']['value'] += timedelta(minutes=29)
                for k in interpolated.keys():
                    try:
                        if type(interpolated[k]) == dict and type(interpolated[k]['value']) in [int, float]:
                            interpolated[k]['value'] += hourly[i + 1][k]['value']
                            interpolated[k]['value'] /= 2.0
                    except KeyError or TypeError:
                        pass
                interpolated2 = copy.deepcopy(interpolated)
                interpolated2['observation_time']['value'] += timedelta(minutes=2)
                interpolated_hours.append(interpolated)
                interpolated_hours.append(interpolated2)
        hourly.extend(interpolated_hours)

        for h in hourly:
            time = h['observation_time']['value']
            if time in times.keys():
                for hk in h.keys():
                    if hk not in times[time].keys():
                        times[time][hk] = h[hk]
            else:
                times[time] = h
        merged = OrderedDict(sorted(times.items(), key=lambda x: x[0]))
        return list(merged.values())

    def set_location(self, loc):
        if self.lat != loc['lat'] or self.long != loc['long']:
            self.location = ''
            self.lat = loc['lat']
            self.long = loc['long']
            # self.location = self._get_location()

    def _get_reports_v4(self, data, interval_name):
        data_input = {}
        for timeline in data:
            if timeline['timestep'] == interval_name:
                data_input = timeline
                break
        reports = OrderedDict()
        for row in data_input['intervals']:
            data = {}
            time_str = row['startTime']
            utc_time = dateutil.parser.parse(time_str)
            local_time = utc_time.astimezone(tzlocal()).replace(microsecond=0, second=0)
            timestamp = local_time
            for key, value in row['values'].items():
                try:
                    param_type = ClimacellPlugin.MAPPING_v4[key]
                    data[param_type] = {'value': value}
                    if param_type in ClimacellPlugin.CONVERSION_FUNCTIONS_v4.keys():
                        data[param_type]['value'] = \
                            ClimacellPlugin.CONVERSION_FUNCTIONS_v4[param_type](data[param_type]['value'])

                except KeyError:
                    pass
            object_map = defaultdict(dict)

            for key, item in data.items():
                object_map[key.__OBJ_CLASS__][key.name] = item
            objs = {}
            for key, item in object_map.items():
                objs[key] = key(**item)
            report = SingleReport(timestamp, objs)
            reports[timestamp] = report
        return reports

    def _get_reports(self, function):
        reports = OrderedDict()
        for row in function():
            data = {}
            timestamp = row['observation_time']['value']
            for key, value in row.items():
                try:
                    param_type = ClimacellPlugin.MAPPING[key]
                    data[param_type] = value
                    if param_type in ClimacellPlugin.CONVERSION_FUNCTIONS.keys():
                        data[param_type]['value'] = \
                            ClimacellPlugin.CONVERSION_FUNCTIONS[param_type](data[param_type]['value'])

                except KeyError:
                    pass
            object_map = defaultdict(dict)

            for key, item in data.items():
                object_map[key.__OBJ_CLASS__][key.name] = item
            objs = {}
            for key, item in object_map.items():
                objs[key] = key(**item)
            report = SingleReport(timestamp, objs)
            reports[timestamp] = report
        return reports
