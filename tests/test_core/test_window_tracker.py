from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from src.core.event_bus import EventBus, EventType
from src.core.window_tracker import WindowTracker
from src.core.models import WindowInfo, WindowEvent
from src.database.repositories import WindowEventRepository


class TestWindowTracker:
    def _make_tracker(self, in_memory_db, mock_window_provider):
        event_bus = EventBus()
        window_repo = WindowEventRepository(in_memory_db)
        tracker = WindowTracker(event_bus, window_repo, mock_window_provider, poll_interval=1.0)
        return tracker, event_bus, window_repo

    def test_poll_detects_new_window(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        now = datetime.now(timezone.utc)
        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="test.py - VS Code", app_name="code.exe", pid=1234, timestamp=now
        )

        tracker._poll()

        assert tracker._current_title == "test.py - VS Code"
        assert tracker._current_app == "code.exe"
        assert tracker._current_start == now

    def test_window_change_flushes_previous_event(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        base = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # First window
        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="VS Code", app_name="code.exe", pid=100, timestamp=base
        )
        tracker._poll()

        # Switch to second window (2 minutes later)
        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="Chrome", app_name="chrome.exe", pid=200, timestamp=base + timedelta(minutes=2)
        )
        tracker._poll()

        # The first window event should have been flushed
        events = repo.get_by_date_range(base - timedelta(hours=1), base + timedelta(hours=1))
        assert len(events) == 1
        assert events[0].app_name == "code.exe"
        assert events[0].window_title == "VS Code"

        # Event bus should have the event too
        received = []
        bus.subscribe(EventType.WINDOW_CHANGED, lambda p: received.append(p))
        bus.process_pending()
        assert len(received) == 1

    def test_same_window_no_flush(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        base = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        info = WindowInfo(title="VS Code", app_name="code.exe", pid=100, timestamp=base)
        mock_window_provider.get_foreground_window_info.return_value = info

        tracker._poll()
        tracker._poll()  # Same window, different timestamp doesn't matter since title/app match

        events = repo.get_by_date_range(base - timedelta(hours=1), base + timedelta(hours=1))
        assert len(events) == 0  # Nothing flushed yet

    def test_stop_flushes_current_event(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        base = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="VS Code", app_name="code.exe", pid=100, timestamp=base
        )
        tracker._poll()

        # Manually set start time in the past so duration > 1s
        tracker._current_start = base - timedelta(seconds=5)
        tracker._flush_current_event()

        events = repo.get_by_date_range(base - timedelta(hours=1), base + timedelta(hours=1))
        assert len(events) == 1
        assert events[0].app_name == "code.exe"

    def test_pause_flushes_and_stops_accumulation(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        base = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="VS Code", app_name="code.exe", pid=100, timestamp=base
        )
        tracker._poll()
        tracker._current_start = base - timedelta(seconds=5)

        tracker.pause()
        assert tracker._is_paused is True
        assert tracker._current_title is None  # state cleared after flush

        events = repo.get_by_date_range(base - timedelta(hours=1), base + timedelta(hours=1))
        assert len(events) == 1

        # Resume and verify new accumulation begins
        tracker.resume()
        assert tracker._is_paused is False

    def test_sub_second_events_ignored(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        now = datetime.now(timezone.utc)

        # Window A for less than 1 second
        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="A", app_name="a.exe", pid=1, timestamp=now
        )
        tracker._poll()

        # Immediately switch to B (start time is almost the same as now)
        mock_window_provider.get_foreground_window_info.return_value = WindowInfo(
            title="B", app_name="b.exe", pid=2, timestamp=now + timedelta(milliseconds=100)
        )
        tracker._poll()

        events = repo.get_by_date_range(now - timedelta(hours=1), now + timedelta(hours=1))
        assert len(events) == 0  # Sub-second event ignored

    def test_null_provider_result_ignored(self, in_memory_db, mock_window_provider):
        tracker, bus, repo = self._make_tracker(in_memory_db, mock_window_provider)
        mock_window_provider.get_foreground_window_info.return_value = None
        tracker._poll()
        assert tracker._current_title is None
