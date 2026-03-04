from .connection import DatabaseConnection

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    color TEXT NOT NULL DEFAULT '#3B8ED0',
    is_archived INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS time_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    start_time TEXT NOT NULL,
    end_time TEXT,
    duration_seconds REAL,
    note TEXT DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_time_entries_project ON time_entries(project_id);
CREATE INDEX IF NOT EXISTS idx_time_entries_start ON time_entries(start_time);

CREATE TABLE IF NOT EXISTS window_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    window_title TEXT NOT NULL,
    app_name TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    project_id INTEGER REFERENCES projects(id)
);
CREATE INDEX IF NOT EXISTS idx_window_events_start ON window_events(start_time);
CREATE INDEX IF NOT EXISTS idx_window_events_app ON window_events(app_name);

CREATE TABLE IF NOT EXISTS idle_periods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    duration_seconds REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_idle_periods_start ON idle_periods(start_time);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def initialize_database(db: DatabaseConnection) -> None:
    """Create tables if they don't exist."""
    conn = db.get_connection()
    conn.executescript(SCHEMA_SQL)
    conn.commit()
