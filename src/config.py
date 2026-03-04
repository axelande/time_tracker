from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AppConfig:
    db_path: Path = field(
        default_factory=lambda: Path.home() / ".time_tracker" / "time_tracker.db"
    )
    idle_threshold_seconds: int = 300
    window_poll_interval_seconds: float = 1.0
    gui_poll_interval_ms: int = 100
    floating_timer_opacity: float = 0.9
    appearance_mode: str = "dark"
    color_theme: str = "blue"
    data_retention_months: int = 2
