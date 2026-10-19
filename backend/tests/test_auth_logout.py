from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from pydantic_settings import SettingsConfigDict
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api.auth import SESSION_COOKIE_NAME
from app.api.deps import CSRF_FAILURE_DETAIL, NOT_AUTHENTICATED_DETAIL
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.main import app
from app.models.user_session import UserSession
from app.services.csrf import CSRF_COOKIE_NAME, issue_csrf_token
from app.services.sessions import (
    SessionAuthenticationError,
    issue_hr_manager_session,
    resolve_active_session,
)

_TEST_USERNAME = "hr.manager"
_TEST_PASSWORD = "test-only-login-password"
_TEST_PASSWORD_HASH = PasswordHasher().hash(_TEST_PASSWORD)
_PLACEHOLDER_DATABASE_URL = "postgresql+psycopg://pytest:pytest@127.0.0.1:1/acme_unused"
_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)
_TEST_CSRF_SECRET = "test-only-logout-csrf-signing-secret"
_TRUSTED_LOGIN_ORIGIN = "https://hr.test"


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


def _logout_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "database_url": _PLACEHOLDER_DATABASE_URL,
        "hr_manager_identity": "audit-hr-manager",
        "hr_manager_username": _TEST_USERNAME,
        "hr_manager_password_hash": _TEST_PASSWORD_HASH,
        "session_cookie_secure": False,
        "session_max_age_seconds": 28800,
        "csrf_signing_secret": _TEST_CSRF_SECRET,
        "csrf_trusted_origins": [_TRUSTED_LOGIN_ORIGIN],
    }
    values.update(overrides)
    return _IsolatedSettings(**values)


@pytest.fixture
def logout_settings() -> Settings:
    return _logout_settings()


@pytest.fixture
def logout_client(
    api_client: TestClient,
    logout_settings: Settings,
) -> Generator[TestClient, None, None]:
    app.dependency_overrides[get_settings] = lambda: logout_settings
    try:
        yield api_client
    finally:
        app.dependency_overrides.pop(get_settings, None)


def _cookie_header(response) -> str:
    return response.headers.get("set-cookie", "")


def _set_cookie_headers(response) -> list[str]:
    headers = response.headers
    if hasattr(headers, "get_list"):
        values = headers.get_list("set-cookie")
        if values:
            return list(values)
    if hasattr(headers, "getlist"):
        values = headers.getlist("set-cookie")
        if values:
            return list(values)
    value = headers.get("set-cookie")
    return [value] if value else []


def _named_cookie(response, name: str) -> str:
    prefix = f"{name.lower()}="
    for header in _set_cookie_headers(response):
        if header.lower().startswith(prefix):
            return header
    return ""


def _csrf_token_for(session_id: int, settings: Settings) -> str:
    return issue_csrf_token(
        session_id=session_id,
        secret=settings.csrf_signing_secret.get_secret_value(),
    )


def _logout(
    client: TestClient,
    raw_token: str,
    csrf_token: str | None = None,
    *,
    send_csrf_header: bool = True,
):
    client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    if csrf_token is not None:
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
    headers = {}
    if send_csrf_header and csrf_token is not None:
        headers["X-CSRF-Token"] = csrf_token
    try:
        return client.post("/api/v1/auth/logout", headers=headers)
    finally:
        client.cookies.delete(SESSION_COOKIE_NAME)
        client.cookies.delete(CSRF_COOKIE_NAME)


def _assert_no_secret_leak(body: str, *secrets: str) -> None:
    lowered = body.lower()
    for secret in secrets:
        assert secret not in body
    assert "OperationalError" not in body
    assert "commit failed" not in body
    assert "COMMIT" not in body
    assert "Traceback" not in body
    assert "sqlalchemy" not in lowered
    assert "token_hash" not in lowered


def test_logout_revokes_current_session_and_clears_cookie(
    logout_client: TestClient,
    db_session: Session,
    logout_settings: Settings,
) -> None:
    before = datetime.now(timezone.utc)
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=before,
    )
    csrf_token = _csrf_token_for(record.id, logout_settings)

    response = _logout(logout_client, raw_token, csrf_token)
    after = datetime.now(timezone.utc)

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert raw_token not in response.text
    assert record.token_hash not in response.text
    assert csrf_token not in response.text
    assert logout_settings.csrf_signing_secret.get_secret_value() not in response.text

    db_session.refresh(record)
    assert record.revoked_at is not None
    assert record.revoked_at.tzinfo is not None
    assert before <= record.revoked_at <= after

    session_header = _named_cookie(response, SESSION_COOKIE_NAME).lower()
    csrf_header = _named_cookie(response, CSRF_COOKIE_NAME).lower()
    assert f"{SESSION_COOKIE_NAME}=" in session_header
    assert "max-age=0" in session_header
    assert "httponly" in session_header
    assert "samesite=lax" in session_header
    assert "path=/" in session_header
    assert "secure" not in [part.strip() for part in session_header.split(";")]
    assert f"{CSRF_COOKIE_NAME}=" in csrf_header
    assert "max-age=0" in csrf_header
    assert "httponly" not in [part.strip() for part in csrf_header.split(";")]

    with pytest.raises(SessionAuthenticationError):
        resolve_active_session(db_session, raw_token)


