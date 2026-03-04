import queue
from enum import Enum, auto
from typing import Any, Callable
from dataclasses import dataclass


class EventType(Enum):
    WINDOW_CHANGED = auto()
    IDLE_STARTED = auto()
    IDLE_ENDED = auto()
    TIMER_STARTED = auto()
    TIMER_STOPPED = auto()
    TIMER_TICK = auto()
    PROJECT_CREATED = auto()
    PROJECT_UPDATED = auto()
    PROJECT_ARCHIVED = auto()


@dataclass
class Event:
    type: EventType
    payload: Any


class EventBus:
    def __init__(self) -> None:
        self._queue: queue.Queue[Event] = queue.Queue()
        self._subscribers: dict[EventType, list[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: EventType, callback: Callable[[Any], None]) -> None:
        self._subscribers.setdefault(event_type, []).append(callback)

    def publish(self, event_type: EventType, payload: Any = None) -> None:
        """Thread-safe. Called from any thread."""
        self._queue.put(Event(type=event_type, payload=payload))

    def process_pending(self) -> None:
        """Called from main (GUI) thread. Drains the queue and dispatches to subscribers."""
        while not self._queue.empty():
            try:
                event = self._queue.get_nowait()
                for callback in self._subscribers.get(event.type, []):
                    callback(event.payload)
            except queue.Empty:
                break
