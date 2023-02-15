from datetime import datetime, timedelta
from typing import List, Dict, Any

import dateutil.rrule
from PyQt5.QtCore import pyqtSignal, Qt, QTimeZone, QDateTime
from PyQt5.QtGui import QIcon, QCloseEvent, QColor
from PyQt5.QtWidgets import QWidget, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QComboBox, QCheckBox, \
    QDateTimeEdit, QLabel, QSpinBox, QTextEdit, QMessageBox, QRadioButton, QButtonGroup
from dateutil.rrule import rrulestr

from helpers import styles
from helpers.tools import PathManager
from plugins.calendarplugin.calendar_plugin import Event, Calendar, CalendarAccessRole
from widgets.base import BaseWidget
from widgets.tool_widgets import FilteringComboBox
from widgets.tool_widgets.dialogs.custom_dialog import CustomWindow


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
        # self.icon_button = QPushButton('')
        # self.icon_button.clicked.connect(self.pick_emoji)
        # self.icon_button.setStyleSheet('QPushButton{min-width:20px;}')
        # self.emoji_code = None
        # self.emoji_file_name = None
        self.summary_layout = QHBoxLayout()
        # self.summary_layout.addWidget(self.icon_button)
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

        self.recurring_widget = QWidget()
        self.rec_lay = QFormLayout()

        self.freq_cb = ["Year(s)", "Month(s)", "Week(s)", "Day(s)"]  # , "Hour(s)", "Minute(s)", "Second(s)"]
        self._freq_list = ["YEARLY", "MONTHLY", "WEEKLY", "DAILY"]  # , "HOURLY", "MINUTELY", "SECONDLY"]

        self.repeat_layout = QHBoxLayout()
        self.repeat_interval = QSpinBox()
        self.repeat_interval.setMinimum(1)
        self.repeat_interval_unit = QComboBox()
        self.repeat_interval_unit.addItems(self.freq_cb)
        self.repeat_interval_unit.setCurrentText('Week(s)')
        self.repeat_interval_unit.currentTextChanged.connect(self.recurrence_interval_unit_changed)
        self.repeat_layout.addWidget(self.repeat_interval)
        self.repeat_layout.addWidget(self.repeat_interval_unit)

        self.detailed_repeat_layout = QHBoxLayout()
        self.detailed_repeat_day = QComboBox()
        self.detailed_repeat_type = QComboBox()
        self.detailed_repeat_type.addItems(['Every', 'On the', 'On day(s)'])
        self.detailed_repeat_type.currentTextChanged.connect(self.detailed_repeat_type_changed)
        self.detailed_repeat_rhythm = QComboBox()
        self.detailed_repeat_rhythm.addItems(['1st', '2nd', '3rd', '4th', '5th', 'Last'])
        self.detailed_repeat_rhythm.setVisible(False)
        self.detailed_repeat_day.addItems(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_type)
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_rhythm)
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_day)

        self.end_repeat_layout = QHBoxLayout()
        self.end_repeat = QComboBox()
        self.end_repeat.addItems(['Never', 'On', 'After'])
        self.end_repeat.currentTextChanged.connect(self.end_repeat_changed)
        self.end_repeat_date = QDateTimeEdit()
        self.end_repeat_date.hide()
        self.end_repeat_occurrences = QSpinBox()
        self.end_repeat_occurrences.setMinimum(2)
        self.end_repeat_occurrences.setSingleStep(1)
        self.end_repeat_occurrences.hide()
        self.end_repeat_occurrences_lb = QLabel('Occurrences')
        self.end_repeat_occurrences_lb.hide()
        self.end_repeat_layout.addWidget(self.end_repeat)
        self.end_repeat_layout.addWidget(self.end_repeat_date)
        self.end_repeat_layout.addWidget(self.end_repeat_occurrences)
        self.end_repeat_layout.addWidget(self.end_repeat_occurrences_lb)

        self.rec_lay.addRow("Every", self.repeat_layout)
        self.rec_lay.addRow('', self.detailed_repeat_layout)
        self.rec_lay.addRow("End", self.end_repeat_layout)
        self.recurring_widget.setLayout(self.rec_lay)

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

    def end_repeat_changed(self, text):
        if text == 'Never':
            self.end_repeat_date.hide()
            self.end_repeat_occurrences.hide()
            self.end_repeat_occurrences_lb.hide()
        elif text == 'After':
            self.end_repeat_date.hide()
            self.end_repeat_occurrences.show()
            self.end_repeat_occurrences_lb.show()
        else:
            self.end_repeat_date.show()
            self.end_repeat_occurrences.hide()
            self.end_repeat_occurrences_lb.hide()

    def detailed_repeat_type_changed(self, text):
        if text == 'Every':
            self.detailed_repeat_rhythm.hide()
            self.detailed_repeat_day.show()
        elif text == 'On the':
            self.detailed_repeat_rhythm.show()
            self.detailed_repeat_day.show()
        elif text == 'On day(s)':
            self.detailed_repeat_rhythm.hide()
            self.detailed_repeat_day.hide()

    def recurrence_interval_unit_changed(self, text):
        if text == 'Month(s)':
            self.rec_lay.insertRow(self.rec_lay.getLayoutPosition(self.repeat_layout)[0]+1, "",
                                   self.detailed_repeat_layout)
            for i in range(self.detailed_repeat_layout.count()):
                self.detailed_repeat_layout.itemAt(i).widget().show()
        else:
            if self.rec_lay.getLayoutPosition(self.detailed_repeat_layout)[0] == 1:
                self.rec_lay.takeRow(self.rec_lay.getLayoutPosition(self.repeat_layout)[0] + 1)
                for i in range(self.detailed_repeat_layout.count()):
                    self.detailed_repeat_layout.itemAt(i).widget().hide()

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

    def set_event(self, event: Event):
        self.setWindowTitle('Edit Event')
        self.event = event
        if self.event.recurrence is not None:
            self.recurring.setChecked(True)
            if isinstance(self.event.recurrence, dateutil.rrule.rrule):
                rule = self.event.recurrence.__dict__
            else:
                recurrence = self.event.recurrence
                rec_interval = recurrence[0]
                # print('event is recurring and editable:')
                rule = rrulestr(rec_interval).__dict__
            # print(recurrence)
            # print(rrulestr(rec_interval))
            # print(rule)

            _interval = rule['_interval']
            _freq = self.freq_cb[int(rule['_freq'])]
            _count = rule['_count']
            _until = rule['_until']

            if _count is None:
                # print(_until)
                if isinstance(_until, datetime):
                    self.end_repeat.setCurrentText('On')
                    self.end_repeat_date.setDateTime(_until)
            else:
                self.end_repeat.setCurrentText('After')
                self.end_repeat_occurrences.setValue(_count)

            self.repeat_interval.setValue(_interval)
            self.repeat_interval_unit.setCurrentText(_freq)

        else:
            if self.event.is_recurring():
                rec_id = self.event.recurring_event_id
                print('recurring single instance, lock recurring settings')
                self.recurring.setEnabled(False)

        # TODO: REUSE EMOJI PICKER
        self.summary.setText(self.event.title)
        # icon, summary = EmojiPicker.split_summary(self.event.title)
        # self.summary.setText(summary)
        # self.emoji_code = icon
        # if icon is not None:
        #     self.emoji_file_name = EmojiPicker.emoji_to_filename(icon)
        #     self.icon_button.setIcon(QIcon(PathManager.get_new_emoji_path(f'{self.emoji_file_name}.png')))

        self.start_time.setDateTime(self.event.start)
        self.end_time.setDateTime(self.event.end)
        self.all_day.setChecked(self.event.all_day)
        self.location.setText(self.event.location)
        if self.event.timezone is not None:
            timezone = self.event.timezone.replace('GMT', 'UTC')
            start = self.start_time.dateTime()
            end = self.end_time.dateTime()
            self.start_time.setDateTime(start.toTimeZone(QTimeZone(timezone.encode())))
            self.end_time.setDateTime(end.toTimeZone(QTimeZone(timezone.encode())))
            self.timezone.setCurrentText(timezone)

        try:
            self.description.setText(event.description)
        except KeyError:
            pass
        try:
            self.calendar.setCurrentText(event.calendar.name)
        except KeyError:
            pass
        if self.event.bg_color is not None:
            self.custom_color_cb.setChecked(True)
            for color_id, color in self.event_colors.items():
                if color_id is not None and color['bg_color'].name() == self.event.bg_color.name():
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
        # if self.emoji_code is not None:
        #     event_title = self.emoji_code + event_title
        if self.event is None:
            event = Event(event_id=None,
                          title=event_title,
                          start=self.start_time.dateTime().toPyDateTime(),
                          end=self.end_time.dateTime().toPyDateTime(),
                          location=self.location.text(),
                          description=self.description.toPlainText(),
                          all_day=self.all_day.isChecked(),
                          calendar=self.calendar_from_name(calendar_name=self.calendar.currentText()),
                          timezone=self.timezone.currentText(),
                          bg_color=self.get_bg_color(),
                          recurrence=self.get_recurrence(),
                          data={})
        else:
            event = self.event
            event.title = event_title
            event.location = self.location.text()
            event.description = self.description.toPlainText()
            event.timezone = self.timezone.currentText()
            event.all_day = self.all_day.isChecked()
            event.start = self.start_time.dateTime().toPyDateTime()
            event.end = self.end_time.dateTime().toPyDateTime()
            event.calendar = self.calendar_from_name(calendar_name=self.calendar.currentText())
            event.bg_color = self.get_bg_color()
            event.recurrence = self.get_recurrence()

        self.accepted.emit(event)
        self.close()

    def get_recurrence(self):
        if self.recurring.isChecked():
            freq = self.freq_cb.index(self.repeat_interval_unit.currentText())
            interval = self.repeat_interval.value()
            if self.end_repeat.currentText() == 'On':
                count = None
                until = self.end_repeat_date.dateTime().toPyDateTime()
            elif self.end_repeat.currentText() == 'After':
                count = self.end_repeat_occurrences.value()
                until = None
            else:
                count = None
                until = None

            rule = dateutil.rrule.rrule(freq, dtstart=None,
                                        interval=interval, wkst=None, count=count, until=until, bysetpos=None,
                                        bymonth=None, bymonthday=None, byyearday=None, byeaster=None,
                                        byweekno=None, byweekday=None,
                                        byhour=None, byminute=None, bysecond=None,
                                        cache=False)

            print(rule)
            return rule
        return None

    def closeEvent(self, ev: QCloseEvent) -> None:
        super().closeEvent(ev)
        self.closed.emit()

    # def pick_emoji(self):
    #     if self.emoji_picker is None:
    #         def set_emoji(emoji, code):
    #             self.icon_button.setIcon(emoji)
    #             self.emoji_code = code
    #         self.emoji_picker = EmojiPicker(self)
    #         self.emoji_picker.emoji_picked.connect(set_emoji)
    #     self.emoji_picker.update_recent()
    #     self.emoji_picker.show()
