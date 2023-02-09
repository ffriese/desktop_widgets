from plugins.music.music_player import MPRISMusicPlayerPlugin, MusicPlayerPlugin


class SpotifyPlugin(MPRISMusicPlayerPlugin):

    def __init__(self):
        super(SpotifyPlugin, self).__init__(mpris_name='spotify')

    def setup(self):
        super(SpotifyPlugin, self).setup()

    @staticmethod
    def get_player_icon():
        return MusicPlayerPlugin.get_player_icon(gtk_icon_name='spotify-client')

    def get_current_position(self):
        return None

    def open_player(self):
        if self.dbus.player is not None:
            self.dbus.raise_player_window()
