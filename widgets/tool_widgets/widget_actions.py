import logging

from PyQt5 import QtCore
from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QWidgetAction, QPushButton, QWidget, QVBoxLayout, QFormLayout, QCheckBox, QSpinBox, \
    QHBoxLayout

from helpers import styles


class ListSelectAction(QWidgetAction):
    selection_changed = pyqtSignal(dict)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.button = QPushButton('Set')
        self.button.clicked.connect(self.button_clicked)
        self.widget = QWidget()
        self.widget.setStyleSheet(styles.get_style('darkblue'))
        self.base_layout = QVBoxLayout()
        self.base_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout = QFormLayout()
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.base_layout.addLayout(self.form_layout)
        self.base_layout.addWidget(self.button)
        self.setDefaultWidget(self.widget)
        self.widget.setLayout(self.base_layout)
        self.items = {}

    def set_list(self, available_items):
        while self.form_layout.rowCount() > 0:
            self.form_layout.removeRow(0)
        self.items = {}
        for item in available_items:
            check_box = QCheckBox()
            check_box.setChecked(item[1])
            self.form_layout.addRow(item[0], check_box)
            self.items[item[0]] = check_box

    def button_clicked(self):
        self.selection_changed.emit({name: box.isChecked() for name, box in self.items.items()})


class QSpinBoxAction(QWidgetAction):

    value_changed = pyqtSignal(int)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.spin_box = QSpinBox()
        self.button = QPushButton('Set')
        self.button.clicked.connect(self.button_clicked)
        self.widget = QWidget()
        self.widget.setStyleSheet(styles.get_style('darkblue'))
        self.widget.setLayout(QHBoxLayout())
        self.widget.layout().setContentsMargins(5, 15, 25, 35)
        self.widget.layout().setSpacing(20)
        self.widget.layout().addWidget(self.spin_box)
        self.widget.layout().addWidget(self.button)
        self.setDefaultWidget(self.widget)
        self.value = self.spin_box.value()

    def button_clicked(self):
        if self.spin_box.value() != self.value:
            self.value = self.spin_box.value()
            self.value_changed.emit(self.spin_box.value())

    def set_value(self, value):
        self.value = value
        self.spin_box.setValue(value)

    def set_range(self, _min, _max):
        self.spin_box.setRange(_min, _max)


class QHourRangeAction(QWidgetAction):

    value_changed = pyqtSignal(int, int)

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self.start_spin_box = QSpinBox()
        self.end_spin_box = QSpinBox()
        self.button = QPushButton('Set')
        self.button.clicked.connect(self.button_clicked)
        self.widget = QWidget()
        self.widget.setStyleSheet(styles.get_style('darkblue'))
        self.widget.setLayout(QHBoxLayout())
        self.widget.layout().setContentsMargins(5, 15, 25, 35)
        self.widget.layout().setSpacing(20)
        self.widget.layout().addWidget(self.start_spin_box)
        self.widget.layout().addWidget(self.end_spin_box)
        self.widget.layout().addWidget(self.button)
        self.setDefaultWidget(self.widget)
        self.value = (self.start_spin_box.value(), self.end_spin_box.value())
        self.range = [0, 24]
        self.start_spin_box.valueChanged.connect(self.ensure_range)

    def ensure_range(self, *_):
        if self.start_spin_box == self.sender():
            self.end_spin_box.setRange(self.start_spin_box.value()+1, self.range[1])
        if self.end_spin_box == self.sender():
            self.start_spin_box.setRange(self.range[0], self.end_spin_box.value()-1)

    def button_clicked(self):
        if self.start_spin_box.value() != self.value[0] or self.end_spin_box.value() != self.value[1]:
            self.set_value((self.start_spin_box.value(), self.end_spin_box.value()))
            self.value_changed.emit(self.start_spin_box.value(), self.end_spin_box.value())

    def set_value(self, value):
        self.value = value
        self.start_spin_box.setValue(value[0])
        self.end_spin_box.setValue(value[1])
        self.start_spin_box.setRange(self.range[0], self.end_spin_box.value() - 1)
        self.end_spin_box.setRange(self.start_spin_box.value() + 1, self.range[1])

    def set_range(self, _min, _max):
        self.range = [_min, _max]
        self.start_spin_box.setRange(_min, self.value[1]-1)
        self.end_spin_box.setRange(self.value[0]+1, _max)
