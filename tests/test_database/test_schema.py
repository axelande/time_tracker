from src.database.schema import initialize_database


class TestSchema:
    def test_initialize_creates_tables(self, in_memory_db):
        conn = in_memory_db.get_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = {row["name"] for row in rows}

        assert "projects" in table_names
        assert "time_entries" in table_names
        assert "window_events" in table_names
        assert "idle_periods" in table_names
        assert "settings" in table_names

    def test_initialize_is_idempotent(self, in_memory_db):
        # Call initialize again -- should not raise
        initialize_database(in_memory_db)
        conn = in_memory_db.get_connection()
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert len(rows) >= 5
