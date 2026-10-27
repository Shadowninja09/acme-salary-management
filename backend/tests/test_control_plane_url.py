import ast
from pathlib import Path

import pytest
from sqlalchemy.engine.url import make_url

from app.core.config import Settings
from app.core.test_database import TEST_DATABASE_NAME, alembic_sqlalchemy_url
from control_plane_migrations.url import (
    ASSESSMENT_DATABASE_NAME,
    CONTROL_PLANE_DATABASE_URL_ENV,
    ControlPlaneMigrationConfigError,
    resolve_configured_control_plane_database_url,
    resolve_control_plane_sqlalchemy_url,
)

ASSESSMENT_URL = "postgresql+psycopg://assessment:secret@db.example:5432/custom_app"
CONTROL_PLANE_URL = (
    "postgresql+psycopg://control:other@db.example:5432/acme_control_plane"
    "?sslmode=require"
)
BACKEND_ROOT = Path(__file__).resolve().parents[1]


def test_missing_control_plane_url_does_not_use_assessment_urls() -> None:
    with pytest.raises(
        ControlPlaneMigrationConfigError, match="DATABASE_URL is not used"
    ):
        resolve_control_plane_sqlalchemy_url(
            None,
            assessment_database_url=ASSESSMENT_URL,
            test_database_url=ASSESSMENT_URL.replace("custom_app", "acme_test"),
        )
    with pytest.raises(ControlPlaneMigrationConfigError):
        resolve_control_plane_sqlalchemy_url("   ")


def test_explicit_url_is_kept_when_it_is_a_different_database() -> None:
    resolved = resolve_control_plane_sqlalchemy_url(
        f"  {CONTROL_PLANE_URL}  ",
        assessment_database_url=ASSESSMENT_URL,
        test_database_url="postgresql+psycopg://assessment:secret@db.example:5432/acme_test",
    )
    assert resolved == CONTROL_PLANE_URL
    assert make_url(resolved).database == "acme_control_plane"


@pytest.mark.parametrize(
    "database_name",
    [ASSESSMENT_DATABASE_NAME, TEST_DATABASE_NAME],
)
def test_forbidden_database_names_are_rejected_on_any_host(
    database_name: str,
) -> None:
    with pytest.raises(ControlPlaneMigrationConfigError, match=database_name):
        resolve_control_plane_sqlalchemy_url(
            f"postgresql+psycopg://control:secret@127.0.0.1:5432/{database_name}"
        )


def test_name_comparison_does_not_use_a_substring() -> None:
    resolved = resolve_control_plane_sqlalchemy_url(
        "postgresql+psycopg://control:secret@db.example:5432/acme_salary_copy",
        assessment_database_url=(
            "postgresql+psycopg://assessment:secret@db.example:5432/acme_salary"
        ),
        test_database_url=(
            "postgresql+psycopg://assessment:secret@db.example:5432/acme_test"
        ),
    )
    assert make_url(resolved).database == "acme_salary_copy"

    resolved_test_prefix = resolve_control_plane_sqlalchemy_url(
        "postgresql+psycopg://control:secret@db.example:5432/not_acme_test"
    )
    assert make_url(resolved_test_prefix).database == "not_acme_test"


def test_same_host_port_and_database_are_rejected_despite_other_url_fields() -> None:
    with pytest.raises(ControlPlaneMigrationConfigError, match="matches DATABASE_URL"):
        resolve_control_plane_sqlalchemy_url(
            "postgresql://other-user:other-secret@DB.Example:5432/custom_app"
            "?sslmode=require",
            assessment_database_url=ASSESSMENT_URL,
        )


def test_omitted_postgresql_port_matches_explicit_5432() -> None:
    with pytest.raises(ControlPlaneMigrationConfigError, match="matches DATABASE_URL"):
        resolve_control_plane_sqlalchemy_url(
            "postgresql+psycopg://control:secret@db.example/custom_app",
            assessment_database_url=ASSESSMENT_URL,
        )


def test_different_port_is_not_the_same_target() -> None:
    resolved = resolve_control_plane_sqlalchemy_url(
        "postgresql+psycopg://control:secret@db.example:5433/custom_app",
        assessment_database_url=ASSESSMENT_URL,
    )
    assert make_url(resolved).port == 5433


def test_localhost_and_loopback_are_not_treated_as_the_same_host() -> None:
    resolved = resolve_control_plane_sqlalchemy_url(
        "postgresql+psycopg://control:secret@127.0.0.1:5432/custom_app",
        assessment_database_url=(
            "postgresql+psycopg://assessment:secret@localhost:5432/custom_app"
        ),
    )
    assert make_url(resolved).host == "127.0.0.1"


def test_derived_acme_test_target_is_rejected() -> None:
    with pytest.raises(ControlPlaneMigrationConfigError, match="acme_test"):
        resolve_control_plane_sqlalchemy_url(
            "postgresql+psycopg://control:secret@db.example:5432/acme_test",
            assessment_database_url=ASSESSMENT_URL,
        )


def test_ini_sqlalchemy_url_must_stay_empty() -> None:
    with pytest.raises(ControlPlaneMigrationConfigError, match="must stay empty"):
        resolve_control_plane_sqlalchemy_url(
            CONTROL_PLANE_URL,
            ini_sqlalchemy_url=ASSESSMENT_URL,
        )


def test_configured_url_comes_from_the_control_plane_variable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(CONTROL_PLANE_DATABASE_URL_ENV, raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://assessment:secret@db.example:5432/acme_salary\n"
        "TEST_DATABASE_URL=postgresql+psycopg://assessment:secret@db.example:5432/acme_test\n"
        f"{CONTROL_PLANE_DATABASE_URL_ENV}={CONTROL_PLANE_URL}\n",
        encoding="utf-8",
    )

    resolved = resolve_configured_control_plane_database_url(search_paths=[env_file])
    assert resolved == CONTROL_PLANE_URL

    monkeypatch.setenv(
        CONTROL_PLANE_DATABASE_URL_ENV,
        "postgresql+psycopg://control:secret@db.example:5432/from_environment",
    )
    resolved_from_env = resolve_configured_control_plane_database_url(
        search_paths=[env_file]
    )
    assert make_url(resolved_from_env).database == "from_environment"


def test_configured_url_reports_missing_without_falling_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.delenv(CONTROL_PLANE_DATABASE_URL_ENV, raising=False)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://assessment:secret@db.example:5432/acme_salary",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://assessment:secret@db.example:5432/acme_salary\n",
        encoding="utf-8",
    )
    with pytest.raises(
        ControlPlaneMigrationConfigError, match="DATABASE_URL is not used"
    ):
        resolve_configured_control_plane_database_url(search_paths=[env_file])


def test_application_settings_and_assessment_alembic_url_are_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert "database_url" in Settings.model_fields
    assert not any("control_plane" in name for name in Settings.model_fields)
    env_source = (
        BACKEND_ROOT / "control_plane_migrations" / "env.py"
    ).read_text(encoding="utf-8")
    env_tree = ast.parse(env_source)
    imported_names = {
        alias.name
        for node in env_tree.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    }
    assert "resolve_configured_control_plane_database_url" in imported_names
    assert "alembic_sqlalchemy_url" not in imported_names
    assert "CONTROL_PLANE_DATABASE_URL" not in (
        BACKEND_ROOT / "app" / "core" / "config.py"
    ).read_text(encoding="utf-8")

    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    application_url = "postgresql+psycopg://assessment:secret@db.example:5432/acme_salary"
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: type("SettingsStub", (), {"database_url": application_url})(),
    )
    assert alembic_sqlalchemy_url() == application_url
