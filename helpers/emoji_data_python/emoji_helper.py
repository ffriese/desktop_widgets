import json
import os
import re
from enum import Enum
from typing import List, Dict

from PyQt5.QtCore import QRect
from PyQt5.QtGui import QPixmap

from helpers.emoji_data_python.emoji_char import EmojiChar
from helpers.tools import PathManager, time_method


class EmojiHelper:

    class Variant(Enum):
        APPLE = 'apple'
        GOOGLE = 'google'

    _emoji_data = None
    _char_to_emoji_char: Dict[str, EmojiChar] = {}
    _emoji_short_names: Dict[str, EmojiChar] = {}
    _sheets_: {str: QPixmap} = {}
    selected_variant = Variant.GOOGLE
    _regex = None

    @classmethod
    def get_source_pixmap(cls, icon_size: int, variant: Variant = None) -> QPixmap:
        if variant is None:
            variant = cls.selected_variant
        sheet_name = f'{variant.value}_{icon_size}'
        if sheet_name not in cls._sheets_:
            file = PathManager.get_emoji_path(f'sheet_{sheet_name}.png')
            # print(f"loading {file} (exists: {os.path.isfile(file)}, {os.path.getsize(file)})")
            cls._sheets_[sheet_name] = QPixmap(file)
            # print(f"loaded {PathManager.get_emoji_path(f'sheet_{sheet_name}.png')}")
        if sheet_name in cls._sheets_:
            return cls._sheets_[sheet_name]

    @classmethod
    def obtain_single_image(cls, icon_size: int, sheet_x: int, sheet_y: int, variant: Variant = None) -> QPixmap:
        x = (sheet_x * (icon_size + 2)) + 1
        y = (sheet_y * (icon_size + 2)) + 1
        return cls.get_source_pixmap(icon_size, variant).copy(QRect(x, y, icon_size, icon_size))

    @classmethod
    def obtain_image_from_unicode(cls, icon_size: int, char: str, variant: Variant = None) -> QPixmap:

        if char in cls._char_to_emoji_char:
            emoji_char = cls._char_to_emoji_char[char]
            return cls.obtain_single_image(icon_size, emoji_char.sheet_x, emoji_char.sheet_y, variant)

    @classmethod
    def get_emoji_char_from_unicode(cls, char: str) -> EmojiChar:
        if char in cls._char_to_emoji_char:
            return cls._char_to_emoji_char[char]

    @classmethod
    def get_emoji_data(cls) -> List[EmojiChar]:
        if not cls._emoji_data:
            cls.initialize()

        return cls._emoji_data

    # ################################################### #
    # Adapted from emoji_data_python                      #
    #######################################################
    @classmethod
    def get_emoji_regex(cls):
        if cls._regex is None:
            # Sort emojis by length to make sure multi-character emojis are
            # matched first
            emojis = sorted([emoji.char for emoji in cls._emoji_data], key=len, reverse=True)
            cls._regex = re.compile("(" + "|".join(re.escape(u) for u in emojis) + ")")
        return cls._regex

    # ################################################### #
    # Adapted from emoji_data_python                      #
    # needs to load custom (current) json file            #
    # ################################################### #
    @classmethod
    def initialize(cls):

        # Read json data on module load to be cached
        with open(os.path.join(os.path.dirname(__file__), '../../resources/emojis/emoji.json'), "r") as full_data:
            # Load and parse emoji data from json into EmojiChar objects
            cls._emoji_data: List[EmojiChar] = [EmojiChar(data_blob) for data_blob in json.loads(full_data.read())]

        # Build a cached dictionary of short names for quicker access, short code keys are normalized with underscores
        cls._emoji_short_names = {emoji.short_name.replace("-", "_"): emoji for emoji in cls._emoji_data}

        cls._char_to_emoji_char = {}
        for emoji in cls._emoji_data:
            cls._char_to_emoji_char[emoji.char] = emoji
            for var in emoji.skin_variations.values():
                cls._char_to_emoji_char[var.char] = var

        # Add other short names if they are not already used as a primary short name for another emoji
        for emoji in cls._emoji_data:
            for short_name in emoji.short_names:
                if short_name not in cls._emoji_short_names:
                    cls._emoji_short_names[short_name] = emoji


EmojiHelper.initialize()
