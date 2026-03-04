import customtkinter
from tkinter import colorchooser

from ...core.event_bus import EventBus, EventType
from ...core.models import Project
from ...database.repositories import ProjectRepository


class ProjectsFrame(customtkinter.CTkFrame):
    def __init__(
        self,
        master,
        project_repo: ProjectRepository,
        event_bus: EventBus,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._project_repo = project_repo
        self._event_bus = event_bus

        self.grid_columnconfigure(0, weight=1)

        # Header row
        header = customtkinter.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(
            header, text="Projects",
            font=customtkinter.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, sticky="w")

        customtkinter.CTkButton(
            header, text="+ Add Project", width=120,
            command=self._show_add_dialog,
        ).grid(row=0, column=1)

        # Show archived toggle
        self._show_archived = customtkinter.BooleanVar(value=False)
        customtkinter.CTkCheckBox(
            header, text="Show archived",
            variable=self._show_archived,
            command=self.refresh,
        ).grid(row=0, column=2, padx=(10, 0))

        # Projects list
        self._list_frame = customtkinter.CTkScrollableFrame(self)
        self._list_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self._list_frame.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.refresh()

    def refresh(self) -> None:
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        projects = self._project_repo.get_all(
            include_archived=self._show_archived.get()
        )

        if not projects:
            customtkinter.CTkLabel(
                self._list_frame,
                text="No projects yet. Click '+ Add Project' to create one.",
                text_color="gray",
            ).grid(row=0, column=0, columnspan=4, padx=10, pady=30)
            return

        for i, project in enumerate(projects):
            self._build_project_row(i, project)

    def _build_project_row(self, row: int, project: Project) -> None:
        # Color indicator
        color_btn = customtkinter.CTkButton(
            self._list_frame,
            text="",
            width=24,
            height=24,
            fg_color=project.color,
            hover_color=project.color,
            corner_radius=12,
            command=lambda p=project: self._pick_color(p),
        )
        color_btn.grid(row=row, column=0, padx=(10, 5), pady=6)

        # Name
        name_label = customtkinter.CTkLabel(
            self._list_frame,
            text=project.name + (" (archived)" if project.is_archived else ""),
            font=customtkinter.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        name_label.grid(row=row, column=1, padx=5, pady=6, sticky="w")

        # Edit button
        customtkinter.CTkButton(
            self._list_frame,
            text="Edit",
            width=60,
            height=26,
            command=lambda p=project: self._show_edit_dialog(p),
        ).grid(row=row, column=2, padx=5, pady=6)

        # Archive/unarchive button
        if not project.is_archived:
            customtkinter.CTkButton(
                self._list_frame,
                text="Archive",
                width=70,
                height=26,
                fg_color="#E04040",
                hover_color="#B03030",
                command=lambda p=project: self._archive_project(p),
            ).grid(row=row, column=3, padx=(5, 10), pady=6)

    def _show_add_dialog(self) -> None:
        dialog = customtkinter.CTkInputDialog(
            text="Enter project name:", title="Add Project"
        )
        name = dialog.get_input()
        if name and name.strip():
            project = self._project_repo.create(
                Project(name=name.strip())
            )
            self._event_bus.publish(EventType.PROJECT_CREATED, project)
            self.refresh()

    def _show_edit_dialog(self, project: Project) -> None:
        dialog = customtkinter.CTkInputDialog(
            text=f"Rename '{project.name}' to:", title="Edit Project"
        )
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            project.name = new_name.strip()
            self._project_repo.update(project)
            self._event_bus.publish(EventType.PROJECT_UPDATED, project)
            self.refresh()

    def _pick_color(self, project: Project) -> None:
        color = colorchooser.askcolor(
            initialcolor=project.color, title="Pick project color"
        )
        if color[1]:
            project.color = color[1]
            self._project_repo.update(project)
            self._event_bus.publish(EventType.PROJECT_UPDATED, project)
            self.refresh()

    def _archive_project(self, project: Project) -> None:
        self._project_repo.archive(project.id)
        self._event_bus.publish(EventType.PROJECT_ARCHIVED, project)
        self.refresh()
