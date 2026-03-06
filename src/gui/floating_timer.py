import customtkinter
from typing import Optional, Callable

from ..core.models import Project
from .components.time_display import format_seconds


class FloatingTimer(customtkinter.CTkToplevel):
    """Always-on-top, borderless, draggable floating timer widget."""

    WIDTH = 300
    HEIGHT = 90

    def __init__(
        self,
        master: customtkinter.CTk,
        projects: list[Project],
        on_start: Callable[[int], None],
        on_stop: Callable[[], None],
        on_switch: Callable[[int], None],
        on_open_main: Callable[[], None],
    ) -> None:
        super().__init__(master)

        self.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.after(100, lambda: self.overrideredirect(True))
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.9)

        # Drag state
        self._offset_x = 0
        self._offset_y = 0

        self._on_start = on_start
        self._on_stop = on_stop
        self._on_switch = on_switch
        self._on_open_main = on_open_main

        # Main frame
        self._main_frame = customtkinter.CTkFrame(self, corner_radius=8)
        self._main_frame.pack(fill="both", expand=True, padx=2, pady=2)
        self._main_frame.bind("<Button-1>", self._start_drag)
        self._main_frame.bind("<B1-Motion>", self._on_drag)

        # Top row: project selector + time display
        top_row = customtkinter.CTkFrame(self._main_frame, fg_color="transparent")
        top_row.pack(fill="x", padx=6, pady=(6, 2))

        self._project_var = customtkinter.StringVar()
        self._project_menu = customtkinter.CTkOptionMenu(
            top_row,
            variable=self._project_var,
            values=[p.name for p in projects] if projects else ["No projects"],
            command=self._on_project_selected,
            width=150,
            height=28,
        )
        self._project_menu.pack(side="left", padx=(0, 6))

        self._time_label = customtkinter.CTkLabel(
            top_row,
            text="00:00:00",
            font=customtkinter.CTkFont(family="Consolas", size=18, weight="bold"),
        )
        self._time_label.pack(side="right")

        # Bottom row: start/stop + open main
        bottom_row = customtkinter.CTkFrame(self._main_frame, fg_color="transparent")
        bottom_row.pack(fill="x", padx=6, pady=(2, 6))

        self._toggle_btn = customtkinter.CTkButton(
            bottom_row,
            text="Start",
            width=90,
            height=28,
            command=self._toggle_timer,
            fg_color="#2FA572",
            hover_color="#1A7A50",
        )
        self._toggle_btn.pack(side="left", padx=(0, 4))

        self._main_btn = customtkinter.CTkButton(
            bottom_row,
            text="Open",
            width=60,
            height=28,
            command=self._on_open_main,
        )
        self._main_btn.pack(side="right")

        # State
        self._is_running = False
        self._projects = projects
        self._selected_project_id: Optional[int] = None
        if projects:
            self._selected_project_id = projects[0].id
            self._project_var.set(projects[0].name)

    def update_time(self, elapsed_seconds: float) -> None:
        self._time_label.configure(text=format_seconds(elapsed_seconds))

    def set_running(self, is_running: bool, project_name: str = "") -> None:
        self._is_running = is_running
        if is_running:
            self._toggle_btn.configure(
                text="Stop", fg_color="#5305f0", hover_color="#1e0159"
            )
            if project_name:
                self._project_var.set(project_name)
        else:
            self._toggle_btn.configure(
                text="Start", fg_color="#2FA572", hover_color="#1A7A50"
            )
            self._time_label.configure(text="00:00:00")

    def update_projects(self, projects: list[Project]) -> None:
        self._projects = projects
        names = [p.name for p in projects] if projects else ["No projects"]
        self._project_menu.configure(values=names)

    def _toggle_timer(self) -> None:
        if self._is_running:
            self._on_stop()
        else:
            if self._selected_project_id is not None:
                self._on_start(self._selected_project_id)

    def _on_project_selected(self, name: str) -> None:
        for p in self._projects:
            if p.name == name:
                self._selected_project_id = p.id
                if self._is_running:
                    self._on_switch(p.id)
                break

    def _start_drag(self, event) -> None:
        self._offset_x = event.x
        self._offset_y = event.y

    def _on_drag(self, event) -> None:
        x = event.x_root - self._offset_x
        y = event.y_root - self._offset_y
        self.geometry(f"+{x}+{y}")
