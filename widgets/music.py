from widgets.base import BaseWidget
from PyQt5.QtCore import *
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5 import QtCore
import math
from mutagen.id3 import ID3, SYLT
import importlib

from helpers.tools import PathManager


class MusicWidget(BaseWidget):
    def __init__(self):
        super(MusicWidget, self).__init__()

        # CONFIGURABLE PLUGINS (PLAYER, LYRICS)
        self.player = 'MusicBee'  #None  # 'Banshee'
        self.lyrics_provider = None  # 'MiniLyrics'
        self.player_plugin = None
        self.lyrics_plugin = None

        # LYRICS EDITOR WINDOW
        self.lyrics_editor = None

        # CUSTOM ACTIONS
        self.player_action = QAction('', self)
        self.lrc_edit_action = QAction(QIcon(PathManager.get_icon_path('lyrics.png')), 'Edit Lyrics')
        self.switch_player_action = QAction('')
        self.context_menu.addAction(self.switch_player_action)
        self.switch_player_action.triggered.connect(self.change_player)
        self.context_menu.addAction(self.player_action)
        self.context_menu.addAction(self.lrc_edit_action)
        self.player_action.triggered.connect(self.open_player)
        self.lrc_edit_action.triggered.connect(self.edit_lyrics)
        self.player_action.setVisible(False)

        # SONG-VARIABLES
        self.current_song = None
        self.s_lyr = None
        self.u_lyr = None
        self.album_art_path = ''
        self.song_pos = 0.0
        self.current_duration = 0.0
        self.player_state = 'stopped'

        # LAYOUT
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # LAYOUT.INFO
        self.info_layout = QHBoxLayout()
        self.layout.addLayout(self.info_layout)

        # LAYOUT.INFO.ALBUM_ART
        self.album_art = QLabel()
        self.album_art.setMaximumSize(100, 100)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.album_art.setScaledContents(True)

        # LAYOUT.INFO.METADATA
        self.meta_data_template = "<span style='font-size:10pt; font-weight:600; color:white;'>%s<br></span>" \
                                  "<span style='font-size:9pt; font-weight:500; color:white;'>%s<br><i>%s</i></span>"
        self.meta_data = QLabel(self.meta_data_template % ('', '', ''))
        self.meta_data.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.meta_data.setWordWrap(True)
        self.meta_layout = QVBoxLayout()
        self.info_layout.addWidget(self.album_art)
        self.info_layout.addLayout(self.meta_layout)
        self.meta_layout.addWidget(self.meta_data)

        # LAYOUT.PROGRESS
        self.progress_layout = QHBoxLayout()
        self.layout.addLayout(self.progress_layout)

        self.progressbar = QProgressBar()
        self.progressbar.setMaximumHeight(12)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.progressbar.setTextVisible(False)
        self.progressbar.setStyleSheet("QProgressBar {border: 1px solid black;padding: 1px;"
                                       "border-bottom-left-radius: 2px;"
                                       "border-bottom-right-radius: 2px;"
                                       "border-top-left-radius: 2px;"
                                       "border-top-right-radius: 2px;}"
                                       "QProgressBar::chunk {background-color:#41a0f4;width: 1px;}")
        self.time_template = "<span style='font-size:8pt; font-weight:500; color:white;'>%02.0f:%02.0f</span>"
        self.elapsed_lb = QLabel(self.time_template % (0.0, 0.0))
        self.duration_lb = QLabel(self.time_template % (0.0, 0.0))
        self.elapsed_lb.setMaximumWidth(38)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.elapsed_lb.setMinimumWidth(38)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.duration_lb.setMaximumWidth(38)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.duration_lb.setMinimumWidth(38)  # TODO: CONFIGURABLE OR CALCULATE FROM TEXT-SIZE
        self.progress_layout.addWidget(self.elapsed_lb)
        self.progress_layout.addWidget(self.progressbar)
        self.progress_layout.addWidget(self.duration_lb)

        # UNUSED: CONTROLS
        # self.control_layout = QHBoxLayout()
        # self.meta_layout.addLayout(self.control_layout)
        # self.next_button = QPushButton('>')
        # self.next_button.clicked.connect(self.media_next)
        # self.control_layout.addWidget(self.next_button)
        # self.lyrics_button = QPushButton('Lyrics')
        # self.lyrics_button.clicked.connect(self.lyr_win)
        # self.control_layout.addWidget(self.lyrics_button)

        # LAYOUT.LYRICS
        self.lyrics_frame = QScrollArea()
        self.layout.addWidget(self.lyrics_frame)

        self.lyrics_label = QLabel()
        self.lyrics_label.setWordWrap(True)
        self.lyrics_label.setAlignment(Qt.AlignHCenter)
        self.template = "<span style='font-size:%dpt; font-family: %s; font-weight:500; color:#41a0f4;'>" \
                        "%s" \
                        "</span><span style='font-size:%dpt; font-family: %s; font-weight:500; color:gray;'>" \
                        "%s" \
                        "</span>"
        self.lyrics_frame.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.lyrics_frame.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.lyrics_frame.setWidgetResizable(True)
        self.lyrics_frame.setStyleSheet("background-color: transparent")
        self.lyrics_frame.setWidget(self.lyrics_label)

        # TIMER
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.recurring_timer)
        self.counter = 0
        self.last_estimate = QDateTime.currentMSecsSinceEpoch()
        self.timer.start()

        # CUSTOM CONFIG-ENTRIES
        self.settings_switcher['player'] = (setattr, ['self', 'key', 'value'], str)
        self.settings_switcher['lyrics_provider'] = (setattr, ['self', 'key', 'value'], str)

    def start(self):
        super(MusicWidget, self).start()
        if self.player is None:
            self.player = 'Banshee'
            self.widget_updated.emit('player', self.player)

        if self.lyrics_provider is None:
            self.lyrics_provider = 'MiniLyrics'
            self.widget_updated.emit('lyrics_provider', self.lyrics_provider)
            lyrics_plugin_class = getattr(importlib.import_module('plugins.%s' % self.lyrics_provider.lower()),
                                          '%sPlugin' % self.lyrics_provider)
            self.register_plugin(lyrics_plugin_class, 'lyrics_plugin')

        self.load_player()

    def load_player(self):
        player_plugin_class = getattr(importlib.import_module('plugins.music.%s' % self.player.lower()),
                                      '%sPlugin' % self.player)
        self.register_plugin(player_plugin_class, 'player_plugin')

        self.player_plugin.song_update.connect(self.song_changed)
        self.player_plugin.player_state_update.connect(self.player_state_changed)
        self.player_plugin.start()
        self.player_action.setText('Open %s' % self.player)
        self.switch_player_action.setText('Switch to %s' % ('Banshee' if self.player == 'Spotify' else 'Spotify'))
        self.player_action.setVisible(True)
        try:
            icon = self.player_plugin.get_player_icon()
            if type(icon) is QIcon:
                self.player_action.setIcon(icon)
            else:
                self.player_action.setIcon(QIcon(icon.get_filename()))
        except Exception as e:
            print(e)

    @pyqtSlot()
    def change_player(self):
        self.deregister_plugin(self.player_plugin, 'player_plugin')
        if self.player == 'Banshee':
            self.player = 'Spotify'
        else:
            self.player = 'Banshee'  # player_name
        self.widget_updated.emit('player', self.player)
        self.load_player()


    @pyqtSlot()
    def open_player(self):
        self.player_plugin.open_player()

    @pyqtSlot(float)
    def position_updated(self, position):
        self.log(position)

    @pyqtSlot(dict)
    def song_changed(self, meta_data):

        self.song_pos = meta_data['position']
        self.current_duration = meta_data['duration']
        # self.album_art_path = album_path
        self.progressbar.setMaximum(self.current_duration * 1000)
        mins = math.floor(self.current_duration / 60)
        secs = self.current_duration - (60 * mins)
        self.duration_lb.setText(self.time_template % (mins, secs))
        title, album, artist = '', '', ''
        if 'open.spotify.com' in meta_data['path']:
            # self.debug('reaction to %s not yet implemented' % meta_data['path'])
            self.current_song = None
            title = meta_data['title']
            album = meta_data['album']
            artist = meta_data['artist']
        elif 'musicbee' in meta_data:
            title = meta_data['title']
            album = meta_data['album']
            artist = meta_data['artist']
        elif meta_data['path']:
            self.current_song = ID3(str(meta_data['path']))
            title = self.current_song.get("TIT2")
            artist = self.current_song.get("TPE1")
            album = self.current_song.get("TALB")

        self.meta_data.setText(self.meta_data_template % (title, artist, album))

        try:
            self.album_art.setPixmap(meta_data['album_pix_map'])
        except Exception as e:
            self.log(str(e))
            self.album_art.setPixmap(QPixmap())

        if self.current_song is not None:
            try:
                sylts = self.current_song.getall("SYLT")
                if len(sylts) < 1:
                    raise Exception('no synced lyrics')
                for sl in sylts:
                    if sl.type == 1:  # normal synced lyrics (5 = chords)
                        self.s_lyr = sl.text
                        break
                if self.s_lyr is None:
                    raise Exception('no correct lyrics found')
            except Exception as e:
                try:
                    if self.lyrics_plugin.get_lrc_for_song(self.current_song):
                        for sl in self.current_song.getall("SYLT"):
                            if sl.type == 1:  # normal synced lyrics (5 = chords)
                                self.s_lyr = sl.text
                                break
                    else:
                        self.u_lyr = self.current_song.getall("USLT")[0].text
                        self.log('used usylt')
                        self.s_lyr = None
                except Exception as e:
                    self.u_lyr = None
                    self.s_lyr = None
        else:
            pass  # Spotify does not have any progress measure accessible yet, so LRCs are unusable
            # self.u_lyr = None
            # self.s_lyr = None
            artist = 'Queens of the Stone Age'
            title = 'I Sat By The Ocean'
            self.s_lyr = self.lyrics_plugin.get_temp_lrc_for_song(artist, title)

    @pyqtSlot(str)
    def player_state_changed(self, state):
        # self.debug('state change: %s' % state)
        self.player_state = state

    @pyqtSlot()
    def media_next(self):
        print('next song')
        # app.sendEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_MediaTogglePlayPause, Qt.NoModifier))
        # QKeySequence(Qt.Key_MediaTogglePlayPause)

    # @pyqtSlot()
    # def lyr_win(self):
    #    if self.lyrics_selector is None:
    #        self.lyrics_selector = QMainWindow(self)
    #        self.lyrics_selector.setWindowTitle('Lyrics Options')
    #        self.lyrics_selector.setVisible(True)
    #        self.lyrics_selector.resize(300, 300)
    #        self.lyrics_selector.show()

    def recurring_timer(self):
        # print('timer called', self.player_state)
        if self.player_state == 'playing':
            self.counter += 1
            if self.counter > 5:
                try:
                    pos = self.player_plugin.get_current_position()
                    if pos is not None:
                        self.song_pos = float(pos)
                    else:
                        self.song_pos += float(QDateTime.currentMSecsSinceEpoch() - self.last_estimate) / 1000.0
                except Exception as e:  # banshee not running
                    self.s_lyr = None
                    self.u_lyr = None
                    self.lyrics_label.setText("<span style='font-size:10pt; font-weight:500; color:#41a0f4;'>"
                                              "Player is not running!</span>")
                    self.player_state = 'stopped'

                self.counter = 0
            else:
                # self.song_pos += float(self.timer.interval()) / 1000.0
                self.song_pos += float(QDateTime.currentMSecsSinceEpoch() - self.last_estimate) / 1000.0

        self.last_estimate = QDateTime.currentMSecsSinceEpoch()

        self.progressbar.setValue(self.song_pos * 1000)

        mins = math.floor(self.song_pos / 60)
        secs = self.song_pos - (60 * mins)
        self.elapsed_lb.setText(self.time_template % (mins, secs))

        if self.s_lyr is not None:
            elapsed = []
            pending = []

            for i in range(0, len(self.s_lyr)):
                this_pos = float(self.s_lyr[i][1] / 1000)
                this_txt = self.s_lyr[i][0]

                if self.song_pos > this_pos:
                    if i < len(self.s_lyr) - 1:
                        next_pos = float(self.s_lyr[i + 1][1] / 1000)
                    else:
                        next_pos = self.current_duration

                    if self.song_pos < next_pos:
                        perc = (self.song_pos - this_pos) \
                               / (next_pos - this_pos)
                        line_len = len(this_txt)
                        done_txt = this_txt[:round(line_len * perc)]
                        elapsed.append(done_txt)
                        pending.append(this_txt[len(done_txt):] + '<br>')

                    else:
                        elapsed.append(this_txt + '<br>')
                else:
                    pending.append(this_txt + '<br>')

            elapsed_text = ''.join(elapsed[-3:])
            pending_text = ''.join(pending)

            self.lyrics_label.setText(self.template % (self.fg_font.pointSize(), self.fg_font.family(), elapsed_text,
                                                       self.fg_font.pointSize(), self.fg_font.family(), pending_text))
        else:
            self.lyrics_label.setText("<span style='font-size:10pt; font-weight:500; color:#41a0f4;'>"
                                      "No Lyrics</span>")

    def closeEvent(self, event):
        self.deleteLater()
        if self.player_plugin is not None:
            self.log("try closing %s..." % self.player_plugin.__class__.__name__)
            self.player_plugin.quit()
            self.log("%s probably closed successfully" % self.player_plugin.__class__.__name__)
        event.accept()

    def edit_lyrics(self):
        self.lyrics_editor = LyricsEditor(self, self.current_song, self.s_lyr, self.u_lyr,
                                          player_plugin=self.player_plugin,
                                          lyrics_plugin=self.lyrics_plugin)


