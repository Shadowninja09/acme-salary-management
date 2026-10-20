from __future__ import annotations

import os
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy.engine.url import make_url
from sqlalchemy.exc import ArgumentError

TEST_DATABASE_NAME = "acme_test"


class DatabaseTestConfigError(RuntimeError):
    """Raised when the test database URL cannot be derived or is not safe."""


def default_env_file_paths() -> list[Path]:
    backend_root = Path(__file__).resolve().parents[2]
    candidates = [
        Path.cwd() / ".env",
        backend_root / ".env",
        backend_root.parent / ".env",
    ]
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(path)
    return unique


def application_database_url_from_config_sources(
    search_paths: list[Path] | None = None,
) -> str | None:
    from_env = os.environ.get("DATABASE_URL", "").strip()
    if from_env:
        return from_env
    for path in search_paths if search_paths is not None else default_env_file_paths():
        if not path.is_file():
            continue
        values = dotenv_values(path)
        value = (values.get("DATABASE_URL") or "").strip()
        if value:
            return value
    return None


def derive_test_database_url(application_database_url: str) -> str:
    stripped = application_database_url.strip()
    if not stripped:
        raise DatabaseTestConfigError(
            "DATABASE_URL is not configured; cannot derive the test database URL"
        )
    try:
        url = make_url(stripped)
    except ArgumentError as exc:
        raise DatabaseTestConfigError(
            "DATABASE_URL is not a valid SQLAlchemy URL; "
            "cannot derive the test database URL"
        ) from exc
    test_url = url.set(database=TEST_DATABASE_NAME)
    rendered = test_url.render_as_string(hide_password=False)
    assert_test_database_target(rendered)
    return rendered


def assert_test_database_target(database_url: str) -> None:
    stripped = database_url.strip()
    if not stripped:
        raise DatabaseTestConfigError(
            "Refusing to run test migrations without a test database URL"
        )
    try:
        url = make_url(stripped)
    except ArgumentError as exc:
        raise DatabaseTestConfigError(
            "Refusing to run test migrations because the test database URL "
            "is not valid"
        ) from exc
    if url.database != TEST_DATABASE_NAME:
        raise DatabaseTestConfigError(
            "Refusing to run test migrations unless the target database name "
            f"is exactly {TEST_DATABASE_NAME}"
        )


def alembic_sqlalchemy_url() -> str:
    if os.environ.get("PYTEST_VERSION") is not None:
        test_url = os.environ.get("TEST_DATABASE_URL", "").strip()
        if not test_url:
            raise DatabaseTestConfigError(
                "Refusing to run test migrations because TEST_DATABASE_URL "
                "is not set; the application DATABASE_URL will not be used"
            )
        assert_test_database_target(test_url)
        return test_url
    from app.core.config import get_settings

    return get_settings().database_url


def configure_pytest_test_database_url() -> str:
    application_url = application_database_url_from_config_sources()
    if not application_url:
        raise DatabaseTestConfigError(
            "DATABASE_URL is not configured; cannot derive the test database URL"
        )
    test_url = derive_test_database_url(application_url)
    os.environ["TEST_DATABASE_URL"] = test_url
    return test_url
