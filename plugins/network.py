
import time
import sys
import socket
from typing import Union
from collections import deque
from threading import Thread
from PyQt5.QtCore import QFileInfo, pyqtSignal
from PyQt5.QtWidgets import QFileIconProvider

from plugins.base import BasePlugin
import psutil


from PyQt5.QtGui import QIcon

# TODO: USE NETHOGS FOR INDIVIDUAL BANDWIDTH STATS


class NetworkPlugin(BasePlugin):

    def update_synchronously(self, *args, **kwargs) -> Union[object, None]:
        return self.get_active_connections()

    found_hostname = pyqtSignal(str, str)

    def __init__(self):
        super(NetworkPlugin, self).__init__()
        self.oldConns = None
        self.icons = dict()
        self.known_hosts = dict()
        self.empty_icon = QIcon()
        self.need_lookup = deque()
        self.running = True
        self.denied_access = []
        self.lookupThread = Thread(target=self.look_it_up, daemon=True)
        self.lookupThread.start()

    def quit(self):
        self.running = False

    def look_it_up(self):
        while self.running:
            while self.need_lookup:
                r_add = self.need_lookup.popleft()
                if r_add in self.known_hosts:
                    continue
                try:
                    r_host = socket.gethostbyaddr(r_add)[0]
                    self.known_hosts[r_add] = r_host
                    self.log_info('FOUND HOST:', r_add, r_host)
                    self.found_hostname.emit(r_add, r_host)
                except socket.herror as e:
                    self.log_error(r_add, e)
                    self.known_hosts[r_add] = r_add
            time.sleep(0.1)

    def get_file_icon(self, path):
        provider = QFileIconProvider()
        if type(path) == list:
            if path:
                path = path[0]
            else:
                path = ''
        else:
            path = path
        info = QFileInfo(path)
        icon = QIcon(provider.icon(info))
        return icon

    def setup(self, *args):
        self.log_info('SETUP', args)

    def get_active_connections(self):
        connections = psutil.net_connections()
        # self.debug(psutil.net_io_counters())
        # self.get_icons()
        net_procs = dict()
        for con in connections:
            if con.raddr == () or self.custom_filter(con):
                continue
            local_host = con.laddr
            remote_host = con.raddr
            if remote_host[0] in self.known_hosts:
                remote_host_name = self.known_hosts[remote_host[0]]
            else:
                remote_host_name = remote_host[0]
                if not remote_host[0] in self.need_lookup:
                    self.need_lookup.append(remote_host[0])
            p_data = None

            if con.pid is None:
                proc_path = 'None'
                process_name = con.status.lower()
            elif con not in self.denied_access:
                try:
                    process = psutil.Process(con.pid)
                    p_data = process
                    proc_path = process.cmdline()
                    process_name = process.name()
                except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                    self.log_error(e, con)
                    self.denied_access.append(con)
                    continue
            else:
                process_name = f"PID {con.pid}"
                proc_path = ''

            # self.debug('%r %r %r' % (con, process_name, proc_path))
            try:
                if isinstance(proc_path, list):
                    for p in proc_path:
                        if 'desktop_widgets_core' in p:
                            process_name = 'desktop_widgets'
                elif 'desktop_widgets_core' in proc_path[1]:
                    process_name = 'desktop_widgets'
            except:
                pass
            info = dict()
            info['p_data'] = p_data
            info['pid'] = con.pid
            info['local_host'] = local_host
            info['remote_host'] = remote_host
            info['remote_host_name'] = remote_host_name
            info['path'] = proc_path
            info['status'] = con.status
            if type(proc_path) == str:
                path_id = proc_path
            else:
                if proc_path:
                    path_id = proc_path[0]
                else:
                    path_id = None
            if self.icons.keys().__contains__(path_id):
                info['icon'] = self.icons[path_id]
            else:
                self.log_info('trying to retrieve', path_id)
                icon = self.get_file_icon(proc_path)
                self.log_info(path_id, '->', icon)
                icon = icon if icon is not None else self.empty_icon
                self.icons[path_id] = icon
                info['icon'] = icon
            try:
                net_procs[process_name].append(info)
            except KeyError:
                net_procs[process_name] = []
                net_procs[process_name].append(info)

        add = dict()
        remove = dict()
        if self.oldConns is None:
            # for parent in net_procs.keys():
            #    self.debug('new in %s: %r' % (parent, net_procs[parent]))
            #    self.debug('-----------------------------------')
            self.oldConns = net_procs
            add = net_procs
        else:
            for parent in net_procs.keys():
                try:
                    new = [item for item in net_procs[parent] if item not in self.oldConns[parent]]
                except KeyError:
                    new = [item for item in net_procs[parent]]
                if len(new) > 0:
                    add[parent] = new
                    # self.debug('new in %s: %r' % (parent, new))
                    # self.debug('-----------------------------------')
            for parent in self.oldConns.keys():
                try:
                    obs = [item for item in self.oldConns[parent] if item not in net_procs[parent]]
                except KeyError:
                    obs = [item for item in self.oldConns[parent]]
                if len(obs) > 0:
                    remove[parent] = obs
                    # self.debug('obs in %s: %r' % (parent, obs))
                    # self.debug('-----------------------------------')
            self.oldConns = net_procs

        return add, remove

    def custom_filter(self, con):
        if con.status == 'LISTEN':
            return True
        filtered_ips = [
            '93.184.220.29',  # firefox certificate-connection
            '127.0.0.1',  # LOCALHORST
            ]
        try:
            if con.raddr[0] in filtered_ips:
                return True
        except:
            pass
        return False


class NetworkProcess:
    ...


class NetworkConnection:
    ...
