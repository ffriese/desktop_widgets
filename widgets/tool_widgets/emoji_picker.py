import re
import time
from collections import defaultdict
from datetime import datetime
from functools import partial
from typing import Union, List

import emoji
from PyQt5.QtCore import pyqtSignal, Qt, QSize
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QHBoxLayout, QTabWidget, QLabel, QListWidget, QListWidgetItem, QButtonGroup, \
    QVBoxLayout, QSpacerItem, QSizePolicy, QToolButton

from helpers import styles
from helpers.emoji_data_python.emoji_char import EmojiChar
from helpers.emoji_data_python.emoji_helper import EmojiHelper
from helpers.settings_storage import SettingsStorage
from widgets.tool_widgets.dialogs.custom_dialog import CustomWindow


class EmojiPicker(CustomWindow):
    _RECENT = '_recent_emojis'
    _EMOJI_SKIN_COLOR = '_emoji_skin_color'
    _recently_used_emojis = defaultdict(lambda: {'count': 0, 'last_access': datetime.now().date()},
                                        SettingsStorage.load_or_default(_RECENT, {}))
    _current_emoji_skin_color = SettingsStorage.load_or_default(_EMOJI_SKIN_COLOR, None)
    CATEGORIES = {
        'Recent': '🕗',
        'Activities': '⚽',
        'Animals & Nature': '🐕',
        'Flags': '🏳️',
        'Food & Drink': '🍽️',
        'Objects': '💡',
        'People & Body': '🙋\u200d♂️',
        'Smileys & Emotion': '🙃',
        'Symbols': '🔣',
        'Travel & Places': '✈️',
    }

    emoji_picked = pyqtSignal(QIcon, str)

    def __init__(self, parent=None):
        super().__init__(parent=parent, flags=Qt.WindowCloseButtonHint)
        self.setWindowTitle('Pick Icon')
        self.setWindowIcon(self.get_emoji_icon_from_unicode('🐨', 32))
        self.setStyleSheet(styles.get_style('darkblue'))
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(2, 2, 2, 2)
        self.tabWidget = QTabWidget(self)
        self.tabWidget.setContentsMargins(2, 2, 2, 2)
        self.tabWidget.setIconSize(QSize(32, 32))
        self.tabWidget.setStyleSheet("QTabBar::tab:!selected"
                                     " { padding: 2px; margin: 2px; "
                                     "   width: 30px; height: 30px; font-size: 8pt; }"
                                     "QTabBar::tab:selected"
                                     " { padding: 2px; margin: 2px; "
                                     "   width: 30px; height: 30px; font-size: 8pt; }")
        self.resize(600, 500)
        self.loading_indicator = QLabel('... loading emojis ...')
        self.layout.addWidget(self.tabWidget)
        self.layout.addWidget(self.loading_indicator)
        self.loading_indicator.hide()

        self.recent_widget = QListWidget(self)
        self.recent_widget.setViewMode(QListWidget.IconMode)
        self.recent_widget.setIconSize(QSize(32, 32))
        self.recent_widget.setResizeMode(QListWidget.Adjust)
        self.recent_widget.setDragEnabled(False)
        self.recent_widget.setAcceptDrops(False)
        self.recent_widget.itemClicked.connect(self.selection_changed)
        self.recent_widget.itemDoubleClicked.connect(self.selection_complete)

        self.tabWidget.addTab(self.recent_widget, 'Recent')
        self.tabWidget.setTabIcon(0, self.get_emoji_icon_from_unicode(self.CATEGORIES['Recent'], 32))
        self.tabWidget.setTabText(0, '')

        self.category_tabs: List[QListWidget] = []

        self.skin_color_layout = QHBoxLayout(self)
        self.skin_color_group = QButtonGroup()
        self.skin_color_group.setExclusive(True)
        self.skin_color_emoji_char = EmojiHelper.get_emoji_char_from_unicode('✋')
        self.layout.addLayout(self.skin_color_layout)
        self.skin_color_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Ignored))

        def add_skin_color_button(emoji_char: EmojiChar, variation_name: Union[str, None], checked=False):
            bt = QToolButton()
            bt.setCheckable(True)
            bt.setChecked(checked)
            bt.setStyleSheet("""
                QToolButton:checked {
                    border: none;
                    background-color: rgba(255,255,255,50);
                    border-radius: 4px;
                }
                QToolButton:!checked {
                    border: none;
                }
            """)
            bt.setIconSize(QSize(32, 32))
            bt.setMaximumWidth(34)
            bt.setFixedSize(32, 32)
            bt.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
            bt.setFixedWidth(34)
            bt.setBaseSize(34, 34)
            bt.setIcon(QIcon(EmojiHelper.obtain_single_image(32, emoji_char.sheet_x, emoji_char.sheet_y)))
            bt.clicked.connect(partial(self.skin_color_changed, variation_name=variation_name))
            self.skin_color_layout.addWidget(bt)
            self.skin_color_group.addButton(bt)

        add_skin_color_button(self.skin_color_emoji_char, None, checked=self._current_emoji_skin_color is None)
        for variation, var_emoji_char in self.skin_color_emoji_char.skin_variations.items():
            add_skin_color_button(var_emoji_char, variation, checked=self._current_emoji_skin_color == variation)

        self.skin_color_layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Expanding, QSizePolicy.Ignored))

        self.setLayout(self.layout)
        self._press_time = time.time()

        self.add_emojis()

    def skin_color_changed(self, variation_name):
        self.__class__._current_emoji_skin_color = variation_name
        SettingsStorage.save(self._current_emoji_skin_color, self._EMOJI_SKIN_COLOR)
        self.update_emoji_variations()

    def done_creating(self):
        self.loading_indicator.hide()
        self.tabWidget.show()
        self.add_emojis()

    @staticmethod
    def split_summary(summary: str) -> (Union[str, None], str):
        if summary is None:
            return None, None
        emojis = re.findall(r'^:.*?:', emoji.demojize(summary))
        if emojis:
            found_emoji = emoji.emojize(emojis[0])
            return found_emoji, summary.replace(found_emoji, '', 1)
        else:
            return None, summary

    @staticmethod
    def get_emoji_icon_from_unicode(code: str, size: int) -> QIcon:
        if size > 20:
            sheet_size = 32
        elif size > 16:
            sheet_size = 20
        else:
            sheet_size = 16
        pixmap = EmojiHelper.obtain_image_from_unicode(sheet_size, code)
        if sheet_size != size:
            return QIcon(pixmap.scaled(size, size))
        else:
            return QIcon(pixmap)

    @classmethod
    def save_recent(cls):
        SettingsStorage.save(dict(cls._recently_used_emojis), cls._RECENT)

    def update_recent(self):
        self.recent_widget.clear()
        none_item = QListWidgetItem(QIcon(), 'None')
        none_item.setFont(QFont('Calibri', 8, 1, False))
        none_item.setTextAlignment(Qt.AlignVCenter)
        none_item.setSizeHint(QSize(36, 36))
        none_item.setData(Qt.UserRole, None)
        self.recent_widget.addItem(none_item)
        if EmojiPicker._recently_used_emojis:
            for em in sorted(EmojiPicker._recently_used_emojis,
                             key=lambda x: EmojiPicker._recently_used_emojis[x]['count'],
                             reverse=True):
                emoji_char = EmojiHelper.get_emoji_char_from_unicode(em)
                item = QListWidgetItem(self.get_emoji_icon_from_unicode(em, 32), None)
                item.setData(Qt.UserRole, emoji_char)
                item.setToolTip(emoji_char.short_name)
                self.recent_widget.addItem(item)

    def update_emoji_variations(self):
        for category_tab in self.category_tabs:
            for i in range(category_tab.count()):
                item = category_tab.item(i)
                emoji_char = item.data(Qt.UserRole)
                if emoji_char.skin_variations:
                    item.setIcon(self.get_variation_icon(emoji_char))

    def get_variation_emoji_char(self, emoji_char: EmojiChar):
        if self._current_emoji_skin_color is not None and \
                self._current_emoji_skin_color in emoji_char.skin_variations:
            char = emoji_char.skin_variations[self._current_emoji_skin_color]
            char.short_name = emoji_char.short_name
            return char
        else:
            return emoji_char

    def get_variation_icon(self, emoji_char: EmojiChar, size=32) -> QIcon:
        variation_char = self.get_variation_emoji_char(emoji_char)
        return QIcon(EmojiHelper.obtain_single_image(size,
                                                     variation_char.sheet_x,
                                                     variation_char.sheet_y))

    def add_emojis(self):
        self.category_tabs = []
        cat_lists = {}
        for emoji_char in sorted(EmojiHelper.get_emoji_data(), key=lambda x: x.sort_order):
            cat = emoji_char.category
            if cat == 'Component':  # filter out modifiers (skin-color etc.)
                continue
            if cat not in cat_lists.keys():
                cat_lists[cat] = QListWidget(self)
                cat_lists[cat].setViewMode(QListWidget.IconMode)
                cat_lists[cat].setIconSize(QSize(32, 32))
                cat_lists[cat].setDragEnabled(False)
                cat_lists[cat].setAcceptDrops(False)
                cat_lists[cat].setResizeMode(QListWidget.Adjust)
                cat_lists[cat].itemClicked.connect(self.selection_changed)
                cat_lists[cat].itemDoubleClicked.connect(self.selection_complete)
                self.category_tabs.append(cat_lists[cat])

            item = QListWidgetItem(self.get_variation_icon(emoji_char), None)

            item.setData(Qt.UserRole, emoji_char)

            item.setToolTip(emoji_char.short_name)
            cat_lists[cat].addItem(item)
        for c, w in cat_lists.items():
            tb_idx = self.tabWidget.addTab(w, c)
            self.tabWidget.setTabIcon(tb_idx, self.get_emoji_icon_from_unicode(self.CATEGORIES[c], 32))
            self.tabWidget.setTabText(tb_idx, '')

        self.update_recent()

    def emit_selection(self, item: QListWidgetItem):
        emoji_char = item.data(Qt.UserRole)
        if emoji_char:
            icon = self.get_variation_icon(emoji_char)
            char = self.get_variation_emoji_char(emoji_char).char
            self._recently_used_emojis[char]['count'] += 1
            self._recently_used_emojis[char]['last_access'] = datetime.now().date()
            self.save_recent()
            self.update_recent()
        else:
            icon = QIcon()
            char = ''
        self.emoji_picked.emit(icon, char)

    def selection_complete(self, item: QListWidgetItem):
        self.emit_selection(item)
        self.hide()

    def selection_changed(self, item: QListWidgetItem):
        self.emit_selection(item)

    def closeEvent(self, event):
        self.hide()


