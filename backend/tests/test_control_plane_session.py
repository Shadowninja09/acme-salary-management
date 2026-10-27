import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.core.test_database import alembic_sqlalchemy_url
from app.db.session import SessionLocal, engine, get_db
from control_plane_migrations.url import ControlPlaneMigrationConfigError

BACKEND_ROOT = Path(__file__).resolve().parents[1]
CONTROL_PLANE_URL = (
    "postgresql+psycopg://control:secret@db.example:5432/acme_control_plane"
)
ASSESSMENT_URL = "postgresql+psycopg://assessment:secret@db.example:5432/acme_salary"


def _redact(text: str) -> str:
    return re.sub(r"postgresql(?:\+\w+)?://\S+", "postgresql://***", text)


@pytest.fixture
def control_plane_session_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("CONTROL_PLANE_DATABASE_URL", raising=False)
    import app.control_plane.session as session_module

    session_module.dispose_control_plane_engine()
    yield session_module
    session_module.dispose_control_plane_engine()


def test_missing_control_plane_url_fails_when_access_is_requested(
    control_plane_session_module,
) -> None:
    with pytest.raises(ControlPlaneMigrationConfigError) as caught:
        control_plane_session_module.control_plane_sessionmaker(search_paths=[])
    message = str(caught.value)
    assert "CONTROL_PLANE_DATABASE_URL" in message
    assert "DATABASE_URL is not used" in message
    assert "://" not in message


def test_unsafe_control_plane_targets_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    control_plane_session_module,
) -> None:
    monkeypatch.setenv("DATABASE_URL", ASSESSMENT_URL)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://assessment:secret@db.example:5432/acme_test",
    )
    for database_name in ("acme_salary", "acme_test"):
        monkeypatch.setenv(
            "CONTROL_PLANE_DATABASE_URL",
            f"postgresql+psycopg://control:secret@db.example:5432/{database_name}",
        )
        with pytest.raises(ControlPlaneMigrationConfigError, match=database_name):
            control_plane_session_module.control_plane_sessionmaker(search_paths=[])

    monkeypatch.setenv(
        "CONTROL_PLANE_DATABASE_URL",
        "postgresql+psycopg://other:other@db.example:5432/custom_app",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://assessment:secret@db.example:5432/custom_app",
    )
    with pytest.raises(ControlPlaneMigrationConfigError, match="matches DATABASE_URL"):
        control_plane_session_module.control_plane_sessionmaker(search_paths=[])


def test_valid_url_builds_a_separate_engine_and_session_factory(
    monkeypatch: pytest.MonkeyPatch,
    control_plane_session_module,
) -> None:
    monkeypatch.setenv("CONTROL_PLANE_DATABASE_URL", CONTROL_PLANE_URL)
    monkeypatch.setenv("DATABASE_URL", ASSESSMENT_URL)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)

    factory = control_plane_session_module.control_plane_sessionmaker(search_paths=[])
    session = factory()
    try:
        bind = session.get_bind()
        assert bind is not engine
        assert bind.url.database == "acme_control_plane"
        assert "secret" not in str(bind.url)
    finally:
        session.close()
        bind.dispose()

    assert SessionLocal.kw["bind"] is engine
    assert engine is not bind


def test_session_helper_commits_and_rolls_back(
    control_plane_session_module,
) -> None:
    events: list[str] = []

    class _FakeSession:
        def commit(self) -> None:
            events.append("commit")

        def rollback(self) -> None:
            events.append("rollback")

        def close(self) -> None:
            events.append("close")

    control_plane_session_module.get_control_plane_sessionmaker = lambda: (
        lambda: _FakeSession()
    )
    with control_plane_session_module.control_plane_session():
        pass
    assert events == ["commit", "close"]

    events.clear()
    with pytest.raises(RuntimeError, match="failed"):
        with control_plane_session_module.control_plane_session():
            raise RuntimeError("failed")
    assert events == ["rollback", "close"]


def test_assessment_database_path_remains_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assessment_engine = engine
    get_db_source = ast.parse(Path(get_db.__code__.co_filename).read_text(encoding="utf-8"))
    get_db_calls = [
        node.func.id
        for node in ast.walk(get_db_source)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "SessionLocal" in get_db_calls

    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    application_url = "postgresql+psycopg://assessment:secret@db.example:5432/acme_salary"
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("SettingsStub", (), {"database_url": application_url})(),
    )
    assert alembic_sqlalchemy_url() == application_url
    assert engine is assessment_engine
    assert SessionLocal.kw["bind"] is assessment_engine


def test_importing_the_assessment_app_does_not_require_control_plane_url() -> None:
    env = os.environ.copy()
    env.pop("CONTROL_PLANE_DATABASE_URL", None)
    env["PYTHONPATH"] = str(BACKEND_ROOT)
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys\n"
                "import app.main\n"
                "import app.db.session\n"
                "assert 'app.control_plane.session' not in sys.modules\n"
            ),
        ],
        cwd=BACKEND_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, _redact(completed.stderr)
    assert "CONTROL_PLANE_DATABASE_URL" not in completed.stderr
