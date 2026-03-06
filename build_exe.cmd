@echo off
echo Building TimeTracker.exe ...

cd /d "%~dp0"

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist TimeTracker.spec del TimeTracker.spec

venv\Scripts\python.exe -m PyInstaller ^
  --onefile ^
  --windowed ^
  --name "TimeTracker" ^
  --icon "assets\stopwatch.ico" ^
  --add-data "assets;assets" ^
  --add-data "venv\Lib\site-packages\customtkinter;customtkinter" ^
  --add-data "venv\Lib\site-packages\tkcalendar;tkcalendar" ^
  --hidden-import "babel.numbers" ^
  --hidden-import "pywintypes" ^
  --hidden-import "win32api" ^
  --hidden-import "win32gui" ^
  --hidden-import "win32process" ^
  --hidden-import "psutil" ^
  --hidden-import "src" ^
  --hidden-import "src.config" ^
  --hidden-import "src.main" ^
  --hidden-import "src.core" ^
  --hidden-import "src.core.models" ^
  --hidden-import "src.core.event_bus" ^
  --hidden-import "src.core.timer_engine" ^
  --hidden-import "src.core.window_tracker" ^
  --hidden-import "src.core.idle_detector" ^
  --hidden-import "src.database" ^
  --hidden-import "src.database.connection" ^
  --hidden-import "src.database.schema" ^
  --hidden-import "src.database.repositories" ^
  --hidden-import "src.gui" ^
  --hidden-import "src.gui.app" ^
  --hidden-import "src.gui.floating_timer" ^
  --hidden-import "src.gui.frames" ^
  --hidden-import "src.gui.frames.dashboard_frame" ^
  --hidden-import "src.gui.frames.projects_frame" ^
  --hidden-import "src.gui.frames.reports_frame" ^
  --hidden-import "src.gui.frames.settings_frame" ^
  --hidden-import "src.gui.components" ^
  --hidden-import "src.gui.components.time_display" ^
  run.py

if exist dist\TimeTracker.exe (
  echo.
  echo Build successful: dist\TimeTracker.exe
) else (
  echo.
  echo Build FAILED.
)
pause
