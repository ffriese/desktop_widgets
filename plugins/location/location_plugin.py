from typing import Union

from plugins.base import BasePlugin


class LocationPlugin(BasePlugin):

    def update_synchronously(self, *args) -> Union[str, None]:
        raise NotImplementedError()

    def setup(self):
        raise NotImplementedError()

    def geocode(self, loc_str):
        raise NotImplementedError()

    def reverse_geocode(self, lat, long):
        raise NotImplementedError()

    def create_location_picker(self):
        raise NotImplementedError()