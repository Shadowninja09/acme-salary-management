import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_session import UserSession


class SessionAuthenticationError(Exception):
    pass


@dataclass(frozen=True)
class AuthenticatedSession:
    id: int
    expires_at: datetime


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def issue_hr_manager_session(
    db: Session,
    *,
    lifetime_seconds: int,
    now: datetime | None = None,
) -> tuple[str, UserSession]:
    issued_at = now if now is not None else datetime.now(timezone.utc)
    raw_token = generate_session_token()
    record = UserSession(
        token_hash=hash_session_token(raw_token),
        expires_at=issued_at + timedelta(seconds=lifetime_seconds),
    )
    db.add(record)
    db.flush()
    db.refresh(record)
    return raw_token, record


def resolve_active_session(
    db: Session,
    raw_token: str | None,
    *,
    now: datetime | None = None,
) -> AuthenticatedSession:
    if raw_token is None or raw_token == "":
        raise SessionAuthenticationError

    current = now if now is not None else datetime.now(timezone.utc)
    record = db.scalar(
        select(UserSession).where(
            UserSession.token_hash == hash_session_token(raw_token)
        )
    )
    if (
        record is None
        or record.revoked_at is not None
        or record.expires_at <= current
    ):
        raise SessionAuthenticationError

    return AuthenticatedSession(id=record.id, expires_at=record.expires_at)
