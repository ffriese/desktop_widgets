from __future__ import absolute_import
import copy
import logging
import math
from datetime import datetime, date, timedelta
from typing import Union, List

from credentials import NoCredentialsSetException
from plugins.base import BasePlugin
from plugins.calendarplugin.caldav.cal_dav import CalDavPlugin
from plugins.calendarplugin.calendar_plugin import CalendarPlugin, Event, CalendarData, Calendar
from plugins.climacell.climacell import ClimacellPlugin
from plugins.location.location_plugin import LocationPlugin
from plugins.location.mapquest_location_plugin import MapQuestLocationPlugin
from plugins.weather.weather_plugin import WeatherPlugin, WeatherReport
from widgets.base import BaseWidget
from plugins.calendarplugin.google.google_calendar import GoogleCalendarPlugin
from PyQt5.QtGui import QColor, QIcon, QResizeEvent, QMouseEvent, QPainter, QBrush, QPen
from PyQt5.QtCore import Qt, QDateTime
from PyQt5.QtWidgets import QHBoxLayout, QAction, QMessageBox, QLabel, QMenu, QApplication

from widgets.calendar.calendar_event import CalendarEventWidget
from widgets.calendar.event_editor import EventEditor
from widgets.calendar.multi_day_view import MultiDayView
from helpers.tools import PathManager
from widgets.tool_widgets import LocationPicker, QSpinBoxAction, ListSelectAction, CustomMessageBox
from widgets.tool_widgets.widget_actions import QHourRangeAction


