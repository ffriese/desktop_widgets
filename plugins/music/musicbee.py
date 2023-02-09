import time
from typing import Union

from PyQt5.QtGui import QPixmap

from plugins.music.music_player import MusicPlayerPlugin
from plugins.third_party.musicbeeipc import MusicBeeIPC
from plugins.third_party.musicbeeipc.enums import *
from threading import Thread


class MusicBeePlugin(MusicPlayerPlugin):
    def update_synchronously(self, *args, **kwargs) -> Union[object, None]:
        pass

    def __init__(self):
        super(MusicBeePlugin, self).__init__()
        self.music_bee = None
        self.polling_thread = None
        self.running = False
        self.curr_song = None
        self.curr_state = None
        self.curr_pos = None

    def setup(self):
        self.music_bee = MusicBeeIPC()
        self.running = True

    def start(self):
        self.polling_thread = Thread(target=self.poll)
        self.polling_thread.start()

    def poll(self):
        while self.running:
            if self.music_bee.probe():
                state = self.music_bee.get_play_state_str().lower()
                pos = self.music_bee.position/1000.0
                song = {
                    'title:': self.music_bee.get_file_tag(MBMD_TrackTitle),
                    'artist': self.music_bee.get_file_tag(MBMD_Artist),
                    'album': self.music_bee.get_file_tag(MBMD_Album)
                }
                if song != self.curr_song:
                    self.curr_song = song
                    song = {
                        **song,
                        'position': pos,
                        'duration': self.music_bee.get_duration()/1000.0,
                        'path': self.music_bee.get_file_url(),
                        'album_pix_map': QPixmap(self.music_bee.get_artwork_url())
                    }
                    self.song_update.emit(song)
                    print(song)
                if pos != self.curr_pos:
                    self.curr_pos = pos
                    self.pos_update.emit(pos)
                if state != self.curr_state:
                    self.curr_state = state
                    self.player_state_update.emit(state)
            else:
                time.sleep(1)
            time.sleep(.1)

    def open_player(self):
        self.music_bee.window_bring_to_front()

    def close_player(self):
        self.music_bee.window_close()

    def quit(self):
        self.running = False

    def get_current_position(self):
        return self.music_bee.get_position()/1000.0

