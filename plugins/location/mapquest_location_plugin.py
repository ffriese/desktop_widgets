import json
from threading import Thread
from typing import Union

import requests

from credentials import MapQuestCredentials
from plugins.location.location_plugin import LocationPlugin


class MapQuestLocationPlugin(LocationPlugin):
    def update_synchronously(self, *args) -> Union[str, None]:
        pass

    def setup(self):
        pass

    def geocode(self, loc_str):
        pass

    def reverse_geocode(self, lat, long):
        api_key = self.get_api_key()
        url = f'http://open.mapquestapi.com/geocoding/v1/reverse?key={api_key}&location={self.lat},{self.long}'
        try:
            response = requests.get(url, headers={'accept-language': 'DE'})
        except requests.exceptions.RequestException as exception:
            return ''
        result = json.loads(response.text)['results'][0]['locations'][0]
        self.log_info(result)
        quality = result.get('geocodeQuality')
        if quality in ['POINT', 'ADDRESS', 'STREET', 'NEIGHBORHOOD', 'CITY']:
            sub = result.get('adminArea5', quality)
        else:
            sub = result.get('adminArea3', quality)
        country = result.get('adminArea1', '')
        return f'{sub}, {country}'

    def create_location_picker(self):
        pass

    def quit(self):
        pass

    def get_api_key(self):
        try:
            return MapQuestCredentials.get_api_key()
        except Exception as e:
            self.log(self, 'CAUGHT EXCEPTION:', e, type(e), level='err')

            def throw(_e):
                self.threaded_exception.emit(_e)

            t = Thread(target=throw, args=[e])
            t.setDaemon(True)
            t.start()
            t.join()
            raise e
