from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.auth import SESSION_COOKIE_NAME
from app.db.session import get_db
from app.services.sessions import (
    AuthenticatedSession,
    SessionAuthenticationError,
    resolve_active_session,
)

NOT_AUTHENTICATED_DETAIL = "Not authenticated"


def require_authenticated_session(
    db: Session = Depends(get_db),
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> AuthenticatedSession:
    try:
        return resolve_active_session(db, session_token)
    except SessionAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from exc
