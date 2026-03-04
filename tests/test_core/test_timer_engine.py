import time
from datetime import datetime, timedelta, timezone

from src.core.event_bus import EventBus, EventType
from src.core.timer_engine import TimerEngine
from src.core.models import Project, TimeEntry
from src.database.repositories import ProjectRepository, TimeEntryRepository


class TestTimerEngine:
    def _make_engine(self, in_memory_db):
        """Helper: creates a TimerEngine with a real DB and event bus."""
        ProjectRepository(in_memory_db).create(Project(name="Project A"))
        ProjectRepository(in_memory_db).create(Project(name="Project B"))
        event_bus = EventBus()
        entry_repo = TimeEntryRepository(in_memory_db)
        engine = TimerEngine(event_bus, entry_repo)
        return engine, event_bus, entry_repo

    def test_start_creates_running_entry(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        entry = engine.start(1)
        assert entry.id is not None
        assert entry.project_id == 1
        assert engine.is_running is True
        assert engine.active_project_id == 1
        engine.stop()

    def test_stop_finishes_entry(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        engine.start(1)
        completed = engine.stop()
        assert completed is not None
        assert completed.end_time is not None
        assert completed.duration_seconds is not None
        assert completed.duration_seconds >= 0
        assert engine.is_running is False

    def test_stop_when_not_running_returns_none(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        result = engine.stop()
        assert result is None

    def test_start_while_running_stops_previous(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        engine.start(1)
        entry2 = engine.start(2)

        assert engine.active_project_id == 2
        # The old entry should be finished
        assert repo.get_running().id == entry2.id
        engine.stop()

    def test_switch_stops_old_starts_new(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        engine.start(1)
        new_entry = engine.switch(2)
        assert new_entry.project_id == 2
        assert engine.active_project_id == 2
        engine.stop()

    def test_elapsed_seconds_increases(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        engine.start(1)
        time.sleep(0.05)
        elapsed = engine.elapsed_seconds
        assert elapsed > 0
        engine.stop()

    def test_elapsed_seconds_zero_when_not_running(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        assert engine.elapsed_seconds == 0.0

    def test_recover_from_crash_resumes_running_entry(self, in_memory_db):
        engine1, bus1, repo = self._make_engine(in_memory_db)
        engine1.start(1)
        # Simulate crash: don't call stop, just create a new engine
        engine1._stop_tick_thread()  # clean up tick thread only

        engine2 = TimerEngine(EventBus(), repo)
        recovered = engine2.recover_from_crash()
        assert recovered is not None
        assert recovered.project_id == 1
        assert engine2.is_running is True
        engine2.stop()

    def test_events_published_on_start_and_stop(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        started_events = []
        stopped_events = []
        bus.subscribe(EventType.TIMER_STARTED, lambda p: started_events.append(p))
        bus.subscribe(EventType.TIMER_STOPPED, lambda p: stopped_events.append(p))

        engine.start(1)
        bus.process_pending()
        assert len(started_events) == 1
        assert started_events[0][0] == 1  # project_id

        engine.stop()
        bus.process_pending()
        assert len(stopped_events) == 1
        assert isinstance(stopped_events[0], TimeEntry)

    def test_elapsed_seconds_excludes_ongoing_idle(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        engine.start(1)

        now = datetime.now(timezone.utc)
        engine._active_entry.start_time = now - timedelta(seconds=10)
        engine.on_idle_started(now - timedelta(seconds=4))

        elapsed = engine.elapsed_seconds
        assert 5.5 <= elapsed <= 6.5
        engine.stop()

    def test_midnight_auto_stop(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        stopped_events = []
        bus.subscribe(EventType.TIMER_STOPPED, lambda p: stopped_events.append(p))

        engine.start(1)
        assert engine.is_running is True

        # Simulate midnight by setting _tick_date to yesterday
        from datetime import date
        engine._tick_date = date.today() - timedelta(days=1)

        # Run one tick cycle — should detect day change and auto-stop
        engine._tick_loop()

        bus.process_pending()
        assert engine.is_running is False
        assert len(stopped_events) == 1
        assert isinstance(stopped_events[0], TimeEntry)

    def test_stop_persists_duration_without_idle(self, in_memory_db):
        engine, bus, repo = self._make_engine(in_memory_db)
        entry = engine.start(1)

        now = datetime.now(timezone.utc)
        engine._active_entry.start_time = now - timedelta(seconds=10)
        engine.on_idle_started(now - timedelta(seconds=4))
        engine.on_idle_ended(now - timedelta(seconds=1))

        completed = engine.stop()
        assert completed is not None
        assert completed.id == entry.id
        assert completed.duration_seconds is not None
        assert 6.5 <= completed.duration_seconds <= 7.5
