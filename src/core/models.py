from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Project:
    id: Optional[int] = None
    name: str = ""
    color: str = "#3B8ED0"
    is_archived: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class TimeEntry:
    id: Optional[int] = None
    project_id: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    note: str = ""
    created_at: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self.end_time is None


@dataclass
class WindowEvent:
    id: Optional[int] = None
    window_title: str = ""
    app_name: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    project_id: Optional[int] = None


@dataclass
class IdlePeriod:
    id: Optional[int] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0


@dataclass
class WindowInfo:
    """Transient snapshot of the current foreground window. Not persisted directly."""
    title: str
    app_name: str
    pid: int
    timestamp: datetime
