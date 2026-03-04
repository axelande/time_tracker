from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from src.core.event_bus import EventBus, EventType
from src.core.idle_detector import IdleDetector
from src.core.models import IdlePeriod
from src.database.repositories import IdlePeriodRepository


class TestIdleDetector:
    def _make_detector(self, in_memory_db, mock_idle_provider, threshold=300.0):
        event_bus = EventBus()
        idle_repo = IdlePeriodRepository(in_memory_db)
        detector = IdleDetector(
            event_bus, idle_repo, mock_idle_provider,
            threshold_seconds=threshold, poll_interval=1.0
        )
        return detector, event_bus, idle_repo

    def test_idle_detected_after_threshold(self, in_memory_db, mock_idle_provider):
        detector, bus, repo = self._make_detector(in_memory_db, mock_idle_provider)
        started_events = []
        bus.subscribe(EventType.IDLE_STARTED, lambda p: started_events.append(p))

        # Not idle
        mock_idle_provider.get_idle_seconds.return_value = 0.0
        detector._check()
        bus.process_pending()
        assert len(started_events) == 0

        # Still not idle
        mock_idle_provider.get_idle_seconds.return_value = 200.0
        detector._check()
        bus.process_pending()
        assert len(started_events) == 0

        # Now idle
        mock_idle_provider.get_idle_seconds.return_value = 301.0
        detector._check()
        bus.process_pending()
        assert len(started_events) == 1
        assert detector.is_idle is True

    def test_idle_ended_when_input_resumes(self, in_memory_db, mock_idle_provider):
        detector, bus, repo = self._make_detector(in_memory_db, mock_idle_provider)
        ended_events = []
        bus.subscribe(EventType.IDLE_ENDED, lambda p: ended_events.append(p))

        base = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)

        # Go idle at t=0
        mock_idle_provider.get_idle_seconds.return_value = 301.0
        with patch("src.core.idle_detector.datetime") as mock_dt:
            mock_dt.now.return_value = base
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            detector._check()

        # Come back at t=10min
        mock_idle_provider.get_idle_seconds.return_value = 0.0
        with patch("src.core.idle_detector.datetime") as mock_dt:
            mock_dt.now.return_value = base + timedelta(minutes=10)
            mock_dt.side_effect = lambda *a, **k: datetime(*a, **k)
            detector._check()

        bus.process_pending()

        assert len(ended_events) == 1
        assert isinstance(ended_events[0], IdlePeriod)
        assert ended_events[0].duration_seconds == 600.0
        assert detector.is_idle is False

    def test_no_idle_event_below_threshold(self, in_memory_db, mock_idle_provider):
        detector, bus, repo = self._make_detector(in_memory_db, mock_idle_provider)
        started_events = []
        bus.subscribe(EventType.IDLE_STARTED, lambda p: started_events.append(p))

        mock_idle_provider.get_idle_seconds.return_value = 200.0
        detector._check()
        detector._check()
        detector._check()
        bus.process_pending()

        assert len(started_events) == 0
        assert detector.is_idle is False

    def test_threshold_can_be_changed(self, in_memory_db, mock_idle_provider):
        detector, bus, repo = self._make_detector(in_memory_db, mock_idle_provider, threshold=300.0)
        started_events = []
        bus.subscribe(EventType.IDLE_STARTED, lambda p: started_events.append(p))

        # 100 seconds is below 300 threshold
        mock_idle_provider.get_idle_seconds.return_value = 100.0
        detector._check()
        bus.process_pending()
        assert len(started_events) == 0

        # Lower threshold to 60
        detector.threshold_seconds = 60.0
        detector._check()
        bus.process_pending()
        assert len(started_events) == 1

    def test_repeated_idle_checks_dont_duplicate_events(self, in_memory_db, mock_idle_provider):
        detector, bus, repo = self._make_detector(in_memory_db, mock_idle_provider)
        started_events = []
        bus.subscribe(EventType.IDLE_STARTED, lambda p: started_events.append(p))

        mock_idle_provider.get_idle_seconds.return_value = 301.0
        detector._check()
        detector._check()
        detector._check()
        bus.process_pending()

        # Only one IDLE_STARTED event should fire
        assert len(started_events) == 1
