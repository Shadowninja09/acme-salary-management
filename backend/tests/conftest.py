import os
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://pytest:pytest@127.0.0.1:1/acme_unused",
)

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db.session import get_db
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
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(sess: Session, trans: object) -> None:
        nonlocal nested
        if connection.closed:
            return
        if not connection.in_nested_transaction():
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.rollback()
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def api_client(db_session: Session) -> Generator[TestClient, None, None]:
    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
