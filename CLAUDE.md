# Time Tracker

A Windows desktop time-tracking application with an always-on-top floating timer, background window focus tracking, and a full management GUI.

## Quick Start

```bash
cd e:/dev_e/program/time_tracker
./venv/Scripts/python.exe -m src.main          # Launch the app
./venv/Scripts/python.exe -m pytest tests/ -v  # Run tests (75 tests)
```

## Tech Stack

- **Python 3.12**, **CustomTkinter** (GUI), **SQLite** (storage), **pywin32** + **psutil** (window tracking), **pytest** (testing)
- Windows-first: uses `win32gui`, `win32process`, `ctypes.GetLastInputInfo`

## Project Structure

```
src/
  main.py                          # Entry point: creates App, runs mainloop
  config.py                        # AppConfig dataclass (all defaults)
  core/
    models.py                      # Project, TimeEntry, WindowEvent, IdlePeriod, WindowInfo
    event_bus.py                   # Thread-safe pub/sub via queue.Queue (9 EventTypes)
    timer_engine.py                # Start/stop/switch timer, idle subtraction, crash recovery
    window_tracker.py              # Background thread: polls foreground window every 1s, merges events
    idle_detector.py               # Background thread: detects idle via GetLastInputInfo
  database/
    connection.py                  # Thread-local SQLite connections (WAL mode)
    schema.py                      # DDL for 5 tables + initialize_database()
    repositories.py                # ProjectRepo, TimeEntryRepo, WindowEventRepo, IdlePeriodRepo, SettingsRepo
  gui/
    app.py                         # Main window orchestrator - wires everything together
    floating_timer.py              # Always-on-top draggable CTkToplevel
    frames/
      dashboard_frame.py           # Today's summary, quick-start buttons per project
      projects_frame.py            # CRUD with color picker, archive
      reports_frame.py             # Date picker, "By Project" + "Window Activity" tabs
      settings_frame.py            # Idle threshold, appearance, opacity, data retention
    components/
      time_display.py              # format_seconds() and format_hours_minutes() helpers
tests/
  conftest.py                      # Shared fixtures: in_memory_db, event_bus, mock providers
  test_models.py                   # Dataclass defaults and properties
  test_core/
    test_event_bus.py              # Pub/sub, threading, queue drain
    test_timer_engine.py           # Start/stop/switch, crash recovery, idle subtraction
    test_window_tracker.py         # Event merging, pause/resume, sub-second filtering
    test_idle_detector.py          # Threshold transitions, period persistence
  test_database/
    test_schema.py                 # Table creation, idempotency
    test_repositories.py           # CRUD, queries, aggregations, purge
  test_gui/
    test_time_display.py           # Time formatting
```

## Architecture

### Threading Model

Three background daemon threads + the main GUI thread:
- **WindowTracker thread** - polls `win32gui.GetForegroundWindow()` every 1s
- **IdleDetector thread** - polls `GetLastInputInfo()` every 1s
- **TimerTick thread** - publishes elapsed time every 1s (only while timer is running)

### EventBus (the communication backbone)

Background threads call `publish()` (thread-safe `queue.Queue.put`). The main GUI thread drains via `process_pending()` in a Tkinter `after()` loop. All subscriber callbacks run on the main thread, so widgets can be safely updated.

### Key Design Patterns

- **Protocol-based OS abstraction**: `WindowInfoProvider` and `IdleTimeProvider` protocols allow injecting mocks. Production uses `Win32WindowInfoProvider` and `Win32IdleTimeProvider`.
- **Event merging**: WindowTracker holds current window state in memory. Only writes to DB when the window *changes*. 1 hour on VS Code = 1 DB row.
- **Idle subtraction**: When idle is detected, `TimerEngine.on_idle_started()` records the timestamp. On return, `on_idle_ended()` accumulates idle duration. The `elapsed_seconds` property and `stop()` both subtract accumulated idle time.
- **Crash recovery**: On startup, `TimerEngine.recover_from_crash()` detects `time_entries` with `end_time IS NULL` and resumes.
- **Thread-local DB**: Each thread gets its own SQLite connection via `threading.local()`. WAL mode allows concurrent reads.
- **Data retention**: On startup, entries older than the configured retention period (default 2 months) are purged. Running entries are protected.

### Database Schema (5 tables)

| Table | Purpose |
|-------|---------|
| `projects` | Name, color, archive flag |
| `time_entries` | Manual timer entries (NULL end_time = running) |
| `window_events` | Merged foreground window events |
| `idle_periods` | Detected idle periods |
| `settings` | Key-value user preferences |

All timestamps are ISO 8601 UTC strings. Indexes on `start_time` and `app_name` columns.

## Testing

Tests use **in-memory SQLite** and **mock providers** for OS APIs. No GUI is instantiated in tests.

```bash
./venv/Scripts/python.exe -m pytest tests/ -v        # All tests
./venv/Scripts/python.exe -m pytest tests/test_core/  # Core logic only
```

### Mocking Strategy

| Module | What's Mocked | How |
|--------|--------------|-----|
| WindowTracker | win32gui/psutil | `WindowInfoProvider` protocol + MagicMock returning `WindowInfo` |
| IdleDetector | ctypes | `IdleTimeProvider` protocol + MagicMock returning `float` |
| TimerEngine | Nothing | Real in-memory DB + real EventBus |
| Repositories | Nothing | Real in-memory DB |

### Adding New Tests

- Use the `in_memory_db` fixture from `conftest.py` for any database test
- Use `mock_window_provider` / `mock_idle_provider` fixtures for OS-level mocking
- Call `_poll()` / `_check()` directly on trackers instead of running threads
- Call `bus.process_pending()` to synchronously drain events

## Dependencies

```
customtkinter>=5.2.0    # Modern Tkinter with dark mode
pywin32>=306            # win32gui, win32process
psutil>=5.9.0           # Process name lookup
pytest>=8.0             # Testing (dev)
pytest-mock>=3.12       # Mock helpers (dev)
```

## Settings (persisted in `settings` table)

| Key | Default | Description |
|-----|---------|-------------|
| `idle_threshold_minutes` | 5 | Minutes before idle detection triggers |
| `appearance_mode` | dark | dark / light / system |
| `opacity` | 0.9 | Floating timer transparency |
| `data_retention_months` | 2 | Auto-purge data older than this |