class CalendarWidget(BaseWidget):
    DEFAULT_PLUGINS = {
        CalendarPlugin: CalDavPlugin,
        WeatherPlugin: ClimacellPlugin,
        LocationPlugin: MapQuestLocationPlugin
    }

    def __init__(self):
        super().__init__()

        self.days = 5
        self.initial_start_date = datetime.now().date()
        self.start_date = self.initial_start_date  # datetime.now().date() - timedelta(days=0)
        self.start_hour = 0
        self.end_hour = 24
        self.events = []
        self.weather_data = None  # type: Union[None, WeatherReport]
        self.calendar_data = None  # type: Union[None, CalendarData]
        self.event_cache = {'create': [], 'delete': [], 'update': {}}
        self.location = {}
        self.calendar_filter = []
        self.setAttribute(Qt.WA_AlwaysShowToolTips)
        self.settings_switcher['calendar_filter'] = (setattr, ['self', 'key', 'value'], list)
        self.settings_switcher['location'] = (setattr, ['self', 'key', 'value'], dict)
        self.settings_switcher['days'] = (setattr, ['self', 'key', 'value'], int)
        self.settings_switcher['start_hour'] = (setattr, ['self', 'key', 'value'], int)
        self.settings_switcher['end_hour'] = (setattr, ['self', 'key', 'value'], int)

        self.cal_plugin = None  # type: Union[None, CalendarPlugin]
        self.weather_plugin = None  # type: Union[None, WeatherPlugin]
        self.location_plugin = None  # type: Union[None, LocationPlugin]
        self.updating_calendars = False
        self.updating_weather = False
        self.visibility_lock = False

        self.mouse_down_loc = None
        self.mouse_cur_loc = None
        self.mouse_down_time = QDateTime.currentMSecsSinceEpoch()
        self.event_editor = None

        self.location_picker = None
        self.view = None
        self.refresh_calendar_action = QAction(QIcon(PathManager.get_icon_path('rep_calendar.png')),
                                               'Refresh Calendar', self)

        self.refresh_weather_action = QAction(QIcon(PathManager.get_icon_path('cloud-sync-icon.png')),
                                              'Refresh Weather', self)
        self.new_event_action = QAction(QIcon(PathManager.get_icon_path('new_event.png')),
                                        'New Event', self)
        self.day_num_select_menu = QMenu('Set Number of Days')
        self.day_num_select_action = QSpinBoxAction(self)

        self.hour_range_select_menu = QMenu('Set Visible Hours')
        self.hour_range_select_action = QHourRangeAction(self)

        self.select_calendars_menu = QMenu('Select Calendars')
        self.select_calendars_action = ListSelectAction(self)

        self.pick_location_action = QAction(QIcon(PathManager.get_icon_path('weather_location.png')),
                                            'Pick Weather-Location', self)
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.view = MultiDayView()
        self.view.event_edit_request.connect(self.show_event_editor)
        self.view.event_delete_request.connect(self.delete_event)
        self.view.event_rescale_request.connect(self.rescale_event)
        self.view.event_date_change_request.connect(self.rescale_event)

        self.layout.addWidget(self.view)

        self.setLayout(self.layout)

        self.visibility_icon = QLabel(self)
        self.visibility_icon.setPixmap(QIcon(PathManager.get_icon_path('events-visible-icon.png')).pixmap(20, 20))
        self.visibility_icon.setGeometry(15, 15, 20, 20)
        self.visibility_icon.enterEvent = lambda *a: self.hide_cal()
        self.visibility_icon.leaveEvent = lambda *a: self.show_cal()
        self.visibility_icon.mouseReleaseEvent = lambda *a: self.toggle_visibility()

        self.jump_to_today_bt = QLabel(self)
        self.jump_to_today_bt.setPixmap(QIcon(PathManager.get_icon_path('calendar_time.png')).pixmap(20, 20))
        self.jump_to_today_bt.setGeometry(15, 40, 20, 20)
        self.jump_to_today_bt.mouseReleaseEvent = lambda *q: self.jump_to_today()

        self.backward_bt = QLabel(self)
        self.forward_bt = QLabel(self)
        self.backward_bt.mouseReleaseEvent = lambda *a: self.backward()
        self.forward_bt.mouseReleaseEvent = lambda *a: self.forward()

        self.backward_bt.setGeometry(15, 65, 20, 20)
        self.forward_bt.setGeometry(350, 65, 20, 20)
        self.backward_bt.setPixmap(QIcon(PathManager.get_icon_path('bullet_arrow_left.png')).pixmap(20, 20))
        self.forward_bt.setPixmap(QIcon(PathManager.get_icon_path('bullet_arrow_right.png')).pixmap(20, 20))

        self.context_menu.addAction(self.refresh_calendar_action)

        self.context_menu.addAction(self.refresh_weather_action)

        self.context_menu.addAction(self.new_event_action)
        self.day_num_select_menu.setIcon(QIcon(PathManager.get_icon_path('calendar_time.png')))
        self.day_num_select_menu.addAction(self.day_num_select_action)
        self.context_menu.addMenu(self.day_num_select_menu)

        self.hour_range_select_menu.setIcon(QIcon(PathManager.get_icon_path('calendar_time.png')))
        self.hour_range_select_menu.addAction(self.hour_range_select_action)
        self.context_menu.addMenu(self.hour_range_select_menu)

        self.select_calendars_menu.setIcon(QIcon(PathManager.get_icon_path('calendar_visible.png')))
        self.select_calendars_menu.addAction(self.select_calendars_action)
        self.context_menu.addMenu(self.select_calendars_menu)

        self.context_menu.addAction(self.pick_location_action)

        self.timer.setInterval(15000)  # 15s
        self.timer.timeout.connect(self.check_update)
        self.timer.start()

    def forward(self):
        self.start_date += timedelta(days=self.days)
        self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
        self.view.set_filter(self.calendar_filter)
        self.update_view()

    def backward(self):
        self.start_date -= timedelta(days=self.days)
        self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
        self.view.set_filter(self.calendar_filter)
        self.update_view()

    def jump_to_today(self):
        self.start_date = self.initial_start_date
        self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
        self.view.set_filter(self.calendar_filter)
        self.update_view()

    def check_update(self):
        if self.initial_start_date == self.start_date and \
                self.view.start_date != datetime.now().date() and not self.updating_calendars:
            self.initial_start_date = self.start_date = datetime.now().date()
            self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
            self.view.set_filter(self.calendar_filter)
            self.async_update_weather()
            self.async_update_calendars()
        else:
            if self.cal_plugin.last_update + timedelta(hours=1) < datetime.now():
                self.async_update_calendars()
            if self.weather_plugin.last_update + timedelta(hours=1) < datetime.now():
                self.async_update_weather()
        self.update()

    def hide_cal(self):
        if not self.visibility_lock:
            self.visibility_icon.setPixmap(
                QIcon(PathManager.get_icon_path('events-temp-invisible-icon.png')).pixmap(20, 20))
            self.view.hide_events()

    def show_cal(self):
        if not self.visibility_lock:
            self.visibility_icon.setPixmap(QIcon(PathManager.get_icon_path('events-visible-icon.png')).pixmap(20, 20))
            self.view.show_events()

    def toggle_visibility(self):
        if self.visibility_lock:
            self.visibility_icon.setPixmap(QIcon(PathManager.get_icon_path('events-visible-icon.png')).pixmap(20, 20))
            self.visibility_lock = False
            self.view.show_events()
        else:
            self.visibility_icon.setPixmap(QIcon(PathManager.get_icon_path('events-invisible-icon.png')).pixmap(20, 20))
            self.visibility_lock = True

    def start(self):
        super().start()
        self.day_num_select_action.set_value(self.days)
        self.day_num_select_action.set_range(1, 7)
        self.day_num_select_action.value_changed.connect(lambda x: self.change_num_days(x))
        self.hour_range_select_action.set_value((self.start_hour, self.end_hour))
        self.hour_range_select_action.set_range(0, 24)
        self.hour_range_select_action.value_changed.connect(lambda x, y: self.change_hour_range(x, y))
        self.select_calendars_action.selection_changed.connect(self.update_calendar_filter)
        self.new_event_action.triggered.connect(self.create_new_event)
        self.refresh_weather_action.triggered.connect(self.async_update_weather)
        self.refresh_calendar_action.triggered.connect(self.async_update_calendars)
        self.pick_location_action.triggered.connect(self.pick_location)

        self.register_plugin(CalendarWidget.DEFAULT_PLUGINS[CalendarPlugin], 'cal_plugin')
        self.register_plugin(CalendarWidget.DEFAULT_PLUGINS[WeatherPlugin], 'weather_plugin')
        self.register_plugin(CalendarWidget.DEFAULT_PLUGINS[LocationPlugin], 'location_plugin')
        if self.location:
            self.weather_plugin.set_location(self.location)
        self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
        self.view.set_filter(self.calendar_filter)

        self.update_view()
        self.async_update_calendars()
        self.async_update_weather()

        self.try_to_apply_cache()

    def try_to_apply_cache(self):
        try:
            self.log_info('got myself some data-cache:', self.__data__['event_cache'])
            created = list(self.event_cache['create'])
            for new_event in created:
                self.log_info('new event: ', new_event.data)
                ne = copy.deepcopy(new_event)
                temp_id = ne.data.pop('id')
                ne.data.pop('synchronized')
                ne.id = None
                synced = self.cal_plugin.create_event(ne)
                if synced.is_synchronized():
                    self.event_cache['create'].remove(new_event)
                    self.log_info('successfully created ', new_event.data)
                    self.display_new_event(synced)
                    if temp_id in self.event_cache['update'].keys():

                        self.log_info(f"moving {temp_id} to {synced.id}")
                        updts = self.event_cache['update'].pop('temp_id')
                        self.event_cache['update'][synced.id] = updts
                    else:
                        self.log_info(f"{temp_id} not found in update cache")
                else:
                    self.log_info('could not create. kept in cache', new_event)
                    self.display_new_event(new_event)

            for update_id in list(self.event_cache['update'].keys()):
                if update_id.startswith("non-sync"):
                    if update_id in self.event_cache['create']:
                        self.log_warn(f'updates for {update_id} are ignored as the main event is not synced')
                        continue
                    else:
                        self.log_error(f"{update_id} is a non-synced event without creation this should not have happend. removing...")
                        self.event_cache['update'].pop(update_id)
                        continue
                updated = self.event_cache['update'][update_id]
                last_change = updated[-1]
                upd_event = last_change['new_data']
                ne = copy.deepcopy(upd_event)
                ne.data.pop('synchronized')
                moved_from = None if updated[0]['old_calendar'].id == upd_event.calendar.id else updated[0]['old_calendar']
                synced = self.cal_plugin.update_event(ne, moved_from_calendar=moved_from)
                if synced.is_synchronized():
                    self.event_cache['update'].pop(update_id)
                    self.log_info('successfully updated ', upd_event.data)
                    self.display_new_event(synced)
                else:
                    self.log_info('could not update. kept in cache', upd_event)
                    self.display_new_event(upd_event)

            for deleted in list(self.event_cache['delete']):
                self.log_info('DELETED EVENT: ', deleted.data)

                if self.cal_plugin.delete_event(deleted):
                    self.log_info('successfully deleted')
                    self.event_cache['delete'].remove(deleted)
                else:
                    self.log_info('could not delete. kept in cache', deleted.data)
                    self.view.remove_event(deleted.id)
            self.__data__['event_cache'] = self.event_cache
            self._save_data()
            self.log_info('got myself some cache:', self.event_cache)
        except KeyError as e:
            self.log_warn('no event cache yet. might get initialized in the future...', e)

    def update_calendar_filter(self, calendars):
        self.calendar_filter = []
        for name, enabled in calendars.items():
            if not enabled:
                self.calendar_filter.append(name)
        self.view.set_filter(self.calendar_filter)
        self.widget_updated.emit('calendar_filter', self.calendar_filter)

    def update_weather(self):
        self.view.set_weather(self.weather_data)
        self.refresh_weather_action.setEnabled(True)
        self.updating_weather = False
        self.update()

    def change_num_days(self, days):
        self.days = days
        self.widget_updated.emit('days', self.days)
        self.view.refresh(self.days, self.start_date, self.start_hour, self.end_hour)
        self.view.set_filter(self.calendar_filter)
        self.update_view()
        # self.request_reload()

    def change_hour_range(self, start_hour, end_hour):
        self.log_info('got start to end: ', start_hour, end_hour)
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.widget_updated.emit('start_hour', self.start_hour)
        self.widget_updated.emit('end_hour', self.end_hour)
        self.view.set_filter(self.calendar_filter)
        self.view.change_hours(start_hour, end_hour)

    def received_new_data(self, plugin: BasePlugin, data: object):
        self.log(f'received {data.__class__.__name__} from {plugin.__class__.__name__}',
                 level=logging.INFO)
        if isinstance(plugin, WeatherPlugin):
            if data is not None:
                self.weather_data = data
                # self.widget_updated.emit('weather_data', self.weather_data)
                self.__data__['weather_data'] = self.weather_data
                self._save_data()
            self.update_weather()
        if isinstance(plugin, CalendarPlugin):
            if data is not None:
                self.calendar_data = data
                # self.widget_updated.emit('calendar_data', self.calendar_data)
                self.__data__['calendar_data'] = self.calendar_data
                self._save_data()
            self.update_view()
            self.try_to_apply_cache()

    def update_view(self):
        self.view.remove_all()
        if self.calendar_data is not None:
            self.view.add_events(self.calendar_data.events)
            self.select_calendars_action.set_list([(c.name, c.name not in self.calendar_filter)
                                                   for c_id, c in self.calendar_data.calendars.items()])

        self.update_weather()
        self.refresh_calendar_action.setEnabled(True)
        self.updating_calendars = False
        self.update()

    def async_update_calendars(self):
        if not self.updating_calendars:
            self.updating_calendars = True
            self.refresh_calendar_action.setEnabled(False)
            self.cal_plugin.update_async(days_in_future=self.days + (self.start_date - datetime.now().date()).days + 5,
                                         days_in_past=max((datetime.now().date() - self.start_date).days, 0) + 1)

    def async_update_weather(self):
        if not self.updating_weather:
            self.updating_weather = True
            self.refresh_weather_action.setEnabled(False)
            self.weather_plugin.update_async()

    def create_event_editor(self):
        return EventEditor(self, [c for c_id, c in self.calendar_data.calendars.items()
                                  if c.name not in self.calendar_filter],
                           self.calendar_data.colors)

    def _clear_rect(self):
        self.mouse_down_loc = None
        self.mouse_cur_loc = None

    def create_new_event(self, start=None, end=None):

        def handle_new_event(event: Event):
            self._clear_rect()
            event = self.cal_plugin.create_event(event)
            if not event.is_synchronized():
                self.log_warn('EVENT CREATION FAILED! TODO: CACHE NEW EVENTS UNTIL CONNECTION IS RE-ESTABLISHED!!')
                self.display_new_event(event)
                self.event_cache['create'].append(event)
                CalendarWidget.__EVENT_CACHE__ = self.event_cache
                self.__data__['event_cache'] = self.event_cache
                self._save_data()
                return
            self.calendar_data.events[event.get_unique_instance_id()] = event
            self.__data__['calendar_data'] = self.calendar_data
            self._save_data()

            self.display_new_event(event)

        if self.calendar_data is not None:
            self.event_editor = self.create_event_editor()
            self.event_editor.setWindowTitle('Create New Event')
            self.event_editor.setWindowIcon(QIcon(PathManager.get_icon_path('new_event.png')))
            self.event_editor.accepted.connect(handle_new_event)
            self.event_editor.closed.connect(self._clear_rect)
            if type(start) is datetime and type(end) is datetime:
                self.event_editor.set_time(start, end)
            self.event_editor.show()

    def display_new_event(self, event):
        self.view.add_events({event.id: event})

    def delete_event(self, requesting_widget: CalendarEventWidget):
        if requesting_widget.event.recurrence:
            quit_msg = '"%s" is a recurring Event.' % requesting_widget.event.title
            mb = CustomMessageBox(QMessageBox.Question, f"Do you want to delete all instances?", quit_msg,
                                  QMessageBox.Yes | QMessageBox.No)
            mb.setWindowIcon(QIcon(PathManager.get_icon_path('delete_event.png')))
            mb.move(self.mapToGlobal(requesting_widget.pos()))
            reply = mb.exec()
            if reply != QMessageBox.Yes:
                return

        quit_msg = 'Do you want to delete "%s"?' % requesting_widget.event.title
        mb = CustomMessageBox(QMessageBox.Question, f"Are you sure?", quit_msg,
                              QMessageBox.Yes | QMessageBox.No)
        mb.setWindowIcon(QIcon(PathManager.get_icon_path('delete_event.png')))
        mb.move(self.mapToGlobal(requesting_widget.pos()))
        reply = mb.exec()
        if reply == QMessageBox.Yes:
            self.log_info('TRYING TO DELETE:', requesting_widget.event.__dict__)
            if not requesting_widget.event.is_synchronized():
                self.log_warn('trying to delete un-synchronized event')
                requesting_widget.delete_signal.emit(requesting_widget.event.id, None)
                self.event_cache['create'].remove(requesting_widget.event)
                self.__data__['event_cache'] = self.event_cache
                self._save_data()
                requesting_widget.log_debug(self.event_cache)
            else:
                self.log_warn('trying to delete synchronized event')
                if self.cal_plugin.delete_event(requesting_widget.event):
                    requesting_widget.delete_signal.emit(requesting_widget.event.id, None)
                    self.calendar_data.events.pop(requesting_widget.event.get_unique_instance_id())
                    # self.widget_updated.emit('calendar_data', self.calendar_data)
                    self.__data__['calendar_data'] = self.calendar_data
                    self._save_data()
                else:
                    self.log_warn('deletion failed. saving in cache')
                    self.event_cache['delete'].append(requesting_widget.event)
                    self.__data__['event_cache'] = self.event_cache
                    self._save_data()
                    requesting_widget.log_debug(self.event_cache)
                    requesting_widget.delete_signal.emit(requesting_widget.event.id, None)

    def all_instance_check(self, requesting_widget: CalendarEventWidget):
        edit_msg = 'Do you want to edit all instances?'
        mb = CustomMessageBox(QMessageBox.Question, f"{requesting_widget.summary} is a recurring event.",
                              edit_msg,
                              QMessageBox.Yes | QMessageBox.No)
        mb.setWindowIcon(QIcon(PathManager.get_icon_path('edit_event.png')))
        mb.move(self.mapToGlobal(requesting_widget.pos()))
        reply = mb.exec()
        return reply

    def make_update_to_event(self, event: Event, old_calendar: Union[None, Calendar],
                             requesting_widget: CalendarEventWidget):

        if event.calendar.id != old_calendar.id:
            updated_event = self.cal_plugin.update_event(event, old_calendar)
        else:
            updated_event = self.cal_plugin.update_event(event)
        if not updated_event.is_synchronized():
            self.log_warn('trying to update non-synchronized event ', updated_event.__dict__)
            up_cache = self.event_cache['update']
            if updated_event.id not in up_cache.keys():
                up_cache[updated_event.id] = []
            cached_edits = up_cache[updated_event.id]
            cached_edits.append({'new_data': updated_event, 'old_calendar': old_calendar})
            self.__data__['event_cache'] = self.event_cache
            self._save_data()
            requesting_widget.log_debug(self.event_cache)
        if requesting_widget:
            print(requesting_widget)
            requesting_widget.delete_signal.emit(requesting_widget.event.id, updated_event)
        else:
            print('WTF THIS SHOULD NEVER HAVE HAPPENED')

    def show_event_editor(self, requesting_widget: CalendarEventWidget):
        if requesting_widget.recurring:
            reply = self.all_instance_check(requesting_widget)
            if reply == QMessageBox.Yes:
                self.event_editor = self.create_event_editor()
                #self.event_editor.set_event(self.cal_plugin.get_recurring_event(requesting_widget.event))
                self.event_editor.set_event(requesting_widget.event)
            elif reply == QMessageBox.No:
                self.event_editor = self.create_event_editor()
                ev = copy.deepcopy(requesting_widget.event)
                ev.recurrence = None
                self.event_editor.set_event(ev)
            else:
                return
        else:
            self.event_editor = self.create_event_editor()
            self.event_editor.set_event(requesting_widget.event)

        def update_event(event):
            self.make_update_to_event(event, old_calendar, requesting_widget)

        old_calendar = requesting_widget.event.calendar
        self.event_editor.accepted.connect(update_event)
        self.event_editor.show()

    def rescale_event(self, requesting_widget: CalendarEventWidget,
                      new_start: Union[datetime, date], new_end: Union[datetime, date],
                      edit_start=False):
        if requesting_widget.recurring:
            reply = self.all_instance_check(requesting_widget)
            # TODO: IMPLEMENT THIS FINALLY!!
            requesting_widget.parent().resizeEvent(QResizeEvent(requesting_widget.parent().size(),
                                                                requesting_widget.parent().size()))

            return
            # if reply == QMessageBox.Yes:
            #     self.event_editor = EventEditor(self, self.calendars)
            #     self.event_editor.set_event(self.calendar_plugin.get_recurring_event(requesting_widget.event))
            # elif reply == QMessageBox.No:
            #     self.event_editor = EventEditor(self, self.calendars)
            #     self.event_editor.set_event(requesting_widget.event)
            # else:
            #     return

        def update_event(event: Event):
            if event.all_day:
                event.start = datetime.combine(new_start, datetime.min.time())
                event.end = datetime.combine(new_end, datetime.min.time())
            else:
                event.start = new_start
                event.end = new_end
            self.make_update_to_event(event, event.calendar, requesting_widget)

        if not requesting_widget.event.all_day:
            edit_msg = f"Do you want to reschedule to " \
                       f"{new_start.hour:02d}:{new_start.minute:02d} - {new_end.hour:02d}:{new_end.minute:02d}?"
        else:
            edit_msg = f"Do you want to reschedule to " \
                       f"{new_start.day:02d}.{new_start.month:02d}. - {new_end.day:02d}.{new_end.month:02d}.?"
        mb = CustomMessageBox(QMessageBox.Question, f"Edit {requesting_widget.summary}",
                              edit_msg,
                              QMessageBox.Yes | QMessageBox.No)
        mb.setWindowIcon(QIcon(PathManager.get_icon_path('edit_event.png')))
        mb.move(self.mapToGlobal(requesting_widget.pos()))
        reply = mb.exec()
        if reply == QMessageBox.Yes:
            update_event(requesting_widget.event)
        elif reply == QMessageBox.No:
            requesting_widget.parent().resizeEvent(QResizeEvent(requesting_widget.parent().size(),
                                                                requesting_widget.parent().size()))

    def pick_location(self):
        def set_location(loc):
            self.log(f'setting location {loc} (old: {self.location})')
            if self.location != loc:
                self.log_info('updating weather location!')
                self.location = loc
                self.widget_updated.emit('location', self.location)
                self.weather_plugin.set_location(self.location)
                self.async_update_weather()

        try:

            self.location_picker = LocationPicker(self,
                                                  'MapQuest',
                                                  self.location_plugin.get_api_key(),
                                                  self.location,
                                                  self.weather_data.get_location_name() if self.weather_data
                                                  else 'Hamburg')
            self.location_picker.location_picked.connect(set_location)
            self.location_picker.show()
        except NoCredentialsSetException as e:
            self.log(e, level=logging.ERROR)

    def mousePressEvent(self, event: QMouseEvent):
        self.mouse_down_time = QDateTime.currentMSecsSinceEpoch()
        self.mouse_down_loc = event.globalPos()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self.mouse_down_loc is not None:
            self.mouse_cur_loc = event.globalPos()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.mouse_down_loc is not None and self.mouse_cur_loc is not None \
                and math.sqrt(math.pow(self.mouse_down_loc.x() - self.mouse_cur_loc.x(), 2) +
                              math.pow(self.mouse_down_loc.y() - self.mouse_cur_loc.y(), 2)) < 15 \
                or QDateTime.currentMSecsSinceEpoch() < self.mouse_down_time + 200:
            self.mouse_down_loc = None
            self.mouse_cur_loc = None
            self.repaint()
        else:
            try:
                start, end = self.view.map_to_time(self.mouse_down_loc, event.globalPos())
                self.create_new_event(start, end)
            except TypeError:  # not a valid event area
                self.mouse_down_loc = None
                self.mouse_cur_loc = None
                self.repaint()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.mouse_down_loc is not None and self.mouse_cur_loc is not None \
                and math.sqrt(math.pow(self.mouse_down_loc.x() - self.mouse_cur_loc.x(), 2) +
                              math.pow(self.mouse_down_loc.y() - self.mouse_cur_loc.y(), 2)) > 15:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(255, 255, 255, 80)))
            painter.setBrush(QBrush(QColor(80, 80, 200, 90)))
            start_w = start_idx = None
            end_w = end_idx = None
            for i, dw in enumerate(self.view.day_widgets):
                start_pos = dw.mapFromGlobal(self.mouse_down_loc)
                end_pos = dw.mapFromGlobal(self.mouse_cur_loc)
                if 0 < start_pos.x() < dw.width() and 0 < start_pos.y() < dw.height():
                    start_w = dw
                    start_idx = i
                if 0 < end_pos.x() < dw.width() and 0 < end_pos.y() < dw.height():
                    end_w = dw
                    end_idx = i

            if start_w is not None:
                md = self.mapFromGlobal(self.mouse_down_loc)
                mc = self.mapFromGlobal(self.mouse_cur_loc)

                if end_w == start_w:
                    painter.drawRect(start_w.x(), md.y(),
                                     start_w.width(),
                                     mc.y() - md.y())
                elif end_w is not None:

                    def switch_vars(a, b):
                        return b, a

                    if md.x() > mc.x():
                        start_w, end_w = switch_vars(start_w, end_w)
                        start_idx, end_idx = switch_vars(start_idx, end_idx)
                        md, mc = switch_vars(md, mc)

                    painter.drawRect(start_w.x(), md.y(),
                                     start_w.width(),
                                     start_w.height() - (md.y() - start_w.y()))
                    for i in range(start_idx + 1, end_idx):
                        dw = self.view.day_widgets[i]
                        painter.drawRect(dw.x(), dw.y(), dw.width(), dw.height())
                    painter.drawRect(end_w.x(), end_w.y(),
                                     end_w.width(),
                                     mc.y() - end_w.y())

    def resizeEvent(self, event):
        if self.view is not None:
            self.forward_bt.move(self.view.x() + self.view.width() - 25, self.forward_bt.y())
