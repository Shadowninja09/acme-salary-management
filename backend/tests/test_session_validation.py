from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import NOT_AUTHENTICATED_DETAIL, require_authenticated_session
from app.models.user_session import UserSession
from app.services.sessions import (
    SessionAuthenticationError,
    hash_session_token,
    issue_hr_manager_session,
    resolve_active_session,
)

_NOW = datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc)


def _assert_generic_auth_failure(exc: BaseException) -> None:
    detail = getattr(exc, "detail", str(exc))
    message = str(exc)
    assert "token" not in message.lower()
    assert "hash" not in message.lower()
    assert "revoked" not in str(detail).lower()
    assert "expired" not in str(detail).lower()
    assert "unknown" not in str(detail).lower()


def test_missing_cookie_is_rejected(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_session(db=db_session, session_token=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == NOT_AUTHENTICATED_DETAIL
    _assert_generic_auth_failure(exc_info.value)


def test_empty_cookie_is_rejected(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_session(db=db_session, session_token="")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == NOT_AUTHENTICATED_DETAIL
    _assert_generic_auth_failure(exc_info.value)


def test_unknown_token_is_rejected(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_session(
            db=db_session,
            session_token="unknown-session-token",
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == NOT_AUTHENTICATED_DETAIL
    _assert_generic_auth_failure(exc_info.value)


def test_valid_active_session_is_accepted(db_session: Session) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )

    authenticated = require_authenticated_session(
        db=db_session,
        session_token=raw_token,
    )

    assert authenticated.id == record.id
    assert authenticated.expires_at == record.expires_at


def test_expired_session_is_rejected(db_session: Session) -> None:
    raw_token, _record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=60,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_session(db=db_session, session_token=raw_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == NOT_AUTHENTICATED_DETAIL
    _assert_generic_auth_failure(exc_info.value)


def test_revoked_session_is_rejected(db_session: Session) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )
    record.revoked_at = _NOW
    db_session.flush()

    with pytest.raises(HTTPException) as exc_info:
        require_authenticated_session(db=db_session, session_token=raw_token)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == NOT_AUTHENTICATED_DETAIL
    _assert_generic_auth_failure(exc_info.value)


def test_token_hashing_matches_login_issuance(db_session: Session) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=_NOW,
    )

    stored = db_session.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(raw_token)
        )
    )
    authenticated = resolve_active_session(db_session, raw_token, now=_NOW)

    assert stored is not None
    assert stored.id == record.id
    assert stored.token_hash == hash_session_token(raw_token)
    assert stored.token_hash != raw_token
    assert authenticated.id == record.id


def test_expiry_at_current_time_is_expired(db_session: Session) -> None:
    raw_token, _record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=0,
        now=_NOW,
    )

    with pytest.raises(SessionAuthenticationError):
        resolve_active_session(db_session, raw_token, now=_NOW)
