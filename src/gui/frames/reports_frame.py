import tkinter
import customtkinter
from datetime import datetime, timedelta, timezone
from tkcalendar import Calendar

from ...core.timer_engine import TimerEngine
from ...database.repositories import (
    TimeEntryRepository,
    WindowEventRepository,
    ProjectRepository,
    IdlePeriodRepository,
)
from ..components.time_display import format_hours_minutes


class ReportsFrame(customtkinter.CTkFrame):
    def __init__(
        self,
        master,
        entry_repo: TimeEntryRepository,
        window_repo: WindowEventRepository,
        project_repo: ProjectRepository,
        idle_repo: IdlePeriodRepository,
        timer_engine: TimerEngine,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._entry_repo = entry_repo
        self._window_repo = window_repo
        self._project_repo = project_repo
        self._idle_repo = idle_repo
        self._timer_engine = timer_engine

        self.grid_columnconfigure(0, weight=1)
        self._expanded_apps: set[str] = set()
        self._child_widgets: dict[str, list] = {}
        self._app_labels: dict[str, customtkinter.CTkLabel] = {}

        # Title
        customtkinter.CTkLabel(
            self, text="Reports",
            font=customtkinter.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 10), sticky="w")

        # Date calendar picker
        cal_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        cal_frame.grid(row=1, column=0, padx=20, pady=5, sticky="w")

        self._calendar = Calendar(
            cal_frame,
            selectmode="day",
            date_pattern="yyyy-mm-dd",
            showothermonthdays=False,
        )
        self._calendar.pack()
        self._calendar.bind("<<CalendarSelected>>", lambda _: self.refresh())

        # Tabview (only By Project and Window Activity)
        self._tabview = customtkinter.CTkTabview(self)
        self._tabview.grid(row=2, column=0, padx=20, pady=10, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)

        self._tabview.add("By Project")
        self._tabview.add("Window Activity")

        project_container = self._tabview.tab("By Project")

        self._timeline_canvas = tkinter.Canvas(
            project_container, height=85, highlightthickness=0,
        )
        self._timeline_canvas.pack(fill="x", padx=5, pady=(5, 0))
        self._timeline_canvas.bind("<Configure>", lambda e: self._draw_timeline())
        self._timeline_blocks: list[tuple[datetime, datetime, int]] = []
        self._timeline_colors: dict[int, str] = {}
        self._timeline_projects: dict = {}

        self._project_tab = customtkinter.CTkScrollableFrame(project_container)
        self._project_tab.pack(fill="both", expand=True)
        self._project_tab.grid_columnconfigure(1, weight=1)

        self._window_tab = customtkinter.CTkScrollableFrame(
            self._tabview.tab("Window Activity")
        )
        self._window_tab.pack(fill="both", expand=True)
        self._window_tab.grid_columnconfigure(0, weight=0, minsize=200)
        self._window_tab.grid_columnconfigure(1, weight=1)
        self._window_tab.grid_columnconfigure(2, weight=0, minsize=80)

        self.refresh()

    def refresh(self) -> None:
        start, end = self._get_date_range()
        self._build_timeline(start, end)
        self._build_project_report(start, end)
        self._build_window_report(start, end)

    def _get_date_range(self) -> tuple[datetime, datetime]:
        selected = self._calendar.get_date()
        day = datetime.strptime(selected, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        end = day.replace(hour=23, minute=59, second=59, microsecond=0)
        return start, end

    def _build_timeline(self, start: datetime, end: datetime) -> None:
        entries = self._entry_repo.get_by_date_range(start, end)
        projects = {p.id: p for p in self._project_repo.get_all(include_archived=True)}
        idle_periods = self._idle_repo.get_by_date_range(start, end)

        # Include currently running timer
        if self._timer_engine.is_running:
            active_id = self._timer_engine.active_project_id
            active_entry = self._timer_engine._active_entry
            running_start = active_entry.start_time if active_entry else None
            if active_id is not None and running_start is not None:
                running_ids = {e.id for e in entries if e.is_running}
                if not running_ids:
                    from ...core.models import TimeEntry as _TE
                    entries.append(_TE(
                        project_id=active_id,
                        start_time=running_start,
                        end_time=None,
                    ))

        # Build visible blocks by subtracting idle periods from entries
        now = datetime.now(timezone.utc)
        # Clamp block ends to the selected day boundary
        day_end = min(end, now)
        blocks: list[tuple[datetime, datetime, int]] = []  # (start, end, project_id)

        for entry in entries:
            if not entry.start_time:
                continue
            entry_end = min(entry.end_time or now, day_end)
            # Find idle periods that overlap this entry
            overlapping = [
                ip for ip in idle_periods
                if ip.start_time and ip.end_time
                and ip.start_time < entry_end and ip.end_time > entry.start_time
            ]
            if not overlapping:
                blocks.append((entry.start_time, entry_end, entry.project_id))
            else:
                # Split entry around idle gaps
                overlapping.sort(key=lambda ip: ip.start_time)
                cursor = entry.start_time
                for ip in overlapping:
                    idle_start = max(ip.start_time, entry.start_time)
                    idle_end = min(ip.end_time, entry_end)
                    if cursor < idle_start:
                        blocks.append((cursor, idle_start, entry.project_id))
                    cursor = max(cursor, idle_end)
                if cursor < entry_end:
                    blocks.append((cursor, entry_end, entry.project_id))

        # Assign distinct colors per project for the timeline
        palette = [
            "#3B8ED0", "#E85D75", "#2ECC71", "#F39C12",
            "#9B59B6", "#1ABC9C", "#E67E22", "#3498DB",
        ]
        project_ids = sorted({b[2] for b in blocks})
        # Use project color only if it's unique across projects; otherwise use palette
        raw_colors = {pid: (projects[pid].color if pid in projects else None) for pid in project_ids}
        color_counts: dict[str, int] = {}
        for c in raw_colors.values():
            if c:
                color_counts[c] = color_counts.get(c, 0) + 1
        timeline_colors: dict[int, str] = {}
        palette_idx = 0
        for pid in project_ids:
            c = raw_colors.get(pid)
            if c and color_counts.get(c, 0) <= 1:
                timeline_colors[pid] = c
            else:
                timeline_colors[pid] = palette[palette_idx % len(palette)]
                palette_idx += 1

        self._timeline_blocks = blocks
        self._timeline_colors = timeline_colors
        self._timeline_projects = projects
        self._draw_timeline()

    def _draw_timeline(self) -> None:
        canvas = self._timeline_canvas
        canvas.delete("all")

        blocks = self._timeline_blocks
        projects = self._timeline_projects

        if not blocks:
            canvas.configure(height=0)
            return

        canvas.configure(height=85)
        w = canvas.winfo_width()
        if w <= 1:
            return

        # Theme colors
        mode = customtkinter.get_appearance_mode()
        if mode == "Dark":
            canvas_bg = "#2b2b2b"
            text_color = "#999999"
            grid_color = "#555555"
            track_bg = "#1e1e1e"
        else:
            canvas_bg = "#ebebeb"
            text_color = "#666666"
            grid_color = "#cccccc"
            track_bg = "#d5d5d5"
        canvas.configure(bg=canvas_bg)

        left_pad = 30
        right_pad = 15
        draw_width = w - left_pad - right_pad
        track_top = 8
        track_bottom = 42
        label_y = 57

        if draw_width <= 0:
            return

        # Calculate time range from blocks
        min_time = min(b[0] for b in blocks)
        max_time = max(b[1] for b in blocks)

        # Round to hours
        min_hour = min_time.replace(minute=0, second=0, microsecond=0)
        max_hour = max_time.replace(minute=0, second=0, microsecond=0)
        if max_hour < max_time:
            max_hour += timedelta(hours=1)
        if min_hour == max_hour:
            max_hour += timedelta(hours=1)

        total_secs = (max_hour - min_hour).total_seconds()

        # Track background
        canvas.create_rectangle(
            left_pad, track_top, left_pad + draw_width, track_bottom,
            fill=track_bg, outline="",
        )

        # Hour grid lines and labels
        num_hours = int(total_secs / 3600)
        for h in range(num_hours + 1):
            x = left_pad + (h * 3600 / total_secs) * draw_width
            canvas.create_line(x, track_top, x, track_bottom, fill=grid_color)
            display_hour = (min_hour.hour + h) % 24
            canvas.create_text(
                x, label_y, text=f"{display_hour:02d}:00",
                fill=text_color, font=("", 8),
            )

        # Draw blocks with distinct project colors
        colors = self._timeline_colors
        for block_start, block_end, project_id in blocks:
            x1 = left_pad + (
                (block_start - min_hour).total_seconds() / total_secs
            ) * draw_width
            x2 = left_pad + (
                (block_end - min_hour).total_seconds() / total_secs
            ) * draw_width

            if x2 - x1 < 2:
                x2 = x1 + 2

            color = colors.get(project_id, "#888888")

            canvas.create_rectangle(
                x1, track_top + 1, x2, track_bottom - 1,
                fill=color, outline="",
            )

        # Legend
        legend_x = left_pad
        legend_y = track_bottom + 25
        for pid in sorted(colors.keys()):
            project = projects.get(pid)
            name = project.name if project else f"#{pid}"
            c = colors[pid]
            canvas.create_rectangle(
                legend_x, legend_y - 5, legend_x + 10, legend_y + 5,
                fill=c, outline="",
            )
            legend_x += 14
            tid = canvas.create_text(
                legend_x, legend_y, text=name, anchor="w",
                fill=text_color, font=("", 8),
            )
            bbox = canvas.bbox(tid)
            legend_x = bbox[2] + 12 if bbox else legend_x + 50

    def _build_project_report(self, start: datetime, end: datetime) -> None:
        for widget in self._project_tab.winfo_children():
            widget.destroy()

        totals = self._entry_repo.get_total_by_project(start, end)

        # Include elapsed time from the currently running timer
        if self._timer_engine.is_running:
            active_id = self._timer_engine.active_project_id
            active_entry = self._timer_engine._active_entry
            if active_id is not None and active_entry and active_entry.start_time:
                # Only add running time if the entry falls within the selected date range
                if start <= active_entry.start_time <= end:
                    running_secs = self._timer_engine.elapsed_seconds
                    if running_secs > 0:
                        totals_dict = dict(totals)
                        # Replace (not add): elapsed_seconds already includes
                        # prior completed entries via _today_prior_seconds
                        totals_dict[active_id] = running_secs
                        totals = sorted(totals_dict.items(), key=lambda x: x[1], reverse=True)

        projects = {p.id: p for p in self._project_repo.get_all(include_archived=True)}

        if not totals:
            customtkinter.CTkLabel(
                self._project_tab, text="No time entries for this period.",
                text_color="gray",
            ).grid(row=0, column=0, columnspan=3, padx=10, pady=20)
            return

        total_all = sum(t for _, t in totals)

        # Total row
        customtkinter.CTkLabel(
            self._project_tab,
            text=f"Total: {format_hours_minutes(total_all)}",
            font=customtkinter.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, columnspan=3, padx=10, pady=(10, 15), sticky="w")

        for i, (project_id, total_secs) in enumerate(totals, start=1):
            project = projects.get(project_id)
            name = project.name if project else f"Project #{project_id}"
            color = project.color if project else "#888888"
            fraction = total_secs / total_all if total_all > 0 else 0

            customtkinter.CTkLabel(
                self._project_tab, text=name, width=120, anchor="w",
                font=customtkinter.CTkFont(weight="bold"),
            ).grid(row=i, column=0, padx=(10, 5), pady=4, sticky="w")

            bar = customtkinter.CTkProgressBar(
                self._project_tab, progress_color=color
            )
            bar.set(fraction)
            bar.grid(row=i, column=1, padx=5, pady=4, sticky="ew")

            customtkinter.CTkLabel(
                self._project_tab, text=format_hours_minutes(total_secs), width=80,
            ).grid(row=i, column=2, padx=(5, 10), pady=4)

    def _build_window_report(self, start: datetime, end: datetime) -> None:
        for widget in self._window_tab.winfo_children():
            widget.destroy()
        self._child_widgets.clear()
        self._app_labels.clear()

        summary = self._window_repo.get_app_summary(start, end)

        if not summary:
            customtkinter.CTkLabel(
                self._window_tab, text="No window activity for this period.",
                text_color="gray",
            ).grid(row=0, column=0, columnspan=3, padx=10, pady=20)
            return

        total_all = sum(t for _, t in summary)
        row = 0

        for app_name, app_secs in summary:
            fraction = app_secs / total_all if total_all > 0 else 0
            expanded = app_name in self._expanded_apps
            indicator = "\u25bc" if expanded else "\u25b6"

            # Parent row: clickable app name
            label = customtkinter.CTkLabel(
                self._window_tab, text=f"{indicator}  {app_name}", width=150,
                anchor="w", font=customtkinter.CTkFont(weight="bold"),
                cursor="hand2",
            )
            label.grid(row=row, column=0, padx=(10, 5), pady=4, sticky="w")
            label.bind("<Button-1>", lambda e, name=app_name: self._toggle_app(name))
            self._app_labels[app_name] = label

            bar = customtkinter.CTkProgressBar(self._window_tab)
            bar.set(fraction)
            bar.grid(row=row, column=1, padx=5, pady=4, sticky="ew")

            customtkinter.CTkLabel(
                self._window_tab, text=format_hours_minutes(app_secs), width=80,
            ).grid(row=row, column=2, padx=(5, 10), pady=4)
            row += 1

            # Child rows: window titles (>=60s only)
            child_widgets: list = []
            titles = self._window_repo.get_title_summary(app_name, start, end)
            for title, title_secs in titles:
                if title_secs < 60:
                    continue
                title_fraction = title_secs / app_secs if app_secs > 0 else 0

                display_title = title if len(title) <= 40 else title[:37] + "..."
                title_lbl = customtkinter.CTkLabel(
                    self._window_tab, text=display_title, width=150, anchor="w",
                    font=customtkinter.CTkFont(size=12),
                    text_color="gray",
                )
                title_lbl.grid(row=row, column=0, padx=(35, 5), pady=1, sticky="w")
                child_widgets.append(title_lbl)

                child_bar = customtkinter.CTkProgressBar(
                    self._window_tab, height=8,
                )
                child_bar.set(title_fraction)
                child_bar.grid(row=row, column=1, padx=(20, 5), pady=1, sticky="ew")
                child_widgets.append(child_bar)

                time_lbl = customtkinter.CTkLabel(
                    self._window_tab, text=format_hours_minutes(title_secs), width=80,
                    font=customtkinter.CTkFont(size=12),
                    text_color="gray",
                )
                time_lbl.grid(row=row, column=2, padx=(5, 10), pady=1)
                child_widgets.append(time_lbl)
                row += 1

            self._child_widgets[app_name] = child_widgets
            if not expanded:
                for w in child_widgets:
                    w.grid_remove()

    def _toggle_app(self, app_name: str) -> None:
        if app_name in self._expanded_apps:
            self._expanded_apps.discard(app_name)
            for w in self._child_widgets.get(app_name, []):
                w.grid_remove()
            indicator = "\u25b6"
        else:
            self._expanded_apps.add(app_name)
            for w in self._child_widgets.get(app_name, []):
                w.grid()
            indicator = "\u25bc"
        label = self._app_labels.get(app_name)
        if label:
            text = label.cget("text")
            label.configure(text=f"{indicator}  {text[2:].lstrip()}")
