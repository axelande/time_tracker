import customtkinter
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from ..config import AppConfig
from ..core.event_bus import EventBus, EventType
from ..core.timer_engine import TimerEngine
from ..core.window_tracker import WindowTracker, Win32WindowInfoProvider
from ..core.idle_detector import IdleDetector, Win32IdleTimeProvider
from ..database.connection import DatabaseConnection
from ..database.schema import initialize_database
from ..database.repositories import (
    ProjectRepository,
    TimeEntryRepository,
    WindowEventRepository,
    IdlePeriodRepository,
    SettingsRepository,
)
from .floating_timer import FloatingTimer
from .frames.dashboard_frame import DashboardFrame
from .frames.projects_frame import ProjectsFrame
from .frames.reports_frame import ReportsFrame
from .frames.settings_frame import SettingsFrame


class App(customtkinter.CTk):
    """Main application window and orchestrator."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        super().__init__()

        self._config = config or AppConfig()
        self.title("Time Tracker")
        self.geometry("900x600")
        self.minsize(700, 500)

        # Set window icon
        icon_path = Path(__file__).resolve().parent.parent.parent / "assets" / "stopwatch.ico"
        if icon_path.exists():
            self.iconbitmap(str(icon_path))
            self._icon_path = str(icon_path)
        else:
            self._icon_path = None

        # Initialize infrastructure
        self._db = DatabaseConnection(self._config.db_path)
        initialize_database(self._db)
        self._event_bus = EventBus()

        # Initialize repositories
        self._project_repo = ProjectRepository(self._db)
        self._entry_repo = TimeEntryRepository(self._db)
        self._window_repo = WindowEventRepository(self._db)
        self._idle_repo = IdlePeriodRepository(self._db)
        self._settings_repo = SettingsRepository(self._db)

        # Load saved appearance
        saved_mode = self._settings_repo.get("appearance_mode", self._config.appearance_mode)
        customtkinter.set_appearance_mode(saved_mode)
        customtkinter.set_default_color_theme(self._config.color_theme)

        # Initialize core services
        self._timer_engine = TimerEngine(self._event_bus, self._entry_repo)
        self._window_tracker = WindowTracker(
            self._event_bus,
            self._window_repo,
            Win32WindowInfoProvider(),
            self._config.window_poll_interval_seconds,
        )
        self._idle_detector = IdleDetector(
            self._event_bus,
            self._idle_repo,
            Win32IdleTimeProvider(),
            self._config.idle_threshold_seconds,
        )

        # Load saved idle threshold
        saved_idle = self._settings_repo.get("idle_threshold_minutes", "")
        if saved_idle:
            self._idle_detector.threshold_seconds = int(saved_idle) * 60

        # Purge old data based on retention setting
        self._purge_old_data()

        # Build UI
        self._build_sidebar()
        self._build_content_area()

        # Floating timer
        self._floating_timer: Optional[FloatingTimer] = None
        self.after(200, self._create_floating_timer)

        # Subscribe to events
        self._subscribe_events()

        # Start background services
        self._timer_engine.recover_from_crash()
        self._window_tracker.start()
        self._idle_detector.start()

        # Start event bus polling
        self._poll_event_bus()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_sidebar(self) -> None:
        self._sidebar = customtkinter.CTkFrame(self, width=180, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_rowconfigure(5, weight=1)

        logo_label = customtkinter.CTkLabel(
            self._sidebar,
            text="Time Tracker",
            font=customtkinter.CTkFont(size=20, weight="bold"),
        )
        logo_label.grid(row=0, column=0, padx=20, pady=(20, 20))

        nav_items = [
            ("Dashboard", self._show_dashboard),
            ("Projects", self._show_projects),
            ("Reports", self._show_reports),
            ("Settings", self._show_settings),
        ]
        self._nav_buttons = {}
        for i, (label, command) in enumerate(nav_items, start=1):
            btn = customtkinter.CTkButton(
                self._sidebar,
                text=label,
                command=command,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                anchor="w",
                height=35,
            )
            btn.grid(row=i, column=0, padx=10, pady=2, sticky="ew")
            self._nav_buttons[label] = btn

    def _build_content_area(self) -> None:
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._content_frame = customtkinter.CTkFrame(self)
        self._content_frame.grid(row=0, column=1, sticky="nsew", padx=10, pady=10)
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        self._frames = {}
        self._frames["Dashboard"] = DashboardFrame(
            self._content_frame,
            self._project_repo,
            self._entry_repo,
            self._timer_engine,
            self._event_bus,
        )
        self._frames["Projects"] = ProjectsFrame(
            self._content_frame, self._project_repo, self._event_bus
        )
        self._frames["Reports"] = ReportsFrame(
            self._content_frame,
            self._entry_repo,
            self._window_repo,
            self._project_repo,
            self._idle_repo,
            self._timer_engine,
        )
        self._frames["Settings"] = SettingsFrame(
            self._content_frame,
            self._settings_repo,
            self._idle_detector,
            self._config,
        )

        for frame in self._frames.values():
            frame.grid(row=0, column=0, sticky="nsew")

        self._show_dashboard()

    def _highlight_nav(self, active: str) -> None:
        for name, btn in self._nav_buttons.items():
            if name == active:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

    def _show_dashboard(self) -> None:
        self._frames["Dashboard"].refresh()
        self._frames["Dashboard"].tkraise()
        self._highlight_nav("Dashboard")

    def _show_projects(self) -> None:
        self._frames["Projects"].refresh()
        self._frames["Projects"].tkraise()
        self._highlight_nav("Projects")

    def _show_reports(self) -> None:
        self._frames["Reports"].refresh()
        self._frames["Reports"].tkraise()
        self._highlight_nav("Reports")

    def _show_settings(self) -> None:
        self._frames["Settings"].tkraise()
        self._highlight_nav("Settings")

    def _create_floating_timer(self) -> None:
        projects = self._project_repo.get_all()
        self._floating_timer = FloatingTimer(
            master=self,
            projects=projects,
            on_start=lambda pid: self._timer_engine.start(pid),
            on_stop=lambda: self._timer_engine.stop(),
            on_switch=lambda pid: self._timer_engine.switch(pid),
            on_open_main=self._bring_to_front,
        )
        if self._icon_path:
            self._floating_timer.after(
                150, lambda: self._floating_timer.iconbitmap(self._icon_path)
            )

    def _bring_to_front(self) -> None:
        self.deiconify()
        self.lift()
        self.focus_force()

    def _subscribe_events(self) -> None:
        self._event_bus.subscribe(EventType.TIMER_TICK, self._on_timer_tick)
        self._event_bus.subscribe(EventType.TIMER_STARTED, self._on_timer_started)
        self._event_bus.subscribe(EventType.TIMER_STOPPED, self._on_timer_stopped)
        self._event_bus.subscribe(EventType.IDLE_STARTED, self._on_idle_started)
        self._event_bus.subscribe(EventType.IDLE_ENDED, self._on_idle_ended)
        self._event_bus.subscribe(EventType.PROJECT_CREATED, self._on_project_changed)
        self._event_bus.subscribe(EventType.PROJECT_UPDATED, self._on_project_changed)
        self._event_bus.subscribe(EventType.PROJECT_ARCHIVED, self._on_project_changed)

    def _on_timer_tick(self, elapsed: float) -> None:
        if self._floating_timer:
            self._floating_timer.update_time(elapsed)

    def _on_timer_started(self, payload) -> None:
        project_id, _ = payload
        project = self._project_repo.get_by_id(project_id)
        if self._floating_timer and project:
            self._floating_timer.set_running(True, project.name)

    def _on_timer_stopped(self, entry) -> None:
        if self._floating_timer:
            self._floating_timer.set_running(False)

    def _on_idle_started(self, timestamp) -> None:
        self._timer_engine.on_idle_started(timestamp)
        self._window_tracker.pause()

    def _on_idle_ended(self, idle_period) -> None:
        self._timer_engine.on_idle_ended(idle_period.end_time)
        self._window_tracker.resume()

    def _on_project_changed(self, project) -> None:
        if self._floating_timer:
            projects = self._project_repo.get_all()
            self._floating_timer.update_projects(projects)

    def _poll_event_bus(self) -> None:
        self._event_bus.process_pending()
        self.after(self._config.gui_poll_interval_ms, self._poll_event_bus)

    def _purge_old_data(self) -> None:
        retention_months = int(
            self._settings_repo.get(
                "data_retention_months",
                str(self._config.data_retention_months),
            )
        )
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_months * 30)
        self._entry_repo.purge_before(cutoff)
        self._window_repo.purge_before(cutoff)
        self._idle_repo.purge_before(cutoff)

    def _on_close(self) -> None:
        self._timer_engine.stop()
        self._window_tracker.stop()
        self._idle_detector.stop()
        self._db.close()
        self.destroy()