def test_unknown_expired_or_revoked_token_cannot_logout(
    logout_client: TestClient,
    db_session: Session,
    logout_settings: Settings,
) -> None:
    unknown = _logout(logout_client, "unknown-session-token", "v1.0.deadbeef.00")
    assert unknown.status_code == 401
    assert unknown.json() == {"detail": NOT_AUTHENTICATED_DETAIL}
    assert "max-age=0" not in _cookie_header(unknown).lower()
    _assert_no_secret_leak(unknown.text, "unknown-session-token")

    expired_token, expired_record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=60,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    expired_id = expired_record.id
    expired_hash = expired_record.token_hash
    db_session.commit()
    expired = _logout(
        logout_client,
        expired_token,
        _csrf_token_for(expired_id, logout_settings),
    )
    assert expired.status_code == 401
    assert expired.json() == {"detail": NOT_AUTHENTICATED_DETAIL}
    stored_expired = db_session.get(UserSession, expired_id)
    assert stored_expired is not None
    assert stored_expired.revoked_at is None
    _assert_no_secret_leak(expired.text, expired_token, expired_hash)

    revoked_token, revoked_record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    revoked_id = revoked_record.id
    revoked_hash = revoked_record.token_hash
    revoked_record.revoked_at = _NOW
    db_session.flush()
    db_session.commit()
    revoked = _logout(
        logout_client,
        revoked_token,
        _csrf_token_for(revoked_id, logout_settings),
    )
    assert revoked.status_code == 401
    assert revoked.json() == {"detail": NOT_AUTHENTICATED_DETAIL}
    stored_revoked = db_session.get(UserSession, revoked_id)
    assert stored_revoked is not None
    assert stored_revoked.revoked_at is not None
    _assert_no_secret_leak(revoked.text, revoked_token, revoked_hash)


def test_logout_does_not_revoke_other_sessions(
    logout_client: TestClient,
    db_session: Session,
    logout_settings: Settings,
) -> None:
    current_token, current = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    other_token, other = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )

    response = _logout(
        logout_client,
        current_token,
        _csrf_token_for(current.id, logout_settings),
    )

    assert response.status_code == 200
    db_session.refresh(current)
    db_session.refresh(other)
    assert current.revoked_at is not None
    assert other.revoked_at is None
    resolve_active_session(db_session, other_token, now=_NOW)


def test_commit_failure_does_not_clear_cookie_or_revoke(
    db_session: Session,
    logout_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    session_id = record.id
    token_hash = record.token_hash
    db_session.commit()

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
    app.dependency_overrides[get_settings] = lambda: logout_settings
    try:
        client = TestClient(app, raise_server_exceptions=False)
        csrf_token = _csrf_token_for(session_id, logout_settings)
        client.cookies.set(SESSION_COOKIE_NAME, raw_token)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        response = client.post(
            "/api/v1/auth/logout",
            headers={"X-CSRF-Token": csrf_token},
        )
    finally:
        app.dependency_overrides.pop(get_settings, None)
        app.dependency_overrides.pop(get_db, None)

    body = response.text
    assert response.status_code == 500
    assert response.text.strip() != '{"status":"ok"}'
    header = _cookie_header(response).lower()
    assert SESSION_COOKIE_NAME not in header
    assert "max-age=0" not in header
    _assert_no_secret_leak(body, raw_token, token_hash)
    assert rollback_invoked is True
    stored = db_session.get(UserSession, session_id)
    assert stored is not None
    assert stored.revoked_at is None


def test_logout_rejects_missing_csrf_without_revoking(
    logout_client: TestClient,
    db_session: Session,
) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    session_id = record.id
    db_session.commit()

    response = _logout(logout_client, raw_token)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    stored = db_session.get(UserSession, session_id)
    assert stored is not None
    assert stored.revoked_at is None
    assert "max-age=0" not in _cookie_header(response).lower()


def test_logout_rejects_invalid_csrf_without_revoking(
    logout_client: TestClient,
    db_session: Session,
    logout_settings: Settings,
) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    _other_token, other = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    session_id = record.id
    other_csrf = _csrf_token_for(other.id, logout_settings)
    db_session.commit()

    response = _logout(logout_client, raw_token, other_csrf)

    assert response.status_code == 403
    assert response.json() == {"detail": CSRF_FAILURE_DETAIL}
    stored = db_session.get(UserSession, session_id)
    assert stored is not None
    assert stored.revoked_at is None
