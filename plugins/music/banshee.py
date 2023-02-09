from plugins.music.music_player import MusicPlayerPlugin, MPRISMusicPlayerPlugin


class BansheePlugin(MPRISMusicPlayerPlugin):
    def __init__(self):
        super(BansheePlugin, self).__init__(mpris_name='banshee')

    def setup(self):
        pass

    @staticmethod
    def get_player_icon():
        return MusicPlayerPlugin.get_player_icon(gtk_icon_name='media-player-banshee')

    def open_player(self):
        if self.dbus.player is not None:
            self.dbus.raise_player_window()

