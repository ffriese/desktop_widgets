import logging
import pickle

from widgets.helper import PathManager


class SettingsStorage:
    pass

    @staticmethod
    def save(obj: object, filename: str):
        PathManager.make_path('storage')
        logging.getLogger(f'ffwidgets.{SettingsStorage.__name__}').log(logging.INFO, f'saving to storage/{filename}')
        with open(PathManager.join_path('storage', f'{filename}.pickle'), 'wb') as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def _load(filename: str):
        logging.getLogger(f'ffwidgets.{SettingsStorage.__name__}').log(logging.INFO, f'loading from storage/{filename}')
        with open(PathManager.join_path('storage', f'{filename}.pickle'), 'rb') as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            return pickle.load(f)

    @staticmethod
    def load_or_default(filename: str, default: object):
        try:
            return SettingsStorage._load(filename)
        except IOError:
            return default


class YamlSettings:
    pass
