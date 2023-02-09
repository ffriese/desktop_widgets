import urllib.request
import urllib.error
import urllib.parse
from PyQt5.QtGui import QPixmap, QIcon
from PyQt5.QtDBus import QDBusMessage, QDBusConnection, QDBusInterface
from PyQt5.QtCore import pyqtSignal, pyqtSlot

from plugins.base import BasePlugin


class MusicPlayerPlugin(BasePlugin):
    pos_update = pyqtSignal(float)
    song_update = pyqtSignal(dict)
    player_state_update = pyqtSignal(str)

    def __init__(self):
        super(MusicPlayerPlugin, self).__init__()
        self.time_multiplier = 1

    def setup(self):
        super(MusicPlayerPlugin, self).setup()

    def open_player(self):
        raise NotImplementedError

    def close_player(self):
        raise NotImplementedError

    @staticmethod
    def get_player_icon(gtk_icon_name=None):
        if gtk_icon_name is not None:
            return QIcon.fromTheme(gtk_icon_name)
            # return Gtk.IconTheme.get_default().lookup_icon(gtk_icon_name, 48, 0)
        print('WARNING: get_player_icon IS NOT IMPLEMENTED!')

    def quit(self):
        raise NotImplementedError

    def get_current_position(self):
        raise NotImplementedError


class MPRISMusicPlayerPlugin(MusicPlayerPlugin):
    def __init__(self, mpris_name):
        super(MPRISMusicPlayerPlugin, self).__init__()
        self.dbus = None
        self.mpris_name = mpris_name

    def setup(self):
        super(MPRISMusicPlayerPlugin, self).setup()
        self.dbus = DBusManager(self.mpris_name)
        self.dbus.time_multiplier = self.time_multiplier
        self.dbus.pos_update.connect(self.pos_update)
        self.dbus.song_update.connect(self.song_update)
        self.dbus.player_state_update.connect(self.player_state_update)
        self.dbus.plugin_log.connect(self.plugin_log)

    def start(self):
        self.dbus.start()

    def open_player(self):
        raise NotImplementedError

    def close_player(self):
        self.dbus.close()

    def quit(self):
        self.dbus.quit()

    def get_current_position(self):
        return self.dbus.get_position()


