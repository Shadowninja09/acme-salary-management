import pytest

from scripts.seed_dev_data import SeedTargetError, assert_safe_seed_target

DEV_URL = "postgresql+psycopg://user:secret@localhost:5432/acme_salary"
TEST_URL = "postgresql+psycopg://user:secret@localhost:5432/acme_test"


def test_accepts_acme_salary_when_not_the_test_database() -> None:
    assert_safe_seed_target(DEV_URL, TEST_URL)


def test_rejects_acme_test_database_name() -> None:
    with pytest.raises(SeedTargetError, match="test database"):
        assert_safe_seed_target(TEST_URL, None)


def test_rejects_url_matching_test_database_url() -> None:
    with pytest.raises(SeedTargetError, match="TEST_DATABASE_URL"):
        assert_safe_seed_target(DEV_URL, DEV_URL)


def test_rejects_unexpected_database_name() -> None:
    other = "postgresql+psycopg://user:secret@localhost:5432/postgres"
    with pytest.raises(SeedTargetError, match="unexpected database"):
        assert_safe_seed_target(other, TEST_URL)


def test_guard_error_does_not_include_credentials() -> None:
    with pytest.raises(SeedTargetError) as exc_info:
        assert_safe_seed_target(TEST_URL, None)
    assert "secret" not in str(exc_info.value)
    assert "user:" not in str(exc_info.value)


def test_rejects_same_host_port_database_with_different_credentials() -> None:
    development_url = (
        "postgresql+psycopg://dev_user:dev_secret@localhost:5432/acme_salary"
    )
    test_url = (
        "postgresql+psycopg://test_user:test_secret@localhost:5432/acme_salary"
    )
    with pytest.raises(SeedTargetError) as exc_info:
        assert_safe_seed_target(development_url, test_url)
    message = str(exc_info.value)
    assert "dev_user" not in message
    assert "dev_secret" not in message
    assert "test_user" not in message
    assert "test_secret" not in message
