# Time Tracker

A Windows desktop time-tracking application with an always-on-top floating timer, background window focus tracking, and a full management GUI.

## Features

- **Floating Timer** — always-on-top draggable overlay showing elapsed time
- **Automatic Window Tracking** — logs which applications and windows you use in the background
- **Idle Detection** — pauses tracking when you step away, subtracts idle time automatically
- **Project Management** — create projects with custom colors, archive old ones
- **Reports** — daily timeline view, per-project totals, and window activity breakdown
- **Crash Recovery** — resumes your timer if the app closes unexpectedly
- **Dark / Light Mode** — follows system appearance or manual override

## Requirements

- Windows 10/11
- Python 3.12+

## Installation

```bash
git clone <repo-url>
cd time_tracker
python -m venv venv
venv\Scripts\activate
pip install -e .
```

For development (includes pytest):

```bash
pip install -e ".[dev]"
```

## Usage

```bash
python -m src.main
```

Or after installing:

```bash
time-tracker
```

## Running Tests

```bash
pytest tests/ -v
```

Tests use in-memory SQLite and mock OS APIs — no GUI is instantiated and no Windows APIs are called.

## Project Structure

```
src/
  main.py                  Entry point
  config.py                AppConfig defaults
  core/
    models.py              Project, TimeEntry, WindowEvent, IdlePeriod
    event_bus.py           Thread-safe pub/sub
    timer_engine.py        Start/stop/switch timer, idle subtraction
    window_tracker.py      Background window focus polling
    idle_detector.py       Idle detection via GetLastInputInfo
  database/
    connection.py          Thread-local SQLite (WAL mode)
    schema.py              DDL and initialization
    repositories.py        CRUD and query layer
  gui/
    app.py                 Main window orchestrator
    floating_timer.py      Always-on-top overlay
    frames/                Dashboard, Projects, Reports, Settings
    components/            Shared UI helpers
tests/                     76 tests covering core, database, and display logic
```

## Tech Stack

- **GUI**: CustomTkinter + tkcalendar
- **Storage**: SQLite (WAL mode, thread-local connections)
- **Window Tracking**: pywin32 (`win32gui`, `win32process`) + psutil
- **Idle Detection**: `ctypes.windll.user32.GetLastInputInfo`
- **Testing**: pytest + pytest-mock
