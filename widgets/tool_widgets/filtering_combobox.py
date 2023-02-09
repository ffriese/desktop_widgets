from PyQt5.QtCore import Qt, QSortFilterProxyModel
from PyQt5.QtWidgets import QComboBox, QCompleter

#  ----------------------------------------------------------------------------
#
#  FilteringComboBox class taken from http://www.gulon.co.uk/2013/05/07/a-filtering-qcombobox/
#
#  "THE BEER-WARE LICENSE" (Revision 42):
#  Rob Kent from http://www.gulon.co.uk wrote this class.  As long as you retain this notice you
#  can do whatever you want with this stuff. If we meet some day, and you think
#  this stuff is worth it, you can buy me a beer in return.
#  ----------------------------------------------------------------------------


class FilteringComboBox(QComboBox):
    def __init__(self, parent=None, *args):
        QComboBox.__init__(self, parent, *args)
        self.setEditable(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setFilterCaseSensitivity(Qt.CaseInsensitive)
        self._proxy.setSourceModel(self.model())

        self._completer = QCompleter(self._proxy, self)
        self._completer.activated.connect(self.on_completer_activated)
        self._completer.setCompletionMode(QCompleter.UnfilteredPopupCompletion)
        self.setCompleter(self._completer)

        self.lineEdit().textEdited.connect(self._proxy.setFilterFixedString)

    def on_completer_activated(self, text):
        if not text:
            return
        self.setCurrentIndex(self.findText(text))
        self.activated[str].emit(self.currentText())