import types
import unittest
from unittest.mock import MagicMock

from plugins.calendarplugin.data_model import CalendarSyncException
from tests.helper import MockPlugin
from tests.plugin_tests.calendar.data_generator import CalendarPluginDataGenerator


class TestCalendarPlugin(unittest.TestCase):

    def setUp(self):
        self.plugin = MockPlugin('MOCKPLUGIN')

    def test_create_event(self):
        # Test creation of a new event
        # 1) create event
        event = CalendarPluginDataGenerator.generate_event(title='Test Event')
        created_event = self.plugin.create_event(event, days_in_future=7, days_in_past=0)
        # 2) test assertions
        self.assertIsNotNone(created_event.id)
        self.assertEqual(created_event.title, "Test Event")
        self.assertTrue(event.is_synchronized())
        self.assertNotIn(event.id, self.plugin.offline_cache.created_events.keys())
        self.assertNotIn(event, self.plugin.offline_cache.created_events.values())

    def test_create_event_sync_fail(self):
        # Test creation of an event that fails to sync
        # 1) mock event creation failure
        self.plugin._create_synced_event = MagicMock(side_effect=CalendarSyncException())
        unsynced_event = self.plugin.create_event(
            CalendarPluginDataGenerator.generate_event(title='Test Event'), days_in_future=7, days_in_past=0)
        # 2) test assertions
        self.assertIsNotNone(unsynced_event.id)
        self.assertEqual(unsynced_event.title, "Test Event")
        self.assertFalse(unsynced_event.is_synchronized())
        self.assertIn(unsynced_event.id, self.plugin.offline_cache.created_events.keys())
        self.assertIn(unsynced_event, self.plugin.offline_cache.created_events.values())
        # 3 try failing cache-update
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 4) test assertions
        self.assertIn(unsynced_event.id, self.plugin.offline_cache.created_events.keys())
        self.assertIn(unsynced_event, self.plugin.offline_cache.created_events.values())
        # 5) mock cache-update success
        self.plugin._create_synced_event = types.MethodType(MockPlugin._create_synced_event, self)
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 6) test assertions
        self.assertNotIn(unsynced_event.id, self.plugin.offline_cache.created_events.keys())  # deleted from cache
        self.assertNotIn(unsynced_event, self.plugin.offline_cache.created_events.values())

    def test_delete_event(self):
        # Test deletion of an event that is synchronized
        event = CalendarPluginDataGenerator.generate_event(title='Test Event')
        created_event = self.plugin.create_event(event, days_in_future=7, days_in_past=0)
        success = self.plugin.delete_event(created_event)
        # 2) test assertions
        self.assertTrue(success)
        self.assertNotIn(event.id, self.plugin.offline_cache.deleted_events.keys())  # not in cache
        self.assertNotIn(event, self.plugin.offline_cache.deleted_events.values())

    def test_delete_event_sync_fail(self):
        # Test deletion of an event that fails to sync
        # 1) mock deletion failure
        event = CalendarPluginDataGenerator.generate_event(title='Test Event')
        self.plugin._delete_synced_event = MagicMock(side_effect=CalendarSyncException())
        success = self.plugin.delete_event(event)
        # 2) test assertions
        self.assertFalse(success)
        self.assertIn(event.id, self.plugin.offline_cache.deleted_events.keys())
        self.assertIn(event, self.plugin.offline_cache.deleted_events.values())
        # 3 try failing cache-update
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 4) test assertions
        self.assertIn(event.id, self.plugin.offline_cache.deleted_events.keys())
        self.assertIn(event, self.plugin.offline_cache.deleted_events.values())
        # 5) mock cache-update success
        self.plugin._delete_synced_event = types.MethodType(MockPlugin._delete_synced_event, self)
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 6) test assertions
        self.assertNotIn(event.id, self.plugin.offline_cache.deleted_events.keys())  # deleted from cache
        self.assertNotIn(event, self.plugin.offline_cache.deleted_events.values())

    def test_update_event(self):
        # Test updating of an event that is synchronized
        # 1) create event
        event = CalendarPluginDataGenerator.generate_event(title='Test Event')
        created_event = self.plugin.create_event(event, days_in_future=7, days_in_past=0)
        created_event.title = "Updated Test Event"
        # 2) update event
        updated_event = self.plugin.update_event(created_event, days_in_future=7, days_in_past=0)
        # 3) test assertions
        self.assertEqual(updated_event.title, "Updated Test Event")
        self.assertNotIn(event.id, self.plugin.offline_cache.updated_events.keys())  # not in cache
        self.assertNotIn(event, self.plugin.offline_cache.updated_events.values())

    def test_update_event_sync_fail(self):
        # Test updating of an event that fails to sync
        # 1) create event
        created_event = self.plugin.create_event(CalendarPluginDataGenerator.generate_event(title='Test Event'),
                                                 days_in_future=7, days_in_past=0)
        created_event.title = "Updated Test Event"
        # 2) mock update failure
        self.plugin._update_synced_event = MagicMock(side_effect=CalendarSyncException())
        updated_event = self.plugin.update_event(created_event, days_in_future=7, days_in_past=0)
        # 3) test assertions
        self.assertEqual(updated_event.title, "Updated Test Event")  # update should contain changes anyway
        self.assertIn(created_event.id, self.plugin.offline_cache.updated_events.keys())  # cache contains event
        self.assertIn(created_event, self.plugin.offline_cache.updated_events.values())
        # 4 try failing cache-update
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 5) test assertions
        self.assertIn(created_event.id, self.plugin.offline_cache.updated_events.keys())  # cache contains event
        self.assertIn(created_event, self.plugin.offline_cache.updated_events.values())
        # 6) mock cache-update success
        self.plugin._update_synced_event = types.MethodType(MockPlugin._update_synced_event, self)
        self.plugin.apply_offline_cache(days_in_future=7, days_in_past=0)
        # 7) test assertions
        self.assertNotIn(created_event.id, self.plugin.offline_cache.updated_events.keys())  # deleted from cache
        self.assertNotIn(created_event, self.plugin.offline_cache.updated_events.values())


if __name__ == '__main__':
    unittest.main()
