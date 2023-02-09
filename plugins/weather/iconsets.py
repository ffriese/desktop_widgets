from plugins.weather.weather_data_types import WeatherCode


class IconSet:
    WEATHER_UNDERGOUND = {
        'folder': 'weather_underground',
        'data': {
            WeatherCode.FREEZING_RAIN_HEAVY: 'sleet',
            WeatherCode.FREEZING_RAIN: 'sleet',
            WeatherCode.FREEZING_RAIN_LIGHT: 'chancesleet',
            WeatherCode.FREEZING_DRIZZLE: 'chanceflurries',
            WeatherCode.ICE_PELLETS_HEAVY: 'sleet',
            WeatherCode.ICE_PELLETS: 'sleet',
            WeatherCode.ICE_PELLETS_LIGHT: 'sleet',
            WeatherCode.SNOW_HEAVY: 'snow',
            WeatherCode.SNOW: 'snow',
            WeatherCode.SNOW_LIGHT: 'flurries',
            WeatherCode.FLURRIES: 'flurries',
            WeatherCode.THUNDERSTORM: 'tstorm',
            WeatherCode.RAIN_HEAVY: 'rain',
            WeatherCode.RAIN: 'rain',
            WeatherCode.RAIN_LIGHT: 'chancerain',
            WeatherCode.DRIZZLE: 'chancerain',
            WeatherCode.FOG_LIGHT: 'fog',
            WeatherCode.FOG: 'fog',
            WeatherCode.CLOUDY: 'cloudy',
            WeatherCode.MOSTLY_CLOUDY: 'mostlycloudy',
            WeatherCode.PARTLY_CLOUDY: 'partlycloudy',
            WeatherCode.MOSTLY_CLEAR: 'mostlysunny',
            WeatherCode.CLEAR: 'sunny'
        },
        'licence': 'https://github.com/manifestinteractive/weather-underground-icons/blob/master/LICENSE'
    }
