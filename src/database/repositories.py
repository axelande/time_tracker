from datetime import datetime
from typing import Optional

from .connection import DatabaseConnection
from ..core.models import Project, TimeEntry, WindowEvent, IdlePeriod


class ProjectRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def create(self, project: Project) -> Project:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "INSERT INTO projects (name, color) VALUES (?, ?)",
            (project.name, project.color),
        )
        conn.commit()
        project.id = cursor.lastrowid
        return project

    def get_by_id(self, project_id: int) -> Optional[Project]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_by_name(self, name: str) -> Optional[Project]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM projects WHERE name = ?", (name,)
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_all(self, include_archived: bool = False) -> list[Project]:
        conn = self._db.get_connection()
        if include_archived:
            rows = conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM projects WHERE is_archived = 0 ORDER BY name"
            ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def update(self, project: Project) -> None:
        conn = self._db.get_connection()
        conn.execute(
            "UPDATE projects SET name = ?, color = ?, updated_at = datetime('now') WHERE id = ?",
            (project.name, project.color, project.id),
        )
        conn.commit()

    def archive(self, project_id: int) -> None:
        conn = self._db.get_connection()
        conn.execute(
            "UPDATE projects SET is_archived = 1, updated_at = datetime('now') WHERE id = ?",
            (project_id,),
        )
        conn.commit()

    @staticmethod
    def _row_to_model(row) -> Project:
        return Project(
            id=row["id"],
            name=row["name"],
            color=row["color"],
            is_archived=bool(row["is_archived"]),
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            updated_at=datetime.fromisoformat(row["updated_at"]) if row["updated_at"] else None,
        )


class TimeEntryRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def create(self, entry: TimeEntry) -> TimeEntry:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "INSERT INTO time_entries (project_id, start_time, end_time, duration_seconds, note) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                entry.project_id,
                entry.start_time.isoformat() if entry.start_time else None,
                entry.end_time.isoformat() if entry.end_time else None,
                entry.duration_seconds,
                entry.note,
            ),
        )
        conn.commit()
        entry.id = cursor.lastrowid
        return entry

    def finish(
        self,
        entry_id: int,
        end_time: datetime,
        duration_seconds: Optional[float] = None,
    ) -> TimeEntry:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM time_entries WHERE id = ?", (entry_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"TimeEntry {entry_id} not found")

        start = datetime.fromisoformat(row["start_time"])
        duration = duration_seconds
        if duration is None:
            duration = (end_time - start).total_seconds()

        conn.execute(
            "UPDATE time_entries SET end_time = ?, duration_seconds = ? WHERE id = ?",
            (end_time.isoformat(), duration, entry_id),
        )
        conn.commit()

        return self._row_to_model(
            conn.execute("SELECT * FROM time_entries WHERE id = ?", (entry_id,)).fetchone()
        )

    def get_running(self) -> Optional[TimeEntry]:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT * FROM time_entries WHERE end_time IS NULL LIMIT 1"
        ).fetchone()
        return self._row_to_model(row) if row else None

    def get_by_date_range(self, start: datetime, end: datetime) -> list[TimeEntry]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE start_time >= ? AND start_time < ? ORDER BY start_time",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_by_project(
        self, project_id: int, start: datetime, end: datetime
    ) -> list[TimeEntry]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT * FROM time_entries WHERE project_id = ? AND start_time >= ? AND start_time < ? "
            "ORDER BY start_time",
            (project_id, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_total_by_project(
        self, start: datetime, end: datetime
    ) -> list[tuple[int, float]]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT project_id, SUM(duration_seconds) as total "
            "FROM time_entries "
            "WHERE start_time >= ? AND start_time < ? AND duration_seconds IS NOT NULL "
            "GROUP BY project_id ORDER BY total DESC",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [(row["project_id"], row["total"]) for row in rows]

    def delete(self, entry_id: int) -> None:
        conn = self._db.get_connection()
        conn.execute("DELETE FROM time_entries WHERE id = ?", (entry_id,))
        conn.commit()

    def purge_before(self, cutoff: datetime) -> int:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM time_entries WHERE start_time < ? AND end_time IS NOT NULL",
            (cutoff.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_model(row) -> TimeEntry:
        return TimeEntry(
            id=row["id"],
            project_id=row["project_id"],
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_seconds=row["duration_seconds"],
            note=row["note"] or "",
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
        )


class WindowEventRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def create(self, event: WindowEvent) -> WindowEvent:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "INSERT INTO window_events (window_title, app_name, start_time, end_time, duration_seconds, project_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.window_title,
                event.app_name,
                event.start_time.isoformat() if event.start_time else "",
                event.end_time.isoformat() if event.end_time else "",
                event.duration_seconds,
                event.project_id,
            ),
        )
        conn.commit()
        event.id = cursor.lastrowid
        return event

    def get_by_date_range(self, start: datetime, end: datetime) -> list[WindowEvent]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT * FROM window_events WHERE start_time >= ? AND start_time < ? ORDER BY start_time",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_app_summary(
        self, start: datetime, end: datetime
    ) -> list[tuple[str, float]]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT app_name, SUM(duration_seconds) as total "
            "FROM window_events "
            "WHERE start_time >= ? AND start_time < ? "
            "GROUP BY app_name ORDER BY total DESC",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [(row["app_name"], row["total"]) for row in rows]

    def get_title_summary(
        self, app_name: str, start: datetime, end: datetime
    ) -> list[tuple[str, float]]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT window_title, SUM(duration_seconds) as total "
            "FROM window_events "
            "WHERE app_name = ? AND start_time >= ? AND start_time < ? "
            "GROUP BY window_title ORDER BY total DESC",
            (app_name, start.isoformat(), end.isoformat()),
        ).fetchall()
        return [(row["window_title"], row["total"]) for row in rows]

    def purge_before(self, cutoff: datetime) -> int:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM window_events WHERE start_time < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_model(row) -> WindowEvent:
        return WindowEvent(
            id=row["id"],
            window_title=row["window_title"],
            app_name=row["app_name"],
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_seconds=row["duration_seconds"],
            project_id=row["project_id"],
        )


class IdlePeriodRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def create(self, period: IdlePeriod) -> IdlePeriod:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "INSERT INTO idle_periods (start_time, end_time, duration_seconds) VALUES (?, ?, ?)",
            (
                period.start_time.isoformat() if period.start_time else "",
                period.end_time.isoformat() if period.end_time else "",
                period.duration_seconds,
            ),
        )
        conn.commit()
        period.id = cursor.lastrowid
        return period

    def get_by_date_range(self, start: datetime, end: datetime) -> list[IdlePeriod]:
        conn = self._db.get_connection()
        rows = conn.execute(
            "SELECT * FROM idle_periods WHERE start_time >= ? AND start_time < ? ORDER BY start_time",
            (start.isoformat(), end.isoformat()),
        ).fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_total_idle(self, start: datetime, end: datetime) -> float:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT COALESCE(SUM(duration_seconds), 0.0) as total "
            "FROM idle_periods "
            "WHERE start_time >= ? AND start_time < ?",
            (start.isoformat(), end.isoformat()),
        ).fetchone()
        return row["total"]

    def purge_before(self, cutoff: datetime) -> int:
        conn = self._db.get_connection()
        cursor = conn.execute(
            "DELETE FROM idle_periods WHERE start_time < ?",
            (cutoff.isoformat(),),
        )
        conn.commit()
        return cursor.rowcount

    @staticmethod
    def _row_to_model(row) -> IdlePeriod:
        return IdlePeriod(
            id=row["id"],
            start_time=datetime.fromisoformat(row["start_time"]) if row["start_time"] else None,
            end_time=datetime.fromisoformat(row["end_time"]) if row["end_time"] else None,
            duration_seconds=row["duration_seconds"],
        )


class SettingsRepository:
    def __init__(self, db: DatabaseConnection) -> None:
        self._db = db

    def get(self, key: str, default: str = "") -> str:
        conn = self._db.get_connection()
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        conn = self._db.get_connection()
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()

    def get_all(self) -> dict[str, str]:
        conn = self._db.get_connection()
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {row["key"]: row["value"] for row in rows}
