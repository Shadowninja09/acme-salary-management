from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.schemas.auth import LoginRequest, LoginResponse
from app.services.auth import verify_hr_manager_credentials
from app.services.sessions import issue_hr_manager_session

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

SESSION_COOKIE_NAME = "acme_session"
INVALID_CREDENTIALS_DETAIL = "Invalid credentials"
SESSION_CREATE_FAILURE_DETAIL = "Unable to create session"


@router.post("/login", response_model=LoginResponse)
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
        raw_token, _record = issue_hr_manager_session(
            db,
            lifetime_seconds=settings.session_max_age_seconds,
        )
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=SESSION_CREATE_FAILURE_DETAIL,
        ) from exc

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        samesite="lax",
        path="/",
        max_age=settings.session_max_age_seconds,
        secure=settings.session_cookie_secure,
    )
    return LoginResponse(status="ok")
