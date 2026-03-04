from src.gui.components.time_display import format_seconds, format_hours_minutes


class TestFormatSeconds:
    def test_zero(self):
        assert format_seconds(0) == "00:00:00"

    def test_seconds_only(self):
        assert format_seconds(45) == "00:00:45"

    def test_minutes_and_seconds(self):
        assert format_seconds(125) == "00:02:05"

    def test_hours_minutes_seconds(self):
        assert format_seconds(3661) == "01:01:01"

    def test_large_value(self):
        assert format_seconds(86400) == "24:00:00"

    def test_fractional_seconds_truncated(self):
        assert format_seconds(59.9) == "00:00:59"


class TestFormatHoursMinutes:
    def test_zero(self):
        assert format_hours_minutes(0) == "0m"

    def test_minutes_only(self):
        assert format_hours_minutes(300) == "5m"

    def test_hours_and_minutes(self):
        assert format_hours_minutes(5400) == "1h 30m"

    def test_exact_hours(self):
        assert format_hours_minutes(7200) == "2h 0m"
