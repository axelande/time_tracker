import threading
from datetime import datetime, timezone
from typing import Optional, Protocol

from .event_bus import EventBus, EventType
from .models import IdlePeriod
from ..database.repositories import IdlePeriodRepository


class IdleTimeProvider(Protocol):
    """Protocol for getting idle duration. Allows mocking."""

    def get_idle_seconds(self) -> float: ...


class Win32IdleTimeProvider:
    """Windows implementation using ctypes GetLastInputInfo."""

    def get_idle_seconds(self) -> float:
        import ctypes
        from ctypes import Structure, c_uint, sizeof, byref, windll

        class LASTINPUTINFO(Structure):
            _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = sizeof(lii)
        windll.user32.GetLastInputInfo(byref(lii))
        millis = windll.kernel32.GetTickCount() - lii.dwTime
        return millis / 1000.0


class IdleDetector:
    """Monitors user idle state. Runs on its own background thread."""

    def __init__(
        self,
        event_bus: EventBus,
        idle_repo: IdlePeriodRepository,
        provider: IdleTimeProvider,
        threshold_seconds: float = 300.0,
        poll_interval: float = 1.0,
    ) -> None:
        self._event_bus = event_bus
        self._idle_repo = idle_repo
        self._provider = provider
        self._threshold = threshold_seconds
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._is_idle: bool = False
        self._idle_start: Optional[datetime] = None

    @property
    def is_idle(self) -> bool:
        return self._is_idle

    @property
    def threshold_seconds(self) -> float:
        return self._threshold

    @threshold_seconds.setter
    def threshold_seconds(self, value: float) -> None:
        self._threshold = value

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="IdleDetector"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            self._check()
            self._stop_event.wait(timeout=self._poll_interval)

    def _check(self) -> None:
        idle_seconds = self._provider.get_idle_seconds()
        now = datetime.now(timezone.utc)

        if not self._is_idle and idle_seconds >= self._threshold:
            self._is_idle = True
            self._idle_start = now
            self._event_bus.publish(EventType.IDLE_STARTED, now)

        elif self._is_idle and idle_seconds < self._threshold:
            self._is_idle = False
            if self._idle_start:
                period = IdlePeriod(
                    start_time=self._idle_start,
                    end_time=now,
                    duration_seconds=(now - self._idle_start).total_seconds(),
                )
                self._idle_repo.create(period)
                self._event_bus.publish(EventType.IDLE_ENDED, period)
            self._idle_start = None
