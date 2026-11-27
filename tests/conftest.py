"""Pytest fixtures shared by the suite.

The schema reset is deliberately guarded: it only runs against a PostgreSQL database whose name
ends in ``_test``. ``create_all`` cannot alter an existing ``bookings.time_slot_id`` or add the new
cargo index, so the test database is rebuilt once per session. SQLite development databases are
left untouched; run ``alembic upgrade head`` for those.
"""

import pytest
from sqlalchemy import text

import app.models  # noqa: F401  -- register every table on Base.metadata
from app.config import settings
from app.database import Base, engine

TEST_ADMIN_CODE = "test-admin-code-0123456789"


@pytest.fixture(autouse=True)
def _default_admin_code(monkeypatch):
    """Every test gets a known admin code unless it overrides it."""
    monkeypatch.setattr(settings, "ADMIN_CODE", TEST_ADMIN_CODE)


@pytest.fixture
def admin_code():
    return TEST_ADMIN_CODE


def _is_postgres() -> bool:
    return engine.dialect.name == "postgresql"


@pytest.fixture(scope="session", autouse=True)
def _reset_schema():
    if _is_postgres():
        database = engine.url.database or ""
        if not database.endswith("_test"):
            raise RuntimeError(
                "Refusing to reset a non-test PostgreSQL database "
                f"({database!r}); the name must end with '_test'."
            )
        Base.metadata.drop_all(bind=engine)
        # SQLAlchemy may leave the native enum type behind after drop_all.
        with engine.begin() as connection:
            connection.execute(text("DROP TYPE IF EXISTS userrole CASCADE"))
        Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    """Point UPLOAD_DIR at a per-test temp directory."""
    directory = tmp_path / "uploads"
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(directory))
    return directory
