import logging
import os
import pickle
from enum import Enum
from typing import Type

import httplib2
from PyQt5.QtWidgets import QWidget, QInputDialog, QLineEdit, QMessageBox
from googleapiclient import discovery
from oauth2client import client, tools
from oauth2client.file import Storage

from widgets.helper import PathManager


class CredentialType(Enum):
    API_KEY = "API_KEY"
    CLIENT_SECRET_JSON = "CLIENT_SECRET_JSON"
    CONNECTION_URL = "CONNECTION_URL"
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    USERNAME_PASSWORD = "USERNAME_PASSWORD"
    SSL_VERIFY = "SSL_VERIFY"


class Credentials:
    __DATA__ = None

    @classmethod
    def _check_data(cls):
        if cls.__DATA__ is None:
            try:
                cls._load_data()
            except FileNotFoundError:
                cls.__DATA__ = {}

    @classmethod
    def _load_data(cls):
        with open(PathManager.join_path(f'{cls.__name__}.pickle'), 'rb') as f:
            # The protocol version used is detected automatically, so we do not
            # have to specify it.
            cls.__DATA__ = pickle.load(f)

    @classmethod
    def _try_get(cls, credential_type: CredentialType, accept_only=None):
        cls._check_data()
        try:
            if accept_only is not None and cls.__DATA__[credential_type] != accept_only:
                raise NoCredentialsSetException(cls, credential_type)
            return cls.__DATA__[credential_type]
        except KeyError:
            raise NoCredentialsSetException(cls, credential_type)

    @classmethod
    def _save_data(cls):
        with open(PathManager.join_path(f'{cls.__name__}.pickle'), 'wb') as f:
            # Pickle the 'data' dictionary using the highest protocol available.
            pickle.dump(cls.__DATA__, f, pickle.HIGHEST_PROTOCOL)

    @classmethod
    def _remove_saved_credentials(cls):
        os.remove(PathManager.join_path(f'{cls.__name__}.pickle'))

    @classmethod
    def set_credentials(cls, credential_type: CredentialType, credential_object):
        cls.__DATA__[credential_type] = credential_object
        cls._save_data()

    @classmethod
    def enter_credentials(cls, parent_widget: QWidget, credential_type: CredentialType, plugin):
        if credential_type == CredentialType.API_KEY:
            return cls.enter_api_key(parent_widget, plugin)
        raise NotImplementedError()

    @classmethod
    def get_api_key(cls):
        return cls._try_get(CredentialType.API_KEY)

    @classmethod
    def enter_text_info(cls, credential_type: CredentialType, parent_widget: QWidget, plugin,
                        title=None,  message=None, input_type=QLineEdit.Normal):
        old_cred = cls.__DATA__.get(credential_type, '')
        if not title:
            title = f'Enter your {credential_type.name}' if old_cred == '' else f'Re-enter your {credential_type.name}'

        credentials, accepted = QInputDialog.getText(parent_widget,
                                                     title,
                                                     message if message else f'{cls.__name__} {credential_type.name}:',
                                                     input_type,
                                                     old_cred)
        if accepted:
            cls.set_credentials(credential_type, credentials)
            plugin.update_async()
        return accepted

    @classmethod
    def enter_boolean_info(cls, credential_type: CredentialType, parent_widget: QWidget, plugin,
                           title=None, question=None, invert_boolean=False):
        reply = QMessageBox.question(parent_widget,
                                     title if title else f'Set {credential_type}?',
                                     question if question else 'Set to "True"?')
        if reply == QMessageBox.Yes:
            cls.set_credentials(credential_type, not invert_boolean)
            plugin.update_async()
            return True
        if reply == QMessageBox.No:
            cls.set_credentials(credential_type, invert_boolean)
            plugin.update_async()
            return True

        return False

    @classmethod
    def enter_api_key(cls, parent_widget: QWidget, plugin):
        return cls.enter_text_info(CredentialType.API_KEY, parent_widget, plugin)


class NoCredentialsSetException(Exception):
    def __init__(self, credentials: Type[Credentials], credential_type: CredentialType):
        self.credentials = credentials
        self.credential_type = credential_type

    def enter_credentials(self, parent_widget: QWidget, plugin):
        return self.credentials.enter_credentials(parent_widget, self.credential_type, plugin)


class CredentialsNotValidException(Exception):
    def __init__(self, credentials: Type[Credentials], credential_type: CredentialType):
        self.credentials = credentials
        self.credential_type = credential_type

    def reenter_credentials(self, parent_widget: QWidget, plugin):
        self.credentials.enter_credentials(parent_widget, self.credential_type, plugin)


class GoogleCredentials(Credentials):
    _service = None

    @classmethod
    def get_service(cls):
        if GoogleCredentials._service is None:
            try:
                credentials = cls._get_client_json_credentials()
            except Exception:
                raise NoCredentialsSetException(cls, CredentialType.CLIENT_SECRET_JSON)
            http = credentials.authorize(httplib2.Http())
            GoogleCredentials.service = discovery.build('calendar', 'v3', http=http, cache_discovery=False)
        return GoogleCredentials.service

    @classmethod
    def enter_credentials(cls, parent_widget: QWidget, credential_type: CredentialType, plugin):
        if credential_type == CredentialType.API_KEY:
            cls.enter_api_key(parent_widget, plugin)
        elif credential_type == CredentialType.CLIENT_SECRET_JSON:
            cls.enter_client_secret(parent_widget, plugin)
        else:
            raise NotImplementedError()

    @classmethod
    def enter_client_secret(cls, parent_widget: QWidget, plugin):
        QMessageBox(QMessageBox.Information, "Download client_secret.json",
                    "You will need to download the file 'credentials.json' from Google.\n"
                    "You will be forwarded to the website in the Browser.\n"
                    "Click 'Enable the Google Calendar API' and follow the instructions.\n"
                    "Finally, click 'DOWNLOAD CLIENT CONFIGURATION' and save the file to the app's main directory.",
                    QMessageBox.Ok).exec()
        import webbrowser
        webbrowser.open("https://developers.google.com/calendar/quickstart/python")

    @classmethod
    def _get_client_json_credentials(cls):
        """Gets valid user credentials from storage.

        If nothing has been stored, or if the stored credentials are invalid,
        the OAuth2 flow is completed to obtain the new credentials.

        Returns:
            Credentials, the obtained credential.
        """
        # If modifying these scopes, delete your previously saved credentials
        # at ~/.credentials/calendar-python-quickstart.json

        SCOPES = 'https://www.googleapis.com/auth/calendar'  # USE FOR WRITE ACCESS
        # SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
        CLIENT_SECRET_FILE = 'credentials.json'
        APPLICATION_NAME = 'DESKTOP WIDGETS'
        try:
            import argparse
            flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
        except ImportError:
            flags = None

        home_dir = os.path.expanduser('~')
        credential_dir = os.path.join(home_dir, '.credentials')
        if not os.path.exists(credential_dir):
            os.makedirs(credential_dir)
        credential_path = os.path.join(credential_dir,
                                       'calendar-python-quickstart.json')

        store = Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            if not os.path.isfile(CLIENT_SECRET_FILE):
                raise NoCredentialsSetException(cls, CredentialType.CLIENT_SECRET_JSON)
            flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
            flow.user_agent = APPLICATION_NAME
            if flags:
                credentials = tools.run_flow(flow, store, flags)
            else:  # Needed only for compatibility with Python 2.6
                credentials = tools.run(flow, store)
            logging.getLogger(cls.__name__).log(level=logging.DEBUG, msg='Storing credentials to ' + credential_path)
        return credentials


class ClimacellCredentials(Credentials):
    pass


class ClimacellAPIv4Credentials(Credentials):
    pass


class MapQuestCredentials(Credentials):
    pass


class BringCredentials(Credentials):
    @classmethod
    def get_username(cls):
        return cls._try_get(CredentialType.USERNAME)

    @classmethod
    def get_password(cls):
        return cls._try_get(CredentialType.PASSWORD)

    @classmethod
    def enter_credentials(cls, parent_widget: QWidget, credential_type: CredentialType, plugin):
        if credential_type == CredentialType.PASSWORD:
            return cls.enter_text_info(credential_type, parent_widget, plugin, input_type=QLineEdit.Password)
        return cls.enter_text_info(credential_type, parent_widget, plugin)


class CalDAVCredentials(Credentials):

    @classmethod
    def get_url(cls):
        return cls._try_get(CredentialType.CONNECTION_URL)

    @classmethod
    def get_username(cls):
        return cls._try_get(CredentialType.USERNAME)

    @classmethod
    def get_password(cls):
        return cls._try_get(CredentialType.PASSWORD)

    @classmethod
    def get_ssl_verify(cls, accept_only=None):
        return cls._try_get(CredentialType.SSL_VERIFY, accept_only)

    @classmethod
    def enter_credentials(cls, parent_widget: QWidget, credential_type: CredentialType, plugin):
        if credential_type == CredentialType.SSL_VERIFY:
            return cls.enter_boolean_info(credential_type, parent_widget, plugin,
                                          title='Certificate could not be verified.',
                                          question='Do you wish to accept the insecure Certificate?',
                                          invert_boolean=True)
        if credential_type == CredentialType.PASSWORD:
            return cls.enter_text_info(credential_type, parent_widget, plugin, input_type=QLineEdit.Password)
        return cls.enter_text_info(credential_type, parent_widget, plugin)

