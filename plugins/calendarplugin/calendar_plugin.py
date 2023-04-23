import copy
import uuid
from datetime import datetime
from enum import Enum
from typing import Union, List, Dict, Any

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QColor
from dateutil.tz import tzlocal

from helpers.settings_storage import SettingsStorage
from plugins.base import BasePlugin
from plugins.calendarplugin.data_model import Calendar, Event, EventInstance, CalendarData, CalendarSyncException
from plugins.calendarplugin.offline_cache import CalendarOfflineCache


class CalendarPlugin(BasePlugin):

    signal_delete = pyqtSignal(str, object)  # event_id, new_event
    single_event_changed = pyqtSignal(object)

    COLORS = {
            1: "#7986cb",  # Lavender
            2: "#33b679",  # Sage
            3: "#8e24aa",  # Grape
            4: "#e67c73",  # Flamingo
            5: "#f6c026",  # Banana
            6: "#f5511d",  # Tangerine
            7: "#039be5",  # Peacock
            8: "#616161",  # Graphite
            9: "#3f51b5",  # Blueberry
            10: "#0b8043",  # Basil
            11: "#d60000"  # Tomato
        }

    COLOR_DICT = {
        None: {},
        **{str(k): {'fg_color': QColor('#f1f1f1'), 'bg_color': QColor(v)} for k, v in COLORS.items()}
    }

    class CacheMode(Enum):
        FORCE_REFRESH = 1,
        REFRESH_LATER = 2,
        ALLOW_CACHE = 3

    def __init__(self, plugin_id: str):
        super().__init__()
        self.id = plugin_id
        self.cache_name = f'cal_event_cache_{self.id}'
        self.offline_cache: CalendarOfflineCache = SettingsStorage.load_or_default(
            self.cache_name, CalendarOfflineCache())

    def update_async(self, days_in_future: int = None, days_in_past: int = None,
                     cache_mode=CacheMode.FORCE_REFRESH, *args, **kwargs) -> None:
        if days_in_future is None:
            self.log_warn('days_in_future missing! should not happen unless after inserting credentials')
            days_in_future = 12
        if days_in_past is None:
            self.log_warn('days_in_past missing! should not happen unless after inserting credentials')
            days_in_past = 2
        self.log_info(self, 'async', cache_mode)
        super().update_async(cache_mode=cache_mode, days_in_future=days_in_future, days_in_past=days_in_past,
                             *args, **kwargs)

    def update_synchronously(self, days_in_future: int, days_in_past: int,
                             *args, **kwargs) -> Union[CalendarData, None]:
        raise NotImplementedError()

    def quit(self):
        raise NotImplementedError()

    def setup(self):
        raise NotImplementedError()

    def create_event(self, event: Event,
                     days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        try:
            return self._create_synced_event(event, days_in_future, days_in_past)
        except CalendarSyncException as cse:
            print('DESYNC! CACHE!!!')
            event.id = f'non-sync{uuid.uuid4()}'
            event.data['id'] = event.id
            event.mark_desynchronized()
            self.offline_cache.add_offline_creation(event)
            SettingsStorage.save(self.offline_cache, self.cache_name)
            self.single_event_changed.emit(event)
            # todo: check if unpack needed
            return event

    def _create_synced_event(self, event: Event,
                             days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        raise NotImplementedError()

    def delete_event(self, event: Event) -> bool:
        if event.is_synchronized():
            try:
                return self._delete_synced_event(event)
            except CalendarSyncException as cse:
                print('DESYNC! CACHE!!!')
                event.mark_desynchronized()
                self.offline_cache.add_offline_deletion(event)
                SettingsStorage.save(self.offline_cache, self.cache_name)
                self.signal_delete.emit(event.id, None)
                # todo: check if unpack needed
                return False
        else:
            self.signal_delete.emit(event.id, None)
            self.offline_cache.delete_cached_event(event)
            SettingsStorage.save(self.offline_cache, self.cache_name)

    def _delete_synced_event(self, event: Event) -> bool:
        raise NotImplementedError()

    def delete_event_instance(self, instance: EventInstance,
                              days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        self.log(f'trying to delete {instance.root_event.id} instance: {instance.instance_id}')
        root_event = instance.root_event

        # remove from exceptions if necessary
        if instance.instance_id in root_event.subcomponents:
            root_event.subcomponents.pop(instance.instance_id)
        # create exdate
        exdate = datetime.strptime(instance.instance_id, '%Y%m%dT%H%M%SZ').replace(tzinfo=tzlocal())
        if root_event.exdates:
            root_event.exdates.append(exdate)
        else:
            root_event.exdates = [exdate]
        # update root event
        return self.update_event(root_event, days_in_future=days_in_future, days_in_past=days_in_past)

    def update_event(self, event: Event,
                     days_in_future: int, days_in_past: int,
                     moved_from_calendar: Union[Calendar, None] = None,
                     ) -> Union[Event, List[EventInstance]]:

        # OPTION 1: Move Event between Calendars = delete in old, create in new
        # note: no sync-exception-check, as we use the individually checked 'create' and 'delete' functions
        if moved_from_calendar is not None:
            # create copy of event to move to new calendar
            # (original event, including old id, is still necessary for proper deletion)
            new_event = copy.deepcopy(event)
            # remove event id for 'new' event, will be re-generated by plugin on creation
            new_event.id = None
            for e in new_event.subcomponents.values():
                e.id = None
            created = self.create_event(new_event, days_in_future, days_in_past)
            event.calendar = moved_from_calendar
            self.delete_event(event)
            # todo: make sure old event is deleted from view
            return created
        # OPTION 2: actual 'update'
        else:
            try:
                return self._update_synced_event(event, days_in_future, days_in_past)
            except CalendarSyncException as cse:
                print('DESYNC, ADD TO CACHE!!!')
                event.mark_desynchronized()
                self.offline_cache.add_offline_update(event)
                SettingsStorage.save(self.offline_cache, self.cache_name)
                # todo: check if unpack needed
                self.single_event_changed.emit(event.id)
                return event

    def _update_synced_event(self, event: Event,
                             days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        raise NotImplementedError()

    def delete_cache(self):
        SettingsStorage.delete(self.cache_name)

    def apply_offline_cache(self, days_in_future: int, days_in_past: int):
        created = list(self.offline_cache.created_events.values())
        for new_event in created:
            self.log_info('trying to cache-create: ', new_event.data)
            ne = copy.deepcopy(new_event)
            temp_id = ne.data.pop('id')
            ne.data.pop('synchronized')
            ne.id = None
            try:
                synced = self._create_synced_event(ne,
                                                   days_in_future=days_in_future,
                                                   days_in_past=days_in_past)
                self.offline_cache.created_events.pop(new_event.id)
                # todo: EMIT DISPLAY-UPDATE
                self.single_event_changed.emit(synced)
                self.log_info('successfully created ', synced.data)
                if temp_id in self.offline_cache.updated_events.keys():
                    self.log_info(f"moving {temp_id} to {synced.id}")
                    updts = self.offline_cache.updated_events.pop('temp_id')
                    self.offline_cache.updated_events[synced.id] = updts
                else:
                    self.log_info(f"{temp_id} not found in update cache")
            except CalendarSyncException as cse:
                self.log_info('could not create. kept in cache', new_event.data)
                # todo: EMIT DISPLAY-UPDATE
                self.single_event_changed.emit(new_event)
                # self.display_new_event(new_event)
                continue

        for update_id in list(self.offline_cache.updated_events.keys()):
            if update_id.startswith("non-sync"):
                if update_id in self.offline_cache.created_events.keys():
                    self.log_warn(f'updates for {update_id} are ignored as the main event is not synced')
                    continue
                else:
                    self.log_error(
                        f"{update_id} is a non-synced event without creation this should not have happend. removing...")
                    self.offline_cache.updated_events.pop(update_id)
                    continue
            updated = self.offline_cache.updated_events[update_id]
            self.log_info('trying to cache-update: ', updated.data)
            ne = copy.deepcopy(updated)
            ne.data.pop('synchronized')
            try:
                synced = self._update_synced_event(ne,
                                                   days_in_future=days_in_future,
                                                   days_in_past=days_in_past)
                self.offline_cache.updated_events.pop(update_id)
                self.log_info('successfully updated ', updated.data)
                # todo: EMIT DISPLAY-UPDATE
                self.single_event_changed.emit(synced)
                # self.display_new_event(synced)
            except CalendarSyncException as cse:
                self.log_info('could not update. kept in cache', updated.data)
                # todo: EMIT DISPLAY-UPDATE
                self.single_event_changed.emit(updated)
                # self.display_new_event(updated)

        for deleted in list(self.offline_cache.deleted_events.values()):
            self.log_info('trying to cache-delete: ', deleted.data)

            try:
                self._delete_synced_event(deleted)
                self.log_info('successfully deleted')
                self.offline_cache.deleted_events.pop(deleted.id)
                self.signal_delete.emit(deleted.id, None)
                # self.view.remove_event(deleted.id)
                # todo: delete from view emit
            except CalendarSyncException as cse:
                self.log_info('could not delete. kept in cache', deleted.data)
                self.signal_delete.emit(deleted.id, None)
                # self.view.remove_event(deleted.id)
                # todo: delete from view emit

        SettingsStorage.save(self.offline_cache, self.cache_name)

    def restore_excluded_date(self, root_event: Event, excluded_date: datetime,
                              days_in_future: int, days_in_past: int) -> Union[Event, List[EventInstance]]:
        if excluded_date in root_event.exdates:
            root_event.exdates.remove(excluded_date)
            return self.update_event(root_event, days_in_future=days_in_future, days_in_past=days_in_past)

    @classmethod
    def get_event_colors(cls) -> Dict[Any, Dict[str, QColor]]:
        return cls.COLOR_DICT


