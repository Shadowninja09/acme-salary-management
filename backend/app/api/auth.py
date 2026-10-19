from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import (
    NOT_AUTHENTICATED_DETAIL,
    require_csrf_token,
    require_trusted_login_origin,
)
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import verify_hr_manager_credentials
from app.services.csrf import CSRF_COOKIE_NAME, issue_csrf_token
from app.services.sessions import (
    SESSION_COOKIE_NAME,
    AuthenticatedSession,
    SessionAuthenticationError,
    issue_hr_manager_session,
    revoke_user_session,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

INVALID_CREDENTIALS_DETAIL = "Invalid credentials"
SESSION_CREATE_FAILURE_DETAIL = "Unable to create session"
SESSION_REVOKE_FAILURE_DETAIL = "Unable to revoke session"


@router.post(
    "/login",
    response_model=LoginResponse,
    dependencies=[Depends(require_trusted_login_origin)],
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db, scope="function"),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    if not verify_hr_manager_credentials(payload.username, payload.password, settings):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS_DETAIL,
        )

    try:
        raw_token, record = issue_hr_manager_session(
            db,
            lifetime_seconds=settings.session_max_age_seconds,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SESSION_CREATE_FAILURE_DETAIL,
        ) from exc

    csrf_token = issue_csrf_token(
        session_id=record.id,
        secret=settings.csrf_signing_secret.get_secret_value(),
    )
    _set_session_cookie(response, raw_token, settings)
    _set_csrf_cookie(response, csrf_token, settings)
    return LoginResponse(status="ok")


@router.post("/logout", response_model=LoginResponse)
def logout(
    response: Response,
    authenticated: AuthenticatedSession = Depends(require_csrf_token),
    db: Session = Depends(get_db, scope="function"),
    settings: Settings = Depends(get_settings),
) -> LoginResponse:
    try:
        revoke_user_session(db, authenticated.id)
    except SessionAuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=NOT_AUTHENTICATED_DETAIL,
        ) from exc
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SESSION_REVOKE_FAILURE_DETAIL,
        ) from exc

    _clear_session_cookie(response, settings)
    _clear_csrf_cookie(response, settings)
    return LoginResponse(status="ok")


def _set_session_cookie(response: Response, raw_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.session_max_age_seconds,
        secure=settings.session_cookie_secure,
    )


def _set_csrf_cookie(response: Response, csrf_token: str, settings: Settings) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        path="/",
        max_age=settings.session_max_age_seconds,
        secure=settings.session_cookie_secure,
    )


def _clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )


def _clear_csrf_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=CSRF_COOKIE_NAME,
        path="/",
        httponly=False,
        samesite="lax",
        secure=settings.session_cookie_secure,
    )
