import customtkinter
from datetime import datetime, timezone, timedelta

from ...core.event_bus import EventBus, EventType
from ...core.timer_engine import TimerEngine
from ...database.repositories import ProjectRepository, TimeEntryRepository
from ..components.time_display import format_seconds, format_hours_minutes


class DashboardFrame(customtkinter.CTkFrame):
    def __init__(
        self,
        master,
        project_repo: ProjectRepository,
        entry_repo: TimeEntryRepository,
        timer_engine: TimerEngine,
        event_bus: EventBus,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._project_repo = project_repo
        self._entry_repo = entry_repo
        self._timer_engine = timer_engine
        self._event_bus = event_bus

        self.grid_columnconfigure(0, weight=1)

        # Title
        title = customtkinter.CTkLabel(
            self, text="Dashboard",
            font=customtkinter.CTkFont(size=24, weight="bold"),
        )
        title.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Current timer section
        self._timer_frame = customtkinter.CTkFrame(self)
        self._timer_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        self._timer_frame.grid_columnconfigure(1, weight=1)

        customtkinter.CTkLabel(
            self._timer_frame, text="Currently Tracking:",
            font=customtkinter.CTkFont(size=14),
        ).grid(row=0, column=0, padx=15, pady=10)

        self._current_label = customtkinter.CTkLabel(
            self._timer_frame, text="Nothing",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        )
        self._current_label.grid(row=0, column=1, padx=10, pady=10, sticky="w")

        self._elapsed_label = customtkinter.CTkLabel(
            self._timer_frame, text="00:00:00",
            font=customtkinter.CTkFont(family="Consolas", size=18, weight="bold"),
        )
        self._elapsed_label.grid(row=0, column=2, padx=15, pady=10)

        # Quick-start buttons
        customtkinter.CTkLabel(
            self, text="Quick Start",
            font=customtkinter.CTkFont(size=16, weight="bold"),
        ).grid(row=2, column=0, padx=20, pady=(20, 5), sticky="w")

        self._quick_start_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        self._quick_start_frame.grid(row=3, column=0, padx=20, pady=5, sticky="ew")

        # Today's summary
        customtkinter.CTkLabel(
            self, text="Today's Summary",
            font=customtkinter.CTkFont(size=16, weight="bold"),
        ).grid(row=4, column=0, padx=20, pady=(20, 5), sticky="w")

        self._summary_frame = customtkinter.CTkScrollableFrame(self, height=200)
        self._summary_frame.grid(row=5, column=0, padx=20, pady=(5, 20), sticky="nsew")
        self._summary_frame.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(5, weight=1)

        # Subscribe to events
        self._event_bus.subscribe(EventType.TIMER_STARTED, self._on_timer_started)
        self._event_bus.subscribe(EventType.TIMER_STOPPED, self._on_timer_stopped)
        self._event_bus.subscribe(EventType.TIMER_TICK, self._on_timer_tick)

        self.refresh()

    def refresh(self) -> None:
        self._build_quick_start_buttons()
        self._build_today_summary()
        self._update_current_timer_display()

    def _build_quick_start_buttons(self) -> None:
        for widget in self._quick_start_frame.winfo_children():
            widget.destroy()

        projects = self._project_repo.get_all()
        for i, project in enumerate(projects):
            btn = customtkinter.CTkButton(
                self._quick_start_frame,
                text=project.name,
                fg_color=project.color,
                hover_color=self._darken_color(project.color),
                width=120,
                height=32,
                command=lambda pid=project.id: self._start_project(pid),
            )
            btn.grid(row=0, column=i, padx=4, pady=4)

    def _build_today_summary(self) -> None:
        for widget in self._summary_frame.winfo_children():
            widget.destroy()

        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        totals = self._entry_repo.get_total_by_project(start_of_day, end_of_day)
        projects = {p.id: p for p in self._project_repo.get_all(include_archived=True)}

        if not totals:
            customtkinter.CTkLabel(
                self._summary_frame,
                text="No time tracked today yet.",
                text_color="gray",
            ).grid(row=0, column=0, padx=10, pady=20)
            return

        total_all = sum(t for _, t in totals)

        for i, (project_id, total_secs) in enumerate(totals):
            project = projects.get(project_id)
            name = project.name if project else f"Project #{project_id}"
            color = project.color if project else "#888888"
            fraction = total_secs / total_all if total_all > 0 else 0

            row_frame = customtkinter.CTkFrame(self._summary_frame, fg_color="transparent")
            row_frame.grid(row=i, column=0, padx=5, pady=3, sticky="ew")
            row_frame.grid_columnconfigure(1, weight=1)

            customtkinter.CTkLabel(
                row_frame, text=name, width=120, anchor="w",
                font=customtkinter.CTkFont(weight="bold"),
            ).grid(row=0, column=0, padx=(5, 10))

            bar = customtkinter.CTkProgressBar(row_frame, progress_color=color)
            bar.set(fraction)
            bar.grid(row=0, column=1, padx=5, sticky="ew")

            customtkinter.CTkLabel(
                row_frame, text=format_hours_minutes(total_secs), width=80,
            ).grid(row=0, column=2, padx=(10, 5))

    def _update_current_timer_display(self) -> None:
        if self._timer_engine.is_running:
            project = self._project_repo.get_by_id(self._timer_engine.active_project_id)
            name = project.name if project else "Unknown"
            self._current_label.configure(text=name)
            self._elapsed_label.configure(
                text=format_seconds(self._timer_engine.elapsed_seconds)
            )
        else:
            self._current_label.configure(text="Nothing")
            self._elapsed_label.configure(text="00:00:00")

    def _start_project(self, project_id: int) -> None:
        self._timer_engine.start(project_id)

    def _on_timer_started(self, payload) -> None:
        project_id, _ = payload
        project = self._project_repo.get_by_id(project_id)
        name = project.name if project else "Unknown"
        self._current_label.configure(text=name)

    def _on_timer_stopped(self, entry) -> None:
        self._current_label.configure(text="Nothing")
        self._elapsed_label.configure(text="00:00:00")
        self._build_today_summary()

    def _on_timer_tick(self, elapsed: float) -> None:
        self._elapsed_label.configure(text=format_seconds(elapsed))

    @staticmethod
    def _darken_color(hex_color: str) -> str:
        """Darken a hex color by 20%."""
        try:
            r = int(hex_color[1:3], 16)
            g = int(hex_color[3:5], 16)
            b = int(hex_color[5:7], 16)
            r = max(0, int(r * 0.8))
            g = max(0, int(g * 0.8))
            b = max(0, int(b * 0.8))
            return f"#{r:02x}{g:02x}{b:02x}"
        except (ValueError, IndexError):
            return "#333333"
