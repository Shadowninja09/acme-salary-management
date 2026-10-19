from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.services.csrf import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    login_origin_is_trusted,
    submitted_csrf_is_valid,
)
from app.services.sessions import (
    SESSION_COOKIE_NAME,
    AuthenticatedSession,
    SessionAuthenticationError,
    resolve_active_session,
)

NOT_AUTHENTICATED_DETAIL = "Not authenticated"
CSRF_FAILURE_DETAIL = "CSRF validation failed"


def require_authenticated_session(
    db: Session = Depends(get_db, scope="function"),
    session_token: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> AuthenticatedSession:
    try:
        return resolve_active_session(db, session_token)
    except SessionAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from exc


def require_csrf_token(
    authenticated: Annotated[AuthenticatedSession, Depends(require_authenticated_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE_NAME)] = None,
    csrf_header: Annotated[str | None, Header(alias=CSRF_HEADER_NAME)] = None,
) -> AuthenticatedSession:
    if not submitted_csrf_is_valid(
        cookie=csrf_cookie,
        header=csrf_header,
        session_id=authenticated.id,
        secret=settings.csrf_signing_secret.get_secret_value(),
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CSRF_FAILURE_DETAIL,
        )
    return authenticated


def require_trusted_login_origin(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> None:
    if not login_origin_is_trusted(request, settings.csrf_trusted_origins):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=CSRF_FAILURE_DETAIL,
        )
