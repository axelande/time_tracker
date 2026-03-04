import pytest
from pathlib import Path
from unittest.mock import MagicMock

from src.database.connection import DatabaseConnection
from src.database.schema import initialize_database
from src.core.event_bus import EventBus


@pytest.fixture
def in_memory_db():
    """Provides an initialized in-memory database."""
    db = DatabaseConnection(Path(":memory:"))
    initialize_database(db)
    yield db
    db.close()


@pytest.fixture
def event_bus():
    return EventBus()


@pytest.fixture
def mock_window_provider():
    provider = MagicMock()
    provider.get_foreground_window_info.return_value = None
    return provider


@pytest.fixture
def mock_idle_provider():
    provider = MagicMock()
    provider.get_idle_seconds.return_value = 0.0
    return provider
