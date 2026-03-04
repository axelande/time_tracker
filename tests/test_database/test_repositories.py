import sqlite3
from datetime import datetime, timezone, timedelta

import pytest

from src.core.models import Project, TimeEntry, WindowEvent, IdlePeriod
from src.database.repositories import (
    ProjectRepository,
    TimeEntryRepository,
    WindowEventRepository,
    IdlePeriodRepository,
    SettingsRepository,
)


class TestProjectRepository:
    @pytest.fixture
    def repo(self, in_memory_db):
        return ProjectRepository(in_memory_db)

    def test_create_and_get_by_id(self, repo):
        project = repo.create(Project(name="My Project", color="#FF0000"))
        assert project.id is not None

        fetched = repo.get_by_id(project.id)
        assert fetched is not None
        assert fetched.name == "My Project"
        assert fetched.color == "#FF0000"

    def test_create_duplicate_name_raises(self, repo):
        repo.create(Project(name="Unique"))
        with pytest.raises(sqlite3.IntegrityError):
            repo.create(Project(name="Unique"))

    def test_get_all_excludes_archived(self, repo):
        repo.create(Project(name="Active"))
        p2 = repo.create(Project(name="Archived"))
        repo.archive(p2.id)

        projects = repo.get_all()
        assert len(projects) == 1
        assert projects[0].name == "Active"

    def test_get_all_includes_archived_when_flag_set(self, repo):
        repo.create(Project(name="Active"))
        p2 = repo.create(Project(name="Archived"))
        repo.archive(p2.id)

        projects = repo.get_all(include_archived=True)
        assert len(projects) == 2

    def test_update_name_and_color(self, repo):
        project = repo.create(Project(name="Old Name", color="#000000"))
        project.name = "New Name"
        project.color = "#FFFFFF"
        repo.update(project)

        fetched = repo.get_by_id(project.id)
        assert fetched.name == "New Name"
        assert fetched.color == "#FFFFFF"

    def test_archive(self, repo):
        project = repo.create(Project(name="ToArchive"))
        repo.archive(project.id)

        fetched = repo.get_by_id(project.id)
        assert fetched.is_archived is True

    def test_get_by_name(self, repo):
        repo.create(Project(name="FindMe"))
        found = repo.get_by_name("FindMe")
        assert found is not None
        assert found.name == "FindMe"

        not_found = repo.get_by_name("Missing")
        assert not_found is None


class TestTimeEntryRepository:
    @pytest.fixture
    def repo(self, in_memory_db):
        # Create a project first for FK
        ProjectRepository(in_memory_db).create(Project(name="Test Project"))
        return TimeEntryRepository(in_memory_db)

    def test_create_with_null_end_time(self, repo):
        now = datetime.now(timezone.utc)
        entry = repo.create(TimeEntry(project_id=1, start_time=now))
        assert entry.id is not None
        assert entry.end_time is None

    def test_finish_sets_end_time_and_duration(self, repo):
        start = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, 11, 30, 0, tzinfo=timezone.utc)
        entry = repo.create(TimeEntry(project_id=1, start_time=start))

        finished = repo.finish(entry.id, end)
        assert finished.end_time == end
        assert finished.duration_seconds == 5400.0  # 1.5 hours

    def test_get_running_returns_active_entry(self, repo):
        now = datetime.now(timezone.utc)
        repo.create(TimeEntry(project_id=1, start_time=now))

        running = repo.get_running()
        assert running is not None
        assert running.is_running is True

    def test_get_running_returns_none_when_none_active(self, repo):
        start = datetime.now(timezone.utc)
        entry = repo.create(TimeEntry(project_id=1, start_time=start))
        repo.finish(entry.id, start + timedelta(hours=1))

        running = repo.get_running()
        assert running is None

    def test_get_by_date_range(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(TimeEntry(project_id=1, start_time=base, end_time=base + timedelta(hours=1), duration_seconds=3600))
        repo.create(TimeEntry(project_id=1, start_time=base + timedelta(days=1), end_time=base + timedelta(days=1, hours=2), duration_seconds=7200))

        results = repo.get_by_date_range(base, base + timedelta(days=2))
        assert len(results) == 2

        results = repo.get_by_date_range(base, base + timedelta(hours=12))
        assert len(results) == 1

    def test_get_total_by_project(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(TimeEntry(project_id=1, start_time=base, end_time=base + timedelta(hours=1), duration_seconds=3600))
        repo.create(TimeEntry(project_id=1, start_time=base + timedelta(hours=2), end_time=base + timedelta(hours=3), duration_seconds=3600))

        totals = repo.get_total_by_project(base, base + timedelta(days=1))
        assert len(totals) == 1
        assert totals[0] == (1, 7200.0)

    def test_delete(self, repo):
        now = datetime.now(timezone.utc)
        entry = repo.create(TimeEntry(project_id=1, start_time=now))
        repo.delete(entry.id)
        assert repo.get_running() is None

    def test_purge_before_deletes_old_finished_entries(self, repo):
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        recent = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(TimeEntry(project_id=1, start_time=old, end_time=old + timedelta(hours=1), duration_seconds=3600))
        repo.create(TimeEntry(project_id=1, start_time=recent, end_time=recent + timedelta(hours=1), duration_seconds=3600))

        deleted = repo.purge_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert deleted == 1
        remaining = repo.get_by_date_range(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
        assert len(remaining) == 1

    def test_purge_before_does_not_delete_running_entries(self, repo):
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        repo.create(TimeEntry(project_id=1, start_time=old))  # end_time is NULL
        deleted = repo.purge_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert deleted == 0
        assert repo.get_running() is not None


class TestWindowEventRepository:
    @pytest.fixture
    def repo(self, in_memory_db):
        return WindowEventRepository(in_memory_db)

    def test_create_and_retrieve(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        event = WindowEvent(
            window_title="test.py - VS Code",
            app_name="code.exe",
            start_time=base,
            end_time=base + timedelta(minutes=30),
            duration_seconds=1800,
        )
        created = repo.create(event)
        assert created.id is not None

        results = repo.get_by_date_range(base, base + timedelta(days=1))
        assert len(results) == 1
        assert results[0].app_name == "code.exe"

    def test_get_app_summary_groups_by_app(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(WindowEvent(window_title="a", app_name="code.exe", start_time=base, end_time=base + timedelta(minutes=30), duration_seconds=1800))
        repo.create(WindowEvent(window_title="b", app_name="code.exe", start_time=base + timedelta(minutes=30), end_time=base + timedelta(hours=1), duration_seconds=1800))
        repo.create(WindowEvent(window_title="c", app_name="chrome.exe", start_time=base + timedelta(hours=1), end_time=base + timedelta(hours=3), duration_seconds=7200))

        summary = repo.get_app_summary(base, base + timedelta(days=1))
        assert len(summary) == 2
        # chrome has more total time, should be first
        assert summary[0] == ("chrome.exe", 7200.0)
        assert summary[1] == ("code.exe", 3600.0)

    def test_get_title_summary_filters_by_app(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(WindowEvent(window_title="tab1", app_name="chrome.exe", start_time=base, end_time=base + timedelta(minutes=10), duration_seconds=600))
        repo.create(WindowEvent(window_title="tab2", app_name="chrome.exe", start_time=base + timedelta(minutes=10), end_time=base + timedelta(minutes=30), duration_seconds=1200))
        repo.create(WindowEvent(window_title="editor", app_name="code.exe", start_time=base + timedelta(minutes=30), end_time=base + timedelta(hours=1), duration_seconds=1800))

        summary = repo.get_title_summary("chrome.exe", base, base + timedelta(days=1))
        assert len(summary) == 2
        assert summary[0] == ("tab2", 1200.0)
        assert summary[1] == ("tab1", 600.0)

    def test_purge_before(self, repo):
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        recent = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(WindowEvent(window_title="old", app_name="a.exe", start_time=old, end_time=old + timedelta(hours=1), duration_seconds=3600))
        repo.create(WindowEvent(window_title="new", app_name="b.exe", start_time=recent, end_time=recent + timedelta(hours=1), duration_seconds=3600))

        deleted = repo.purge_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert deleted == 1
        remaining = repo.get_by_date_range(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
        assert len(remaining) == 1
        assert remaining[0].window_title == "new"


class TestIdlePeriodRepository:
    @pytest.fixture
    def repo(self, in_memory_db):
        return IdlePeriodRepository(in_memory_db)

    def test_create_and_retrieve(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        period = IdlePeriod(
            start_time=base,
            end_time=base + timedelta(minutes=10),
            duration_seconds=600,
        )
        created = repo.create(period)
        assert created.id is not None

        results = repo.get_by_date_range(base, base + timedelta(days=1))
        assert len(results) == 1

    def test_get_total_idle(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(IdlePeriod(start_time=base, end_time=base + timedelta(minutes=5), duration_seconds=300))
        repo.create(IdlePeriod(start_time=base + timedelta(hours=1), end_time=base + timedelta(hours=1, minutes=10), duration_seconds=600))

        total = repo.get_total_idle(base, base + timedelta(days=1))
        assert total == 900.0

    def test_get_total_idle_empty(self, repo):
        base = datetime(2025, 6, 1, tzinfo=timezone.utc)
        total = repo.get_total_idle(base, base + timedelta(days=1))
        assert total == 0.0

    def test_purge_before(self, repo):
        old = datetime(2024, 1, 1, tzinfo=timezone.utc)
        recent = datetime(2025, 6, 1, tzinfo=timezone.utc)
        repo.create(IdlePeriod(start_time=old, end_time=old + timedelta(minutes=5), duration_seconds=300))
        repo.create(IdlePeriod(start_time=recent, end_time=recent + timedelta(minutes=5), duration_seconds=300))

        deleted = repo.purge_before(datetime(2025, 1, 1, tzinfo=timezone.utc))
        assert deleted == 1
        remaining = repo.get_by_date_range(datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
        assert len(remaining) == 1


class TestSettingsRepository:
    @pytest.fixture
    def repo(self, in_memory_db):
        return SettingsRepository(in_memory_db)

    def test_get_set_roundtrip(self, repo):
        repo.set("theme", "dark")
        assert repo.get("theme") == "dark"

    def test_get_missing_key_returns_default(self, repo):
        assert repo.get("missing", "fallback") == "fallback"
        assert repo.get("missing") == ""

    def test_set_overwrites_existing(self, repo):
        repo.set("key", "value1")
        repo.set("key", "value2")
        assert repo.get("key") == "value2"

    def test_get_all(self, repo):
        repo.set("a", "1")
        repo.set("b", "2")
        all_settings = repo.get_all()
        assert all_settings == {"a": "1", "b": "2"}
