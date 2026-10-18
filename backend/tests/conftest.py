import os
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://acme:acme@localhost:5432/acme_test",
)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.main import app

BACKEND_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def test_database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "").strip()
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL is not configured; skipping database integration tests"
        )
    return url


@pytest.fixture(scope="session")
def migrated_test_engine(test_database_url: str) -> Generator[Engine, None, None]:
    engine = create_engine(test_database_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception as exc:
        engine.dispose()
        pytest.fail(
            f"TEST_DATABASE_URL is set but the database is unreachable: {exc}"
        )

    alembic_cfg = Config(str(BACKEND_ROOT / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    alembic_cfg.set_main_option("prepend_sys_path", str(BACKEND_ROOT))
    command.upgrade(alembic_cfg, "head")

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_test_engine: Engine) -> Generator[Session, None, None]:
    connection = migrated_test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()
