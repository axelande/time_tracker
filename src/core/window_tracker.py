import threading
from datetime import datetime, timezone
from typing import Optional, Protocol

from .models import WindowInfo, WindowEvent
from .event_bus import EventBus, EventType
from ..database.repositories import WindowEventRepository


class WindowInfoProvider(Protocol):
    """Protocol for OS-level window info retrieval. Allows mocking."""

    def get_foreground_window_info(self) -> Optional[WindowInfo]: ...


class Win32WindowInfoProvider:
    """Windows implementation using win32gui + psutil."""

    def get_foreground_window_info(self) -> Optional[WindowInfo]:
        import win32gui
        import win32process
        import psutil

        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd == 0:
                return None
            title = win32gui.GetWindowText(hwnd)
            if not title:
                return None
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            try:
                process = psutil.Process(pid)
                app_name = process.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                app_name = "unknown"
            return WindowInfo(
                title=title,
                app_name=app_name,
                pid=pid,
                timestamp=datetime.now(timezone.utc),
            )
        except Exception:
            return None


class WindowTracker:
    """Background thread that polls the foreground window and emits merged events."""

    def __init__(
        self,
        event_bus: EventBus,
        window_repo: WindowEventRepository,
        provider: WindowInfoProvider,
        poll_interval: float = 1.0,
    ) -> None:
        self._event_bus = event_bus
        self._window_repo = window_repo
        self._provider = provider
        self._poll_interval = poll_interval
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        self._current_title: Optional[str] = None
        self._current_app: Optional[str] = None
        self._current_start: Optional[datetime] = None
        self._is_paused: bool = False

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="WindowTracker"
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=3.0)
        self._flush_current_event()

    def pause(self) -> None:
        """Called when idle is detected. Flushes current event, stops accumulating."""
        self._flush_current_event()
        self._is_paused = True

    def resume(self) -> None:
        """Called when user returns from idle."""
        self._is_paused = False

    def _run(self) -> None:
        while not self._stop_event.is_set():
            if not self._is_paused:
                self._poll()
            self._stop_event.wait(timeout=self._poll_interval)

    def _poll(self) -> None:
        info = self._provider.get_foreground_window_info()
        if info is None:
            return
        now = info.timestamp

        if info.title != self._current_title or info.app_name != self._current_app:
            self._flush_current_event()
            self._current_title = info.title
            self._current_app = info.app_name
            self._current_start = now

    def _flush_current_event(self) -> None:
        if self._current_title and self._current_start:
            now = datetime.now(timezone.utc)
            duration = (now - self._current_start).total_seconds()
            if duration >= 1.0:
                event = WindowEvent(
                    window_title=self._current_title,
                    app_name=self._current_app or "unknown",
                    start_time=self._current_start,
                    end_time=now,
                    duration_seconds=duration,
                )
                self._window_repo.create(event)
                self._event_bus.publish(EventType.WINDOW_CHANGED, event)
        self._current_title = None
        self._current_app = None
        self._current_start = None
