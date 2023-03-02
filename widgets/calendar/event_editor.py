from datetime import datetime, timedelta
from typing import List, Dict, Any, Union

from PyQt5.QtCore import pyqtSignal, Qt, QTimeZone, QDateTime
from PyQt5.QtGui import QIcon, QCloseEvent, QColor
from PyQt5.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QComboBox, QCheckBox, \
    QDateTimeEdit, QLabel, QTextEdit, QMessageBox, QRadioButton, QButtonGroup

from helpers import styles
from helpers.tools import PathManager
from plugins.calendarplugin.calendar_plugin import Event, Calendar, CalendarAccessRole, EventInstance
from widgets.base import BaseWidget
from widgets.tool_widgets import FilteringComboBox, EmojiPicker
from widgets.tool_widgets.dialogs.custom_dialog import CustomWindow
from widgets.tool_widgets.recurrence_selector import RecurrenceSelector


class EventEditor(CustomWindow):
    accepted = pyqtSignal(Event)
    closed = pyqtSignal()

    def __init__(self, parent: BaseWidget, calendars: List[Calendar], event_colors: Dict[Any, Dict[str, QColor]]):
        # noinspection PyTypeChecker
        super().__init__(parent=parent, flags=Qt.WindowCloseButtonHint)#, flags=Qt.Window)
        self.emoji_picker = None  # EmojiPicker(self)
        self.setStyleSheet(styles.get_style('darkblue'))
        self.setWindowIcon(QIcon(PathManager.get_icon_path('edit_event.png')))
        self.calendars = calendars
        self.event_colors = event_colors
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.layout = QFormLayout()
        self.event = None

        ###
        #   EVENT TITLE
        ###
        self.summary = QLineEdit()
        self.icon_button = QPushButton('')
        self.icon_button.clicked.connect(self.pick_emoji)
        self.icon_button.setStyleSheet('QPushButton{min-width:26px;min-height:26px}')
        self.emoji_code = None
        self.summary_layout = QHBoxLayout()
        self.summary_layout.addWidget(self.icon_button)
        self.summary_layout.addWidget(self.summary)

        ###
        #   EVENT LOCATION
        ###
        self.location = QLineEdit()

        ###
        #   TIMEZONE
        ###
        self.timezone = FilteringComboBox()
        for tz in QTimeZone.availableTimeZoneIds():
            self.timezone.addItem(tz.data().decode())
        self.timezone.setCurrentText(QTimeZone.systemTimeZoneId().data().decode())

        ###
        #   CALENDAR SELECTION
        ###
        self.calendar = QComboBox()
        for cal in self.calendars:
            if cal.access_role in [CalendarAccessRole.OWNER, CalendarAccessRole.WRITER]:
                self.calendar.addItem(cal.name)
        for cal in self.calendars:
            if cal.primary:
                self.calendar.setCurrentText(cal.name)
        ####
        #   EVENT TIME
        ####
        self.time_layout = QHBoxLayout()
        self.all_day = QCheckBox()
        self.all_day.stateChanged.connect(self.all_day_changed)
        self.start_time = QDateTimeEdit()
        self.start_time.setCalendarPopup(True)
        self.start_time.setDateTime(datetime.now())
        self.end_time = QDateTimeEdit()
        self.end_time.setCalendarPopup(True)
        self.end_time.setDateTime(datetime.now() + timedelta(hours=1))
        self.time_diff = timedelta(milliseconds=self.start_time.dateTime().msecsTo(self.end_time.dateTime()))
        self.start_time.dateTimeChanged.connect(self.time_changed)
        self.end_time.dateTimeChanged.connect(self.time_changed)

        self.time_layout.addWidget(self.start_time)
        self.time_layout.addWidget(QLabel('  -'))
        self.time_layout.addWidget(self.end_time)
        self.time_layout.addWidget(QLabel('All Day:'))
        self.time_layout.addWidget(self.all_day)

        ####
        #  CUSTOM EVENT COLOR
        ###
        self.custom_color_cb = QCheckBox()
        self.custom_color_cb.stateChanged.connect(self.color_enabled_changed)
        self.custom_color_widget = QWidget()
        self.custom_color_layout = QHBoxLayout()
        self.color_radio_button_group = QButtonGroup()
        self.color_radio_buttons = {}
        for color_id, color in self.event_colors.items():
            if color_id is not None:
                rb = QRadioButton()
                rb.setProperty('color_id', color_id)
                rb.setProperty('color', color['bg_color'])
                rb.setStyleSheet(f"QRadioButton::indicator:checked {{"
                                 f"background-color: {color['bg_color'].name()};"
                                 f"color: {color['bg_color'].name()};"
                                 f"border: 2px solid{color['bg_color'].name()};}}"
                                 f"QRadioButton::indicator:unchecked {{"
                                 f"background-color: {color['fg_color'].name()};"
                                 f"color: {color['bg_color'].name()};"
                                 f"border: 2px solid {color['bg_color'].name()};}}"
                                 f"QRadioButton::indicator {{"
                                 f"width:10px;"
                                 f"height:10px;"
                                 f"border-radius:7px;}}"
                                 )
                self.color_radio_buttons[color_id] = rb
                self.color_radio_button_group.addButton(rb)
                self.custom_color_layout.addWidget(rb)

        self.custom_color_widget.setLayout(self.custom_color_layout)

        ####
        #    RECURRING EVENT SETTINGS
        ####
        self.recurring = QCheckBox()
        self.recurring.stateChanged.connect(self.recurring_changed)

        self.recurring_widget = RecurrenceSelector()


        ###
        #   EVENT DESCRIPTION
        ###
        self.description = QTextEdit()

        ###
        #   SUBMIT BUTTON
        ###
        self.accept_button = QPushButton('Submit changes')
        self.accept_button.setIcon(QIcon(PathManager.get_icon_path('submit_event.png')))
        self.accept_button.clicked.connect(self.accept_button_clicked)

        ###
        #      LAYOUT COMPOSITION
        ###
        self.layout.addRow("Summary:", self.summary_layout)
        self.layout.addRow("Time:", self.time_layout)
        self.layout.addRow("Location:", self.location)
        self.layout.addRow("Time Zone:", self.timezone)
        self.layout.addRow("Calendar:", self.calendar)
        self.layout.addRow("Recurring:", self.recurring)
        self.layout.addRow("Event Color:", self.custom_color_cb)
        self.layout.addRow("Description:", self.description)
        self.layout.addWidget(self.accept_button)
        self.setLayout(self.layout)

    def all_day_changed(self, enabled):
        if enabled:
            self.start_time.setDisplayFormat('dd.MM.yy          ')
            self.end_time.setDisplayFormat('dd.MM.yy          ')
        else:
            self.start_time.setDisplayFormat('dd.MM.yy hh:mm  ')
            self.end_time.setDisplayFormat('dd.MM.yy hh:mm  ')
        self.repaint()

    def recurring_changed(self, enabled):
        self._set_config_part_enabled(self.recurring, self.recurring_widget, enabled)

    def color_enabled_changed(self, enabled):
        self._set_config_part_enabled(self.custom_color_cb, self.custom_color_widget, enabled)

    def _set_config_part_enabled(self, checkbox, widget, enabled):
        # if enabled:
        #     self.layout.insertRow(self.layout.getWidgetPosition(checkbox)[0]+1, "", widget)
        # else:
        #     self.layout.takeRow(self.layout.getWidgetPosition(checkbox)[0]+1)
        # widget.setVisible(enabled)
        self._set_layout_row_enabled(self.layout, checkbox, widget, enabled)

    def _set_layout_row_enabled(self, form_layout, widget_above, widget, enabled):
        if enabled:
            form_layout.insertRow(form_layout.getWidgetPosition(widget_above)[0]+1, "", widget)
        else:
            form_layout.takeRow(form_layout.getWidgetPosition(widget_above)[0]+1)
        if isinstance(widget, QWidget):
            widget.setVisible(enabled)


    def set_time(self, start, end):
        self.blockSignals(True)
        self.start_time.setDateTime(start)
        self.end_time.setDateTime(end)
        self.blockSignals(False)

    def time_changed(self, new_time: QDateTime):
        if self.sender() == self.start_time:
            self.end_time.setDateTime(new_time.toPyDateTime() + self.time_diff)
        else:
            if new_time < self.start_time.dateTime():
                self.start_time.setDateTime(new_time.toPyDateTime() - self.time_diff)
            self.time_diff = timedelta(
                    milliseconds=self.start_time.dateTime().msecsTo(self.end_time.dateTime()))

    def root_event(self) -> Event:
        if isinstance(self.event, Event):
            return self.event
        elif isinstance(self.event, EventInstance):
            return self.event.root_event

    def event_instance(self) -> Event:
        if isinstance(self.event, Event):
            return self.event
        elif isinstance(self.event, EventInstance):
            return self.event.instance


    def set_event(self, event: Union[Event, EventInstance]):
        self.setWindowTitle('Edit Event')

        self.event = event

        if isinstance(self.event, EventInstance):
            rec_id = self.event_instance().recurring_event_id
            print('recurring single instance, lock recurring settings')
            self.recurring.setEnabled(False)
        else:
            if self.root_event().recurrence is not None:
                self.recurring.setChecked(True)
                self.recurring_widget.set_recurrence(self.root_event().recurrence)

        # TODO: REUSE EMOJI PICKER
        self.summary.setText(self.event_instance().title)
        icon, summary = EmojiPicker.split_summary(self.event_instance().title)
        self.summary.setText(summary)
        self.emoji_code = icon
        if icon is not None:
            self.icon_button.setIcon(EmojiPicker.get_emoji_icon_from_unicode(icon, 32))

        self.start_time.setDateTime(self.event_instance().start)
        self.end_time.setDateTime((self.event_instance().end - timedelta(days=1)) if self.event_instance().all_day
                                  else self.event_instance().end)
        self.all_day.setChecked(self.event_instance().all_day)
        self.location.setText(self.event_instance().location)
        if self.event_instance().timezone is not None:
            timezone = self.event_instance().timezone.replace('GMT', 'UTC')
            start = self.start_time.dateTime()
            end = self.end_time.dateTime()
            self.start_time.setDateTime(start.toTimeZone(QTimeZone(timezone.encode())))
            self.end_time.setDateTime(end.toTimeZone(QTimeZone(timezone.encode())))
            self.timezone.setCurrentText(timezone)

        try:
            self.description.setText(self.event_instance().description)
        except KeyError:
            pass
        try:
            self.calendar.setCurrentText(self.event_instance().calendar.name)
        except KeyError:
            pass
        if self.event_instance().bg_color is not None:
            self.custom_color_cb.setChecked(True)
            for color_id, color in self.event_colors.items():
                if color_id is not None and color['bg_color'].name() == self.event_instance().bg_color.name():
                    self.color_radio_buttons[color_id].setChecked(True)

    def _calendar_info_from_name(self, calendar_name):
        for calendar in self.calendars:
            if calendar.name == calendar_name:
                return calendar.id, calendar.bg_color, calendar.fg_color

    def calendar_from_name(self, calendar_name):

        for calendar in self.calendars:
            if calendar.name == calendar_name:
                return calendar

    def get_bg_color(self):
        if self.custom_color_cb.isChecked():
            checked_button = self.color_radio_button_group.checkedButton()
            if checked_button is not None:
                return checked_button.property('color')
        else:
            return None

    def accept_button_clicked(self):
        if not QTimeZone.isTimeZoneIdAvailable(self.timezone.currentText().encode()):
            QMessageBox.warning(self, 'Invalid Event', '"%s" is not a valid time zone ID' % self.timezone.currentText(),
                                QMessageBox.Ok)
            return

        event_title = self.summary.text()
        if self.emoji_code is not None:
            event_title = self.emoji_code + event_title
        if self.event is None:
            event = Event(event_id=None,
                          title=event_title,
                          start=self.start_time.dateTime().toPyDateTime(),
                          end=(self.end_time.dateTime().toPyDateTime() + timedelta(days=1)) if self.all_day.isChecked()
                          else self.end_time.dateTime().toPyDateTime(),
                          location=self.location.text(),
                          description=self.description.toPlainText(),
                          all_day=self.all_day.isChecked(),
                          calendar=self.calendar_from_name(calendar_name=self.calendar.currentText()),
                          timezone=self.timezone.currentText(),
                          bg_color=self.get_bg_color(),
                          recurrence=self.get_recurrence(),
                          data={})
            self.accepted.emit(event)
        else:

            if isinstance(self.event, EventInstance):
                if self.event.instance_id not in self.event.root_event.subcomponents:
                    # we need to create a subcomponent. easy as that.
                    self.event.root_event.subcomponents[self.event.instance_id] = self.event.instance

                # subcomponent exists! we only need to edit it :)
                self.set_event_data_to_edited_data(
                    self.event.root_event.subcomponents[self.event.instance_id],
                    event_title=event_title)

                # emit root event
                self.accepted.emit(self.event.root_event)
            else:
                # just work directly on the current event
                self.set_event_data_to_edited_data(self.event, event_title=event_title)
                self.accepted.emit(self.event)
        self.close()

    def set_event_data_to_edited_data(self, event: Event, event_title: str):
        event.title = event_title
        event.location = self.location.text()
        event.description = self.description.toPlainText()
        event.timezone = self.timezone.currentText()
        event.all_day = self.all_day.isChecked()
        event.start = self.start_time.dateTime().toPyDateTime()
        if event.all_day:
            # all-day end-times are non-inclusive
            event.end = (self.end_time.dateTime().toPyDateTime() + timedelta(days=1))
        else:
            event.end = self.end_time.dateTime().toPyDateTime()
        event.calendar = self.calendar_from_name(calendar_name=self.calendar.currentText())
        event.bg_color = self.get_bg_color()
        event.recurrence = self.get_recurrence()


    def get_recurrence(self):
        if self.recurring.isChecked():
            return self.recurring_widget.get_rrule()
        return None

    def closeEvent(self, ev: QCloseEvent) -> None:
        super().closeEvent(ev)
        self.closed.emit()

    def update_emoji(self, emoji, code):
        self.icon_button.setIcon(emoji)
        self.emoji_code = code

    def pick_emoji(self):
        if self.emoji_picker is None:
            self.emoji_picker = EmojiPicker(self)
            self.emoji_picker.emoji_picked.connect(self.update_emoji)
        self.emoji_picker.update_recent()
        self.emoji_picker.show()