class DBusManager(BasePlugin):
    pos_update = pyqtSignal(float)
    song_update = pyqtSignal(dict)
    player_state_update = pyqtSignal(str)

    def __init__(self, mpris_name):
        super(DBusManager, self).__init__()
        self.mpris_name = mpris_name
        self.time_multiplier = 1
        self.current_properties = {'Metadata': {}, 'PlaybackStatus': None}
        self.player = None
        self.player_controller = None
        self.loop = None
        self.quit_requested = False

    def start(self):
        QDBusConnection.sessionBus().connect('', '',
                                             'org.freedesktop.DBus', 'NameOwnerChanged',
                                             self.change)
        self.connect_to_player()

    @pyqtSlot(QDBusMessage)
    def change(self, *args):
        data = args[0].arguments()
        if data[0] == 'org.mpris.MediaPlayer2.%s' % self.mpris_name:
            if data[1] == '':
                self.connect_to_player()
                self.player.setProperty('dbus_id', data[2])
            elif self.player is not None and data[2] == '':
                self.log('disconnecting...', self.player.property('dbus_id'))
                self.disconnect_from_player()
            else:
                self.log('weird state:', self.player, data)

    def connect_to_player(self):
        self.log('trying to connect to', self.mpris_name)

        QDBusConnection.sessionBus().connect('org.mpris.MediaPlayer2.%s' % self.mpris_name, '/org/mpris/MediaPlayer2',
                                             'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                                             self.properties_change)
        self.player = QDBusInterface('org.mpris.MediaPlayer2.%s' % self.mpris_name, '/org/mpris/MediaPlayer2',
                                     'org.freedesktop.DBus.Properties', QDBusConnection.sessionBus())
        self.player_controller = QDBusInterface('org.mpris.MediaPlayer2.%s' % self.mpris_name,
                                                '/org/mpris/MediaPlayer2')

        if self.player.isValid():
            metadata_reply = self.player.call('Get', 'org.mpris.MediaPlayer2.Player', 'Metadata')
            status_reply = self.player.call('Get', 'org.mpris.MediaPlayer2.Player', 'PlaybackStatus')
            self.player.setProperty('dbus_id', status_reply.service())
            self.relay_metadata(metadata_reply.arguments()[0])
            self.player_state_update.emit(status_reply.arguments()[0].lower())
            self.log('connection successful')
        else:
            self.log('connection to', self.mpris_name, 'failed!')

    def disconnect_from_player(self):
        self.log('disconnecting from', self.mpris_name)
        QDBusConnection.sessionBus().disconnect('org.mpris.MediaPlayer2.%s' % self.mpris_name, '/org/mpris/MediaPlayer2',
                                                'org.freedesktop.DBus.Properties', 'PropertiesChanged',
                                                self.properties_change)
        self.player = None
        self.player_controller = None
        meta_data = {
            'title': '',
            'album': '',
            'artist': '',
            'path': '',
            'duration': 0.0,
            'position': 0.0,
            'album_pix_map': QPixmap()
        }
        self.song_update.emit(meta_data)
        self.player_state_update.emit('stopped')

    @pyqtSlot(QDBusMessage)
    def properties_change(self, *args):
        data = args[0].arguments()[1]
        try:  # METADATA UPDATE
            metadata = data['Metadata']
            is_update = False
            try:
                for key in metadata.keys():
                    if self.current_properties['Metadata'][key] != metadata[key]:
                        # filter weird length changes
                        if str(key) == 'mpris:length':
                            if abs(self.current_properties['Metadata'][key] - metadata[key]) < 1000000:
                                continue
                        else:
                            is_update = True
            except KeyError:
                is_update = True

            if is_update:
                self.current_properties['Metadata'] = data['Metadata']
                self.relay_metadata(metadata)
        except KeyError:
            pass
        try:   # PLAYBACK-STATUS UPDATE
            playback_status = data['PlaybackStatus']
            if self.current_properties['PlaybackStatus'] != playback_status:
                self.current_properties['PlaybackStatus'] = playback_status
                self.player_state_update.emit(playback_status.lower())
        except KeyError:
            pass

    def relay_metadata(self, metadata):
        pos = self.get_position()
        duration = (float(metadata['mpris:length']) * self.time_multiplier) / 1000000 \
            if 'mpris:length' in metadata else 0.0
        title = metadata['xesam:title'] if 'xesam:title' in metadata else ''
        album = metadata['xesam:album'] if 'xesam:album' in metadata else ''
        try:
            artist = metadata['xesam:artist'][0]
        except (KeyError, IndexError):
            try:
                artist = metadata['xesam:artists'][0]
            except (KeyError, IndexError):
                artist = ''
        uri = metadata['xesam:url'] if 'xesam:url' in metadata else ''
        art_uri = metadata['mpris:artUrl'] if 'mpris:artUrl' in metadata else ''
        if uri.startswith('file://'):
            uri = urllib.parse.unquote(uri).replace('file://', '')
        if art_uri.startswith('file://'):
            art_uri = urllib.parse.unquote(art_uri).replace('file://', '')
            pix_map = QPixmap(art_uri)
        else:
            pix_map = QPixmap()
            try:
                pix_map.loadFromData(urllib.request.urlopen(art_uri).read())
            except (urllib.error.HTTPError, ValueError) as e:
                self.log('error:', e)
        meta_data = {
            'title': title,
            'album': album,
            'artist': artist,
            'path': uri,
            'duration': duration,
            'position': pos,
            'album_pix_map': pix_map
        }
        self.song_update.emit(meta_data)

    def get_position(self):
        if self.player is not None and self.player.isValid():
            position = self.player.call('Get', 'org.mpris.MediaPlayer2.Player', 'Position').arguments()[0]
            return (position * self.time_multiplier) / 1000000
        return 0.0

    def close(self):
        self.player_controller.call('Quit')

    def raise_player_window(self):
        self.player_controller.call('Raise')

    def next(self):
        self.player_controller.call('Next')

    def prev(self):
        self.player_controller.call('Previous')

    def quit(self):
        self.log(self.mpris_name, 'quit requested')
        self.quit_requested = True
        self.disconnect_from_player()
        self.log(self.mpris_name, 'quit')
