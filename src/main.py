import ctypes

from .config import AppConfig
from .gui.app import App


def main():
    # Set AppUserModelID so Windows uses our icon in the taskbar instead of Python's
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("timetracker.app")

    config = AppConfig()
    app = App(config)
    app.mainloop()


if __name__ == "__main__":
    main()
