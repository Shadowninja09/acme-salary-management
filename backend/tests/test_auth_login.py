import hashlib
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from pydantic import ValidationError
from pydantic_settings import SettingsConfigDict
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.api.auth import INVALID_CREDENTIALS_DETAIL, SESSION_COOKIE_NAME
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.user_session import UserSession
from app.services.sessions import hash_session_token, issue_hr_manager_session

_TEST_USERNAME = "hr.manager"
_TEST_PASSWORD = "test-only-login-password"
_TEST_PASSWORD_HASH = PasswordHasher().hash(_TEST_PASSWORD)
_PLACEHOLDER_DATABASE_URL = "postgresql+psycopg://pytest:pytest@127.0.0.1:1/acme_unused"
_SESSION_MAX_AGE_SECONDS = 28800


class _IsolatedSettings(Settings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[Settings],
        init_settings: object,
        env_settings: object,
        dotenv_settings: object,
        file_secret_settings: object,
    ) -> tuple[object, ...]:
        return (init_settings,)


def _login_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": _PLACEHOLDER_DATABASE_URL,
        "hr_manager_identity": "audit-hr-manager",
        "hr_manager_username": _TEST_USERNAME,
        "hr_manager_password_hash": _TEST_PASSWORD_HASH,
        "session_cookie_secure": False,
        "session_max_age_seconds": _SESSION_MAX_AGE_SECONDS,
    }
    values.update(overrides)
    return _IsolatedSettings(**values)


@pytest.fixture
def login_settings() -> Settings:
    return _login_settings()


@pytest.fixture
def login_client(
    api_client: TestClient,
    login_settings: Settings,
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_settings] = lambda: login_settings
    try:
        yield api_client
    finally:
        app.dependency_overrides.pop(get_settings, None)


def _session_count(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(UserSession)) or 0)


def _cookie_header(response) -> str:
    return response.headers.get("set-cookie", "")


def test_valid_credentials_return_success(login_client: TestClient) -> None:
    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_invalid_username_returns_401(
    login_client: TestClient,
    db_session: Session,
) -> None:
    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": "other.user", "password": _TEST_PASSWORD},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_CREDENTIALS_DETAIL}
    assert SESSION_COOKIE_NAME not in _cookie_header(response).lower()
    assert _session_count(db_session) == 0


def test_invalid_password_returns_401(
    login_client: TestClient,
    db_session: Session,
) -> None:
    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": INVALID_CREDENTIALS_DETAIL}
    assert SESSION_COOKIE_NAME not in _cookie_header(response).lower()
    assert _session_count(db_session) == 0


def test_successful_login_creates_one_hashed_session(
    login_client: TestClient,
    db_session: Session,
    login_settings: Settings,
) -> None:
    before = datetime.now(timezone.utc)
    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
    )
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    assert _session_count(db_session) == 1

    raw_token = response.cookies.get(SESSION_COOKIE_NAME)
    assert raw_token
    assert raw_token not in response.text
    assert raw_token not in str(response.json())

    stored = db_session.scalar(select(UserSession))
    assert stored is not None
    assert stored.token_hash == hash_session_token(raw_token)
    assert stored.token_hash != raw_token
    assert len(stored.token_hash) == 64
    assert stored.token_hash == hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    assert stored.revoked_at is None

    expected_min = before + timedelta(seconds=login_settings.session_max_age_seconds)
    expected_max = after + timedelta(seconds=login_settings.session_max_age_seconds)
    assert expected_min <= stored.expires_at <= expected_max


def test_session_cookie_attributes(
    login_client: TestClient,
    login_settings: Settings,
) -> None:
    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
    )

    header = _cookie_header(response).lower()
    assert response.status_code == 200
    assert f"{SESSION_COOKIE_NAME}=" in header
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header
    assert f"max-age={login_settings.session_max_age_seconds}" in header
    assert "secure" not in header.split(";")[0]
    assert "secure" not in [part.strip() for part in header.split(";")]


def test_secure_cookie_attribute_when_enabled(
    api_client: TestClient,
    login_settings: Settings,
) -> None:
    secure_settings = _login_settings(session_cookie_secure=True)
    app.dependency_overrides[get_settings] = lambda: secure_settings
    try:
        response = api_client.post(
            "/api/v1/auth/login",
            json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)

    header = _cookie_header(response).lower()
    assert response.status_code == 200
    assert "secure" in [part.strip() for part in header.split(";")]


def test_failed_authentication_creates_no_session(
    login_client: TestClient,
    db_session: Session,
) -> None:
    login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": "wrong-password"},
    )
    assert _session_count(db_session) == 0


def test_commit_failure_does_not_set_session_cookie(
    db_session: Session,
    login_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_commit() -> None:
        raise OperationalError("COMMIT", {}, Exception("commit failed"))

    rollback_invoked = False
    original_rollback = db_session.rollback

    def spy_rollback() -> None:
        nonlocal rollback_invoked
        rollback_invoked = True
        original_rollback()

    monkeypatch.setattr(db_session, "commit", fail_commit)
    monkeypatch.setattr(db_session, "rollback", spy_rollback)

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_settings] = lambda: login_settings
    try:
        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/v1/auth/login",
            json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_db, None)

    body = response.text
    assert response.status_code == 500
    assert SESSION_COOKIE_NAME not in _cookie_header(response).lower()
    assert "OperationalError" not in body
    assert "commit failed" not in body
    assert "COMMIT" not in body
    assert "Traceback" not in body
    assert "sqlalchemy" not in body.lower()
    assert rollback_invoked is True


def test_persistence_failure_does_not_set_session_cookie(
    login_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_issue_session(*args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT INTO user_sessions", {}, Exception())

    monkeypatch.setattr("app.api.auth.issue_hr_manager_session", fail_issue_session)

    response = login_client.post(
        "/api/v1/auth/login",
        json={"username": _TEST_USERNAME, "password": _TEST_PASSWORD},
    )

    assert response.status_code == 500
    assert response.json() == {"detail": "Unable to create session"}
    assert SESSION_COOKIE_NAME not in _cookie_header(response).lower()
    assert _session_count(db_session) == 0


def test_issue_session_uses_configured_lifetime(db_session: Session) -> None:
    issued_at = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=issued_at,
    )

    assert record.expires_at == issued_at + timedelta(seconds=3600)
    assert record.token_hash == hash_session_token(raw_token)
    assert raw_token != record.token_hash


def test_session_cookie_secure_is_required() -> None:
    try:
        _IsolatedSettings(
            database_url=_PLACEHOLDER_DATABASE_URL,
            hr_manager_identity="audit-hr-manager",
            hr_manager_username=_TEST_USERNAME,
            hr_manager_password_hash=_TEST_PASSWORD_HASH,
        )
    except ValidationError as exc:
        assert "session_cookie_secure" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")


def test_non_positive_session_max_age_is_rejected() -> None:
    try:
        _login_settings(session_max_age_seconds=0)
    except ValidationError as exc:
        assert "session_max_age_seconds" in str(exc)
    else:
        raise AssertionError("expected Settings validation to fail")
