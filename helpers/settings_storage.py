import logging
import os
import pickle

from helpers.tools import PathManager


class SettingsStorage:
    pass

    @staticmethod
    def save(obj: object, filename: str):
        PathManager.make_path(PathManager.get_storage_path())
        logging.getLogger('desktopwidgets.{SettingsStorage.__name__}').log(logging.INFO, f'saving to storage/{filename}')
        with open(PathManager.get_storage_path(f'{filename}.pickle'), 'wb') as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _load(filename: str):
        logging.getLogger(f'desktopwidgets.{SettingsStorage.__name__}').log(logging.INFO, f'loading from storage/{filename}')
        with open(PathManager.get_storage_path(f'{filename}.pickle'), 'rb') as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            return pickle.load(f)

    @staticmethod
    def load_or_default(filename: str, default: object):
        try:
            return SettingsStorage._load(filename)
        except IOError:
            return default

    @staticmethod
    def delete(filename: str):
        logging.getLogger(f'ffwidgets.{SettingsStorage.__name__}').log(logging.INFO, f'deleting from storage/{filename}')
        file_path = PathManager.join_path('storage', f'{filename}.pickle')
        if os.path.exists(file_path):
            os.remove(file_path)


class YamlSettings:
    pass
