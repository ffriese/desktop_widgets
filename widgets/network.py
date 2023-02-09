import shlex
import socket
import subprocess
from collections import deque

from PyQt5 import QtCore
from PyQt5.QtGui import QIcon, QCursor, QColor
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHeaderView, QToolTip, QStyle

from plugins.base import BasePlugin
from widgets.base import BaseWidget
import time

from plugins.network import NetworkPlugin


class NetworkWidget(BaseWidget):

    def received_new_data(self, plugin: BasePlugin, data: object):
        self.log_info(f'got data: {data}')

    def __init__(self):
        super(NetworkWidget, self).__init__()
        self.net_plugin = None

        self.tree_wid = QTreeWidget()
        self.tree_wid.setHeaderHidden(True)
        self.tree_wid.setColumnCount(2)
        self.tree_wid.header().setStretchLastSection(False)
        self.tree_wid.header().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tree_wid.header().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tree_wid.setStyleSheet("QTreeView{ background-color: transparent; color:white;"
                                    "selection-background-color: argb(0,0,255,90); "
                                    "selection-color: white; "
                                    "outline: none;}"
                                    ""
                                    "QTreeView::branch:has-children:!has-siblings:closed,"
                                    """QTreeView::branch:closed:has-children:has-siblings {
                                            border-image: none;
                                            image: url(resources/icons/stylesheet-branch-closed.png);
                                    }
                                    
                                    QTreeView::branch:open:has-children:!has-siblings,
                                    QTreeView::branch:open:has-children:has-siblings  {
                                            border-image: none;
                                            image: url(resources/icons/stylesheet-branch-open.png);
                                    }"""
                                    )
        self.tree_wid.setIndentation(10)
        self.tree_wid.setMouseTracking(True)
        self.tree_wid.entered.connect(self.handleItemEntered)
        self.tree_wid.itemCollapsed.connect(self.handleCollapse)
        self.tree_wid.itemExpanded.connect(self.handleExpand)

        self.layout = QVBoxLayout()
        self.layout.addWidget(self.tree_wid)
        self.setLayout(self.layout)

        self.custom_repl = []

        self.custom_replacements = dict()
        self.icon_repl = {
            'desktop_widgets': self.style().standardIcon(QStyle.SP_FileDialogListView)
        }

        self.timer.setInterval(1000)

        self.collapsed_items = []
        self.settings_switcher['custom_repl'] = (setattr, ['self', 'key', 'value'], list)
        self.settings_switcher['collapsed_items'] = (setattr, ['self', 'key', 'value'], list)


    def update_ip_to_hostname(self, ip, hostname):
        print(f'GOT {ip}->{hostname}')
        try:
            proc_items = self.tree_wid.findItems(ip, QtCore.Qt.MatchContains | QtCore.Qt.MatchRecursive, 0)
            for proc_item in proc_items:
                print('found proc item')
                print(f'current text: {proc_item.text(0)}')
                proc_item.setText(0, proc_item.text(0).replace(ip, hostname))
                print(f'new text: {proc_item.text(0)}')
        except Exception as e:
            print(e)

    def dig_custom_replacements(self):
        for rep in self.custom_repl:
            try:
                cmd = 'dig %s A %s AAAA +short +time=3 +tries=3' % (rep, rep)
                self.log_info('digging: %s' % cmd)
                proc = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE)
                out, err = proc.communicate()
                time.sleep(0)
                out = out.decode()
                self.log_info('%s : -> %r' % (rep, out))
                if out.__contains__('connection timed out'):
                    self.log(out)
                    break
                for ip in out.split('\n'):
                    if ip != '':
                        self.custom_replacements[ip] = rep
            except:
                self.log_info('resolving %s failed' % rep)
                pass
        self.log_info('custom replacements: %r' % self.custom_replacements)

    def start(self):
        super(NetworkWidget, self).start()
        self.register_plugin(NetworkPlugin, 'net_plugin')
        # t = Thread(target=self.dig_custom_replacements)
        # t.start()
        # todo: make sure we REALLY DON'T need to join here
        self.net_plugin.found_hostname.connect(self.update_ip_to_hostname)
        self.timer.timeout.connect(self.update_con)
        self.timer.start()
        self.update_con()
        self.log_info('started')

    def update_con(self):
        add, remove = self.net_plugin.get_active_connections()
        self.addItems(self.tree_wid.invisibleRootItem(), add)
        self.removeItems(remove)

    def addItems(self, parent, data):
        column = 0
        for proc_name in data.keys():
            proc_icon = self.check_icon_replacement(proc_name)
            proc_item = self.addParent(parent, column, proc_name, data[proc_name], proc_icon)
            for proc in data[proc_name]:
                    # check for dupes
                    dupe_found = False
                    for i in range(0, proc_item.childCount()):

                        dt = proc_item.child(i).data(column, QtCore.Qt.UserRole)
                        try:
                            if dt[1]['remote_host'] == proc['remote_host']:
                                dupe_found = True
                                break
                        except Exception as e:
                            self.log_error(e, dt[1], proc)
                    if not dupe_found:
                        self.addChild(proc_item, column, self.proc_text(proc), proc, proc['icon'])

    def addParent(self, parent, column, title, data, icon=None):
        existing = self.tree_wid.findItems(title, QtCore.Qt.MatchExactly, 0)
        if len(existing) > 0:
            # self.debug('found parent %s' % title)
            return existing[0]
        else:
            # self.debug('need to create new parent %s' % title)
            if icon is None:
                icon = data[0]['icon']
            item = QTreeWidgetItem(parent, [title])
            item.setIcon(0, icon)
            item.setData(column, QtCore.Qt.UserRole, ('proc', data[0]))
            # item.setData(column, QtCore.Qt.BackgroundRole, QColor(0, 0, 255))
            # item.setData(column, QtCore.Qt.ForegroundRole, QColor(255, 0, 0))
            font = item.font(column)  # QFont('Arial', 9)
            font.setBold(True)
            item.setData(column, QtCore.Qt.FontRole, font)
            # item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
            if not self.collapsed_items.__contains__(title):
                item.setExpanded(True)
            return item

    def addChild(self, parent, column, title, data, icon=QIcon()):
        item = QTreeWidgetItem(parent, [title])
        item.setIcon(0, icon)
        item.setData(column, QtCore.Qt.UserRole, ('subproc', data))
        # item.setCheckState(column, QtCore.Qt.Unchecked)
        if data['status'] == 'ESTABLISHED':
            item.setData(column, QtCore.Qt.ForegroundRole, QColor(0, 255, 0))
        elif data['status'] == 'CLOSE_WAIT':
            item.setData(column, QtCore.Qt.ForegroundRole, QColor(255, 0, 0))
        return item

    def handleItemEntered(self, index):
        if index.isValid():
            data = index.data(QtCore.Qt.UserRole)
            if data is None:
                return
            try:
                display = str(data[1]['path'][0]) if data[0] == 'proc' else str(data[1])
            except IndexError as e:
                display = str(e)
            QToolTip.showText(
                QCursor.pos(),
                display,
                self.tree_wid.viewport(),
                self.tree_wid.visualRect(index)
            )

    def handleCollapse(self, item):
        title = item.text(0)
        if not self.collapsed_items.__contains__(title):
            self.collapsed_items.append(title)
        self.widget_updated.emit('collapsed_items', self.collapsed_items)

    def handleExpand(self, item):
        title = item.text(0)
        if self.collapsed_items.__contains__(title):
            self.collapsed_items.remove(title)
        self.widget_updated.emit('collapsed_items', self.collapsed_items)

    def proc_text(self, proc):
        try:
            r_add = proc['remote_host'][0]
            r_port = proc['remote_host'][1]
        except:
            r_add = str(proc['remote_host'])
            r_port = ''
        if True:
            try:
                # self.log_info('TRYING TO GET HOST FOR', r_add)
                if self.custom_replacements.__contains__(r_add):
                    r_host = self.custom_replacements[r_add]
                elif r_add in self.net_plugin.known_hosts:
                    r_host = self.net_plugin.known_hosts[r_add]
                else:
                    r_host = r_add
                # self.log_info('GOT: ', r_host)
            except Exception as e:
                self.log_error(e)
                r_host = r_add
                self.log_info('unable to resolve %s' % r_host)
        else:
            r_host = r_add
            self.log_info('skipped resolution for', r_add)

        return '%s:%s' % (r_host, r_port)

    def removeItems(self, data):
        for proc_name in data.keys():
            try:
                proc_item = self.tree_wid.findItems(proc_name, QtCore.Qt.MatchExactly, 0)[0]
                for proc in data[proc_name]:
                    text = self.proc_text(proc)
                    self.debug('processing remove instruction: [%s] - %s' % (proc_name, text))
                    for i in range(0, proc_item.childCount()):
                        if proc_item.child(i).text(0) == text:
                            (proc_item.child(i).parent() or self.tree_wid.invisibleRootItem()).\
                                removeChild(proc_item.child(i))
                            break

                if proc_item.childCount() < 1:
                    (proc_item.parent() or self.tree_wid.invisibleRootItem()).removeChild(proc_item)
                    self.debug('removed %s' % proc_item.text(0))
            except:
                pass

    def check_icon_replacement(self, proc_name):
        try:
            return self.icon_repl[proc_name]
        except KeyError:
            return None
        except Exception as e:
            self.log_info(str(e))
            return None
