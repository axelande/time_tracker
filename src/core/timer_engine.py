import threading
from datetime import datetime, timezone, timedelta
from typing import Optional

from .event_bus import EventBus, EventType
from .models import TimeEntry
from ..database.repositories import TimeEntryRepository


class TimerEngine:
    """Manages the active project timer. Thread-safe for access from GUI thread."""

    def __init__(self, event_bus: EventBus, entry_repo: TimeEntryRepository) -> None:
        self._event_bus = event_bus
        self._entry_repo = entry_repo
        self._lock = threading.Lock()
        self._active_entry: Optional[TimeEntry] = None
        self._idle_accumulated_seconds: float = 0.0
        self._idle_started_at: Optional[datetime] = None
        self._today_prior_seconds: float = 0.0
        self._tick_thread: Optional[threading.Thread] = None
        self._stop_tick = threading.Event()
        self._tick_date = None

    @property
    def is_running(self) -> bool:
        return self._active_entry is not None

    @property
    def active_project_id(self) -> Optional[int]:
        return self._active_entry.project_id if self._active_entry else None

    @property
    def elapsed_seconds(self) -> float:
        with self._lock:
            if not self._active_entry or not self._active_entry.start_time:
                return 0.0

            now = datetime.now(timezone.utc)
            elapsed = (now - self._active_entry.start_time).total_seconds()
            idle_total = self._idle_accumulated_seconds
            if self._idle_started_at:
                idle_total += (now - self._idle_started_at).total_seconds()

            return max(0.0, elapsed - idle_total) + self._today_prior_seconds

    def start(self, project_id: int) -> TimeEntry:
        """Start timing for a project. Stops any running timer first."""
        with self._lock:
            if self._active_entry:
                self._stop_internal()

            now = datetime.now(timezone.utc)
            entry = TimeEntry(project_id=project_id, start_time=now)
            entry = self._entry_repo.create(entry)
            self._active_entry = entry
            self._idle_accumulated_seconds = 0.0
            self._idle_started_at = None
            self._today_prior_seconds = self._get_today_prior_seconds(project_id)
            self._tick_date = datetime.now().date()
            self._event_bus.publish(EventType.TIMER_STARTED, (project_id, now))
            self._start_tick_thread()
            return entry

    def stop(self) -> Optional[TimeEntry]:
        """Stop the current timer. Returns the completed entry or None."""
        with self._lock:
            return self._stop_internal()

    def switch(self, project_id: int) -> TimeEntry:
        """Switch to a different project. Convenience for stop + start."""
        return self.start(project_id)

    def recover_from_crash(self) -> Optional[TimeEntry]:
        """On startup, check for entries with end_time=NULL (app crashed).
        Resume or close them."""
        running = self._entry_repo.get_running()
        if running:
            self._active_entry = running
            self._idle_accumulated_seconds = 0.0
            self._idle_started_at = None
            self._today_prior_seconds = self._get_today_prior_seconds(running.project_id)
            self._tick_date = datetime.now().date()
            self._start_tick_thread()
        return running

    def on_idle_started(self, at: Optional[datetime] = None) -> None:
        with self._lock:
            if not self._active_entry or self._idle_started_at is not None:
                return
            self._idle_started_at = at or datetime.now(timezone.utc)

    def on_idle_ended(self, at: Optional[datetime] = None) -> None:
        with self._lock:
            if not self._active_entry or self._idle_started_at is None:
                return

            end = at or datetime.now(timezone.utc)
            idle_duration = (end - self._idle_started_at).total_seconds()
            if idle_duration > 0:
                self._idle_accumulated_seconds += idle_duration
            self._idle_started_at = None

    def _stop_internal(self) -> Optional[TimeEntry]:
        if not self._active_entry:
            return None
        self._stop_tick_thread()
        now = datetime.now(timezone.utc)
        if self._idle_started_at:
            idle_duration = (now - self._idle_started_at).total_seconds()
            if idle_duration > 0:
                self._idle_accumulated_seconds += idle_duration
            self._idle_started_at = None

        start = self._active_entry.start_time
        total_duration = (now - start).total_seconds() if start else 0.0
        active_duration = max(0.0, total_duration - self._idle_accumulated_seconds)

        completed = self._entry_repo.finish(
            self._active_entry.id,
            now,
            duration_seconds=active_duration,
        )
        self._active_entry = None
        self._idle_accumulated_seconds = 0.0
        self._today_prior_seconds = 0.0
        self._tick_date = None
        self._event_bus.publish(EventType.TIMER_STOPPED, completed)
        return completed

    def _get_today_prior_seconds(self, project_id: int) -> float:
        """Sum of already-completed time entries for this project today."""
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        totals = self._entry_repo.get_total_by_project(start_of_day, end_of_day)
        for pid, total in totals:
            if pid == project_id:
                return total
        return 0.0

    def _start_tick_thread(self) -> None:
        self._stop_tick.clear()
        self._tick_thread = threading.Thread(
            target=self._tick_loop, daemon=True, name="TimerTick"
        )
        self._tick_thread.start()

    def _stop_tick_thread(self) -> None:
        self._stop_tick.set()
        if self._tick_thread:
            self._tick_thread.join(timeout=2.0)

    def _tick_loop(self) -> None:
        while not self._stop_tick.is_set():
            if self._active_entry:
                if self._tick_date and datetime.now().date() != self._tick_date:
                    self.stop()
                    return
                self._event_bus.publish(EventType.TIMER_TICK, self.elapsed_seconds)
            self._stop_tick.wait(timeout=1.0)
