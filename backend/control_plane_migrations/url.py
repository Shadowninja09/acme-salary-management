"""Control-plane Alembic URL.

The migration URL is ``CONTROL_PLANE_DATABASE_URL``, from the environment or
from the same ``.env`` files the assessment URL reader searches. It is not an
application ``Settings`` field.

This module does not use that value as ``DATABASE_URL``. ``DATABASE_URL`` and
``TEST_DATABASE_URL`` are read only so their parsed host, port, and database
name can be rejected. Credentials, privilege separation, and a control-plane
test-database name are not decided here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

from app.core.test_database import (
    TEST_DATABASE_NAME,
    DatabaseTestConfigError,
    application_database_url_from_config_sources,
    default_env_file_paths,
    derive_test_database_url,
)

CONTROL_PLANE_DATABASE_URL_ENV = "CONTROL_PLANE_DATABASE_URL"
ASSESSMENT_DATABASE_NAME = "acme_salary"
FORBIDDEN_DATABASE_NAMES = frozenset({ASSESSMENT_DATABASE_NAME, TEST_DATABASE_NAME})
POSTGRESQL_DEFAULT_PORT = 5432


class ControlPlaneMigrationConfigError(RuntimeError):
    """Raised when the control-plane migration URL is missing or unsafe."""


def _connection_target(database_url: str) -> tuple[str, int, str]:
    try:
        parsed = make_url(database_url.strip())
    except ArgumentError as exc:
        raise ControlPlaneMigrationConfigError(
            "Control-plane migration URL is not a valid SQLAlchemy URL. "
            "DATABASE_URL is not used."
        ) from exc
    if parsed.get_backend_name() != "postgresql":
        raise ControlPlaneMigrationConfigError(
            "Control-plane migrations require a PostgreSQL URL."
        )
    host = (parsed.host or "").lower()
    database_name = parsed.database or ""
    if not host or not database_name:
        raise ControlPlaneMigrationConfigError(
            "Control-plane migration URL must include a host and database name."
        )
    port = POSTGRESQL_DEFAULT_PORT if parsed.port is None else parsed.port
    return (host, port, database_name)


def _optional_target(database_url: str | None) -> tuple[str, int, str] | None:
    if database_url is None or not database_url.strip():
        return None
    try:
        return _connection_target(database_url)
    except ControlPlaneMigrationConfigError:
        return None


def _reject_same_target(
    target: tuple[str, int, str],
    other: tuple[str, int, str] | None,
    message: str,
) -> None:
    if other is not None and target == other:
        host, port, database_name = target
        raise ControlPlaneMigrationConfigError(
            f"{message} Host {host}, port {port}, database {database_name}."
        )


def _first_configured_url(
    env_name: str,
    search_paths: list[Path] | None,
) -> str | None:
    from_env = os.environ.get(env_name, "").strip()
    if from_env:
        return from_env
    paths = search_paths if search_paths is not None else default_env_file_paths()
    for path in paths:
        if not path.is_file():
            continue
        value = (dotenv_values(path).get(env_name) or "").strip()
        if value:
            return value
    return None


def resolve_control_plane_sqlalchemy_url(
    configured_url: str | None,
    *,
    ini_sqlalchemy_url: str | None = None,
    assessment_database_url: str | None = None,
    test_database_url: str | None = None,
) -> str:
    if (ini_sqlalchemy_url or "").strip():
        raise ControlPlaneMigrationConfigError(
            "alembic-control-plane.ini sqlalchemy.url must stay empty. "
            "Set CONTROL_PLANE_DATABASE_URL instead. DATABASE_URL is not used."
        )
    url = (configured_url or "").strip()
    if not url:
        raise ControlPlaneMigrationConfigError(
            "Control-plane Alembic requires CONTROL_PLANE_DATABASE_URL. "
            "The assessment DATABASE_URL is not used."
        )

    target = _connection_target(url)
    database_name = target[2]
    if database_name in FORBIDDEN_DATABASE_NAMES:
        raise ControlPlaneMigrationConfigError(
            "Refusing control-plane migrations for database "
            f"{database_name}. DATABASE_URL is not used."
        )

    _reject_same_target(
        target,
        _optional_target(assessment_database_url),
        "Refusing control-plane migrations because the target matches DATABASE_URL.",
    )
    _reject_same_target(
        target,
        _optional_target(test_database_url),
        "Refusing control-plane migrations because the target matches "
        "TEST_DATABASE_URL.",
    )
    derived_test_url = None
    if assessment_database_url and assessment_database_url.strip():
        try:
            derived_test_url = derive_test_database_url(assessment_database_url)
        except DatabaseTestConfigError:
            derived_test_url = None
    _reject_same_target(
        target,
        _optional_target(derived_test_url),
        "Refusing control-plane migrations because the target matches the "
        "derived acme_test database.",
    )
    return url


def resolve_configured_control_plane_database_url(
    search_paths: list[Path] | None = None,
    *,
    ini_sqlalchemy_url: str | None = None,
) -> str:
    return resolve_control_plane_sqlalchemy_url(
        _first_configured_url(CONTROL_PLANE_DATABASE_URL_ENV, search_paths),
        ini_sqlalchemy_url=ini_sqlalchemy_url,
        assessment_database_url=application_database_url_from_config_sources(
            search_paths
        ),
        test_database_url=_first_configured_url("TEST_DATABASE_URL", search_paths),
    )
