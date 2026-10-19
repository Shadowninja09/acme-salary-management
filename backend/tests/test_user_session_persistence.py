from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import UserSession

_TOKEN_HASH = "a" * 64


def test_user_session_table_and_columns() -> None:
    table = UserSession.__table__
    assert table.name == "user_sessions"
    assert set(table.c.keys()) == {
        "id",
        "token_hash",
        "created_at",
        "expires_at",
        "revoked_at",
    }
    assert table.c.token_hash.nullable is False
    assert table.c.created_at.nullable is False
    assert table.c.expires_at.nullable is False
    assert table.c.revoked_at.nullable is True
    unique_names = {constraint.name for constraint in table.constraints}
    assert "uq_user_sessions_token_hash" in unique_names


def test_user_sessions_migration_applied(migrated_test_engine: Engine) -> None:
    inspector = inspect(migrated_test_engine)
    assert "user_sessions" in inspector.get_table_names()
    columns = {column["name"] for column in inspector.get_columns("user_sessions")}
    assert columns == {
        "id",
        "token_hash",
        "created_at",
        "expires_at",
        "revoked_at",
    }
    unique = inspector.get_unique_constraints("user_sessions")
    assert any(item["name"] == "uq_user_sessions_token_hash" for item in unique)


def test_insert_and_read_user_session(db_session: Session) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    session_row = UserSession(token_hash=_TOKEN_HASH, expires_at=expires_at)
    db_session.add(session_row)
    db_session.flush()
    db_session.refresh(session_row)

    stored = db_session.get(UserSession, session_row.id)
    assert stored is not None
    assert stored.token_hash == _TOKEN_HASH
    assert stored.expires_at is not None
    assert stored.revoked_at is None
    assert stored.created_at is not None
    assert stored.created_at.tzinfo is not None


def test_duplicate_token_hash_is_rejected(db_session: Session) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(UserSession(token_hash=_TOKEN_HASH, expires_at=expires_at))
    db_session.flush()

    db_session.add(
        UserSession(
            token_hash=_TOKEN_HASH,
            expires_at=expires_at + timedelta(hours=1),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_unique_constraint_exists_in_database(db_session: Session) -> None:
    result = db_session.execute(
        text(
            """
            SELECT 1
            FROM pg_constraint
            WHERE conname = 'uq_user_sessions_token_hash'
            """
        )
    )
    assert result.scalar() == 1
