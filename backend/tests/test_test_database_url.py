import os
from types import SimpleNamespace

import pytest
from sqlalchemy.engine.url import make_url

from app.core.test_database import (
    TEST_DATABASE_NAME,
    DatabaseTestConfigError,
    alembic_sqlalchemy_url,
    application_database_url_from_config_sources,
    assert_test_database_target,
    configure_pytest_test_database_url,
    derive_test_database_url,
)

APP_URL = (
    "postgresql+psycopg://hr_user:s3cret%40pass@db.example:6543/acme_salary"
    "?sslmode=require"
)


def test_derive_replaces_only_the_database_name() -> None:
    derived = derive_test_database_url(APP_URL)
    url = make_url(derived)
    original = make_url(APP_URL)
    assert url.database == TEST_DATABASE_NAME
    assert url.drivername == original.drivername
    assert url.username == original.username
    assert url.password == original.password
    assert url.host == original.host
    assert url.port == original.port
    assert url.query == original.query


def test_derive_from_url_that_already_names_acme_test() -> None:
    source = "postgresql+psycopg://u:p@localhost:5432/acme_test"
    derived = derive_test_database_url(source)
    assert make_url(derived).database == TEST_DATABASE_NAME


def test_derive_rejects_missing_application_url() -> None:
    with pytest.raises(DatabaseTestConfigError, match="DATABASE_URL is not configured"):
        derive_test_database_url("   ")


def test_derive_rejects_invalid_application_url() -> None:
    with pytest.raises(DatabaseTestConfigError, match="not a valid SQLAlchemy URL"):
        derive_test_database_url("not-a-url")


def test_derive_error_does_not_include_credentials() -> None:
    with pytest.raises(DatabaseTestConfigError) as exc_info:
        derive_test_database_url("not-a-url://hr_user:s3cret@localhost/acme_salary")
    message = str(exc_info.value)
    assert "s3cret" not in message
    assert "hr_user" not in message


def test_assert_accepts_exact_acme_test_name() -> None:
    assert_test_database_target(
        "postgresql+psycopg://u:p@localhost:5432/acme_test"
    )


def test_assert_refuses_application_database() -> None:
    with pytest.raises(DatabaseTestConfigError, match="exactly acme_test"):
        assert_test_database_target(
            "postgresql+psycopg://u:p@localhost:5432/acme_salary"
        )


def test_assert_refuses_other_database_names() -> None:
    with pytest.raises(DatabaseTestConfigError, match="exactly acme_test"):
        assert_test_database_target(
            "postgresql+psycopg://u:p@localhost:5432/postgres"
        )


def test_assert_refuses_empty_url() -> None:
    with pytest.raises(DatabaseTestConfigError, match="without a test database URL"):
        assert_test_database_target("  ")


def test_assert_error_does_not_include_credentials() -> None:
    with pytest.raises(DatabaseTestConfigError) as exc_info:
        assert_test_database_target(
            "postgresql+psycopg://hr_user:s3cret@localhost:5432/acme_salary"
        )
    message = str(exc_info.value)
    assert "s3cret" not in message
    assert "hr_user" not in message


def test_reads_database_url_from_process_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", APP_URL)
    assert application_database_url_from_config_sources(search_paths=[]) == APP_URL


def test_reads_database_url_from_env_file_when_unset(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "DATABASE_URL=postgresql+psycopg://file_user:file_secret@localhost:5432/acme_salary\n",
        encoding="utf-8",
    )
    found = application_database_url_from_config_sources(search_paths=[env_file])
    assert found is not None
    assert make_url(found).username == "file_user"
    assert make_url(found).database == "acme_salary"


def test_missing_configuration_returns_none(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert application_database_url_from_config_sources(search_paths=[tmp_path / "missing.env"]) is None


def test_configure_sets_test_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", APP_URL)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    configured = configure_pytest_test_database_url()
    assert make_url(configured).database == TEST_DATABASE_NAME
    assert os.environ.get("TEST_DATABASE_URL") == configured


def test_configure_overwrites_unsafe_existing_test_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DATABASE_URL", APP_URL)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://u:p@localhost:5432/acme_salary",
    )
    configured = configure_pytest_test_database_url()
    assert make_url(configured).database == TEST_DATABASE_NAME
    assert make_url(os.environ["TEST_DATABASE_URL"]).database == TEST_DATABASE_NAME


def test_configure_fails_when_database_url_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.setattr(
        "app.core.test_database.default_env_file_paths",
        lambda: [tmp_path / "missing.env"],
    )
    with pytest.raises(DatabaseTestConfigError, match="DATABASE_URL is not configured"):
        configure_pytest_test_database_url()
    assert "TEST_DATABASE_URL" not in os.environ


def test_alembic_url_during_pytest_uses_test_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_VERSION", "9.1.1")
    test_url = "postgresql+psycopg://u:p@localhost:5432/acme_test"
    monkeypatch.setenv("TEST_DATABASE_URL", test_url)
    assert alembic_sqlalchemy_url() == test_url


def test_alembic_url_during_pytest_refuses_other_databases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_VERSION", "9.1.1")
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://u:p@localhost:5432/acme_salary",
    )
    with pytest.raises(DatabaseTestConfigError, match="exactly acme_test"):
        alembic_sqlalchemy_url()


def test_alembic_url_during_pytest_does_not_fall_back_to_application_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYTEST_VERSION", "9.1.1")
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(DatabaseTestConfigError, match="will not be used"):
        alembic_sqlalchemy_url()


def test_ordinary_alembic_uses_application_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PYTEST_VERSION", raising=False)
    monkeypatch.setenv(
        "TEST_DATABASE_URL",
        "postgresql+psycopg://u:p@localhost:5432/acme_test",
    )
    application_url = "postgresql+psycopg://u:p@localhost:5432/acme_salary"
    monkeypatch.setattr(
        "app.core.config.get_settings",
        lambda: SimpleNamespace(database_url=application_url),
    )
    assert alembic_sqlalchemy_url() == application_url

