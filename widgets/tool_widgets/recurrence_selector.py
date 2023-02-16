from datetime import datetime

import dateutil
from PyQt5.QtWidgets import QLabel, QSpinBox, QDateTimeEdit, QHBoxLayout, QComboBox, QFormLayout
from dateutil.rrule import rrulestr, weekday

from helpers.rrule_helper import WeekOfMonth, Weekdays, Monthday, Frequencies
from widgets.tool_widgets.widget import Widget


class RecurrenceSelector(Widget):
    def __init__(self, *args):
        super().__init__(*args)
        self.rec_lay = QFormLayout()

        self.repeat_layout = QHBoxLayout()
        self.repeat_interval = QSpinBox()
        self.repeat_interval.setMinimum(1)
        self.repeat_interval_unit = QComboBox()
        self.repeat_interval_unit.addItems(Frequencies.EN)
        self.repeat_interval_unit.currentTextChanged.connect(self.recurrence_interval_unit_changed)
        self.repeat_layout.addWidget(self.repeat_interval)
        self.repeat_layout.addWidget(self.repeat_interval_unit)

        self.detailed_repeat_layout = QHBoxLayout()

        self.detailed_repeat_day_of_week = QComboBox()
        self.detailed_repeat_day_of_week.addItems(Weekdays.EN)

        self.detailed_repeat_type = QComboBox()
        self.detailed_repeat_type.addItems(['Every', 'On the', 'Every Single'])
        self.detailed_repeat_type.currentTextChanged.connect(self.detailed_repeat_type_changed)

        self.detailed_repeat_rhythm = QComboBox()
        self.detailed_repeat_rhythm.addItems(WeekOfMonth.EN)
        self.detailed_repeat_rhythm.setVisible(False)

        self.detailed_repeat_day_of_month = QComboBox()
        self.detailed_repeat_day_of_month.addItems(Monthday.EN)
        self.detailed_repeat_day_of_month.setVisible(False)

        self.detailed_repeat_layout.addWidget(self.detailed_repeat_type)
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_rhythm)
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_day_of_week)
        self.detailed_repeat_layout.addWidget(self.detailed_repeat_day_of_month)

        self.end_repeat_layout = QHBoxLayout()
        self.end_repeat = QComboBox()
        self.end_repeat.addItems(['Never', 'On', 'After'])
        self.end_repeat.currentTextChanged.connect(self.end_repeat_changed)
        self.end_repeat_date = QDateTimeEdit()
        self.end_repeat_date.setCalendarPopup(True)
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
        self.setLayout(self.rec_lay)

        # Set defaults
        self.repeat_interval_unit.setCurrentText(Frequencies.en_from_raw(Frequencies.WEEKLY))

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
        if text == 'Every Single':
            self.detailed_repeat_rhythm.hide()
            self.detailed_repeat_day_of_week.show()
            self.detailed_repeat_day_of_month.hide()
        elif text == 'Every':
            self.detailed_repeat_rhythm.show()
            self.detailed_repeat_day_of_week.show()
            self.detailed_repeat_day_of_month.hide()
        elif text == 'On the':
            self.detailed_repeat_rhythm.hide()
            self.detailed_repeat_day_of_week.hide()
            self.detailed_repeat_day_of_month.show()

    def recurrence_interval_unit_changed(self, text):
        if text == Frequencies.en_from_raw(Frequencies.MONTHLY):
            self.rec_lay.insertRow(self.rec_lay.getLayoutPosition(self.repeat_layout)[0]+1, "",
                                   self.detailed_repeat_layout)
            for i in range(self.detailed_repeat_layout.count()):
                self.detailed_repeat_layout.itemAt(i).widget().show()
            self.detailed_repeat_type_changed(self.detailed_repeat_type.currentText())
        else:
            if self.rec_lay.getLayoutPosition(self.detailed_repeat_layout)[0] == 1:
                self.rec_lay.takeRow(self.rec_lay.getLayoutPosition(self.repeat_layout)[0] + 1)
                for i in range(self.detailed_repeat_layout.count()):
                    self.detailed_repeat_layout.itemAt(i).widget().hide()

    def set_recurrence(self, recurrence):
        if isinstance(recurrence, dateutil.rrule.rrule):
            rule = recurrence.__dict__
        else:
            rec_interval = recurrence[0]
            # print('event is recurring and editable:')
            rule = rrulestr(rec_interval).__dict__
        # print(recurrence)
        # print(rrulestr(rec_interval))
        # print(rule)

        _interval = rule['_interval']
        _freq = Frequencies.EN[int(rule['_freq'])]
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

    def get_rrule(self):
        repeat_interval_unit = self.repeat_interval_unit.currentText()
        freq = Frequencies.EN.index(repeat_interval_unit)
        interval = self.repeat_interval.value()
        detailed_repeat_type = self.detailed_repeat_type.currentText()

        by_month_day = None
        by_week_day = None

        if repeat_interval_unit == Frequencies.en_from_raw(Frequencies.MONTHLY):
            if detailed_repeat_type == 'Every Single':
                by_week_day = weekday(self.detailed_repeat_day_of_week.currentIndex())
            elif detailed_repeat_type == 'Every':
                by_week_day = weekday(self.detailed_repeat_day_of_week.currentIndex(),
                                      WeekOfMonth.raw_from_selection(self.detailed_repeat_rhythm.currentText()))
            elif detailed_repeat_type == 'On the':
                by_month_day = Monthday.raw_from_selection(self.detailed_repeat_day_of_month.currentText())

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
                                    bymonth=None, bymonthday=by_month_day, byyearday=None, byeaster=None,
                                    byweekno=None, byweekday=by_week_day,
                                    byhour=None, byminute=None, bysecond=None,
                                    cache=False)

        print(rule)
        return rule