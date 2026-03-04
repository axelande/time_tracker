from datetime import datetime, timezone

from src.core.models import TimeEntry, Project, WindowEvent, IdlePeriod


class TestTimeEntry:
    def test_is_running_when_end_time_is_none(self):
        entry = TimeEntry(start_time=datetime.now(timezone.utc))
        assert entry.is_running is True

    def test_is_not_running_when_end_time_set(self):
        entry = TimeEntry(
            start_time=datetime.now(timezone.utc),
            end_time=datetime.now(timezone.utc),
        )
        assert entry.is_running is False

    def test_default_values(self):
        entry = TimeEntry()
        assert entry.id is None
        assert entry.project_id == 0
        assert entry.note == ""
        assert entry.duration_seconds is None


class TestProject:
    def test_default_values(self):
        project = Project()
        assert project.id is None
        assert project.name == ""
        assert project.color == "#3B8ED0"
        assert project.is_archived is False


class TestWindowEvent:
    def test_default_values(self):
        event = WindowEvent()
        assert event.duration_seconds == 0.0
        assert event.project_id is None


class TestIdlePeriod:
    def test_default_values(self):
        period = IdlePeriod()
        assert period.duration_seconds == 0.0
        assert period.start_time is None