class LyricsEditor(QWidget):
    def __init__(self, parent=None, song=None, s_lyr=None, u_lyr=None, player_plugin=None, lyrics_plugin=None):
        super(LyricsEditor, self).__init__(parent=parent, flags=Qt.Window)
        import copy
        self.layout = QVBoxLayout()
        self.player_plugin = player_plugin
        self.song = copy.deepcopy(song)
        self.lyrics_plugin = lyrics_plugin
        self.control_layout = QHBoxLayout()
        self.sync_button = QPushButton('[...]')
        self.sync_button.setFocusPolicy(Qt.NoFocus)
        self.sync_button.clicked.connect(self.sync_and_next_line)
        self.save_lrc_button = QPushButton('Save to lrc')
        self.save_lrc_button.clicked.connect(self.save_lrc)
        self.control_layout.addWidget(self.sync_button)
        self.control_layout.addWidget(self.save_lrc_button)

        self.lrc_edit = QTextEdit()
        self.layout.addLayout(self.control_layout)
        self.layout.addWidget(self.lrc_edit)
        self.setLayout(self.layout)
        self.s_lyr = s_lyr
        self.u_lyr = u_lyr
        self.setup_text()
        self.resize(500, 700)
        self.show()

    def setup_text(self):
        if self.s_lyr is not None:
            text = ''
            for line in self.s_lyr:
                lyr = line[0]
                t = float(line[1]) / 1000.0
                minutes = math.floor(t / 60)
                seconds = math.floor(t - (minutes * 60))
                mseconds = round((t - (minutes * 60) - seconds), 2) * 100
                time = '[%02d:%02d.%02d]' % (minutes, seconds, mseconds)
                text += '%s %s\n' % (time, lyr)
            self.lrc_edit.setText(text)

        elif self.u_lyr is not None:
            self.lrc_edit.setText(self.u_lyr)

    def save_lrc(self):
        self.lyrics_plugin.write_lrc_to_song(self.song, self.lrc_edit.toPlainText())

    def sync_and_next_line(self):
        t = float(self.player_plugin.player_plugin.get_current_position())
        minutes = math.floor(t / 60)
        seconds = math.floor(t - (minutes * 60))
        mseconds = round((t - (minutes * 60) - seconds), 2) * 100
        time = '[%02d:%02d.%02d]' % (minutes, seconds, mseconds)
        cursor = self.lrc_edit.textCursor()
        line = cursor.blockNumber()
        text = self.lrc_edit.toPlainText()
        new_text = text.split('\n')
        new_text[line] = '%s%s' % (time, new_text[line])
        self.lrc_edit.setText('\n'.join(new_text))
        cursor = self.lrc_edit.textCursor()
        cursor.movePosition(QTextCursor.Down, n=line + 1)
        self.lrc_edit.setTextCursor(cursor)
