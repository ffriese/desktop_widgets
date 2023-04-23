from plugins.calendarplugin.data_model import Event


class CalendarOfflineCache:
    def __init__(self):
        self.deleted_events = {}
        self.created_events = {}
        self.updated_events = {}

    def add_offline_creation(self, event: Event):
        self.created_events[event.id] = event

    def add_offline_deletion(self, event: Event):
        self.deleted_events[event.id] = event

    def add_offline_update(self, event: Event):
        self.updated_events[event.id] = event

    def __repr__(self):
        return f"CalendarOfflineCache(new:{self.created_events}, update:{self.updated_events}, del:{self.deleted_events})"

    def delete_cached_event(self, event):
        # remove from created
        self.created_events.pop(event.id, None)
        # remove from updates
        self.updated_events.pop(event.id, None)
