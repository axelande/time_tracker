import customtkinter

from ...config import AppConfig
from ...core.idle_detector import IdleDetector
from ...database.repositories import SettingsRepository


class SettingsFrame(customtkinter.CTkFrame):
    def __init__(
        self,
        master,
        settings_repo: SettingsRepository,
        idle_detector: IdleDetector,
        config: AppConfig,
    ) -> None:
        super().__init__(master, fg_color="transparent")
        self._settings_repo = settings_repo
        self._idle_detector = idle_detector
        self._config = config

        self.grid_columnconfigure(0, weight=1)

        customtkinter.CTkLabel(
            self, text="Settings",
            font=customtkinter.CTkFont(size=24, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 20), sticky="w")

        settings_card = customtkinter.CTkFrame(self)
        settings_card.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        settings_card.grid_columnconfigure(1, weight=1)

        # Idle threshold
        customtkinter.CTkLabel(
            settings_card, text="Idle threshold (minutes):",
        ).grid(row=0, column=0, padx=15, pady=10, sticky="w")

        self._idle_var = customtkinter.IntVar(
            value=int(self._idle_detector.threshold_seconds / 60)
        )
        self._idle_slider = customtkinter.CTkSlider(
            settings_card, from_=1, to=60,
            variable=self._idle_var,
            number_of_steps=59,
            command=self._on_idle_changed,
        )
        self._idle_slider.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        self._idle_label = customtkinter.CTkLabel(
            settings_card, text=f"{self._idle_var.get()} min", width=60,
        )
        self._idle_label.grid(row=0, column=2, padx=(0, 15), pady=10)

        # Appearance mode
        customtkinter.CTkLabel(
            settings_card, text="Appearance:",
        ).grid(row=1, column=0, padx=15, pady=10, sticky="w")

        current_mode = self._settings_repo.get("appearance_mode", config.appearance_mode)
        self._appearance_var = customtkinter.StringVar(value=current_mode)
        appearance_menu = customtkinter.CTkOptionMenu(
            settings_card,
            variable=self._appearance_var,
            values=["dark", "light", "system"],
            command=self._on_appearance_changed,
        )
        appearance_menu.grid(row=1, column=1, padx=10, pady=10, sticky="w")

        # Floating timer opacity
        customtkinter.CTkLabel(
            settings_card, text="Floating timer opacity:",
        ).grid(row=2, column=0, padx=15, pady=10, sticky="w")

        saved_opacity = self._settings_repo.get("opacity", str(config.floating_timer_opacity))
        self._opacity_var = customtkinter.DoubleVar(value=float(saved_opacity))
        self._opacity_slider = customtkinter.CTkSlider(
            settings_card, from_=0.3, to=1.0,
            variable=self._opacity_var,
            command=self._on_opacity_changed,
        )
        self._opacity_slider.grid(row=2, column=1, padx=10, pady=10, sticky="ew")

        self._opacity_label = customtkinter.CTkLabel(
            settings_card, text=f"{self._opacity_var.get():.0%}", width=60,
        )
        self._opacity_label.grid(row=2, column=2, padx=(0, 15), pady=10)

        # Data retention
        customtkinter.CTkLabel(
            settings_card, text="Data retention (months):",
        ).grid(row=3, column=0, padx=15, pady=10, sticky="w")

        saved_retention = self._settings_repo.get(
            "data_retention_months", str(config.data_retention_months)
        )
        self._retention_var = customtkinter.IntVar(value=int(saved_retention))
        self._retention_slider = customtkinter.CTkSlider(
            settings_card, from_=1, to=12,
            variable=self._retention_var,
            number_of_steps=11,
            command=self._on_retention_changed,
        )
        self._retention_slider.grid(row=3, column=1, padx=10, pady=10, sticky="ew")

        self._retention_label = customtkinter.CTkLabel(
            settings_card, text=f"{self._retention_var.get()} months", width=80,
        )
        self._retention_label.grid(row=3, column=2, padx=(0, 15), pady=10)

    def _on_idle_changed(self, value) -> None:
        minutes = int(value)
        self._idle_label.configure(text=f"{minutes} min")
        self._idle_detector.threshold_seconds = minutes * 60
        self._settings_repo.set("idle_threshold_minutes", str(minutes))

    def _on_appearance_changed(self, mode: str) -> None:
        customtkinter.set_appearance_mode(mode)
        self._settings_repo.set("appearance_mode", mode)

    def _on_opacity_changed(self, value) -> None:
        self._opacity_label.configure(text=f"{value:.0%}")
        self._settings_repo.set("opacity", str(value))
        # Update floating timer opacity if accessible
        top = self.winfo_toplevel()
        for child in top.winfo_children():
            if hasattr(child, "attributes") and child.winfo_class() == "Toplevel":
                try:
                    child.attributes("-alpha", value)
                except Exception:
                    pass

    def _on_retention_changed(self, value) -> None:
        months = int(value)
        self._retention_label.configure(text=f"{months} months")
        self._settings_repo.set("data_retention_months", str(months))
