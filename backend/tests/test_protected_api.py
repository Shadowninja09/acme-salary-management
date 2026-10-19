from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import NOT_AUTHENTICATED_DETAIL
from app.services.sessions import SESSION_COOKIE_NAME, issue_hr_manager_session

EMPLOYEE_PAYLOAD = {
    "employee_code": "EMP-000001",
    "full_name": "Ada Lovelace",
    "country": "United Kingdom",
    "department": "Engineering",
    "job_title": "Analyst",
    "employment_status": "ACTIVE",
}

_PROTECTED_REQUESTS = (
    ("POST", "/api/v1/employees", {"json": EMPLOYEE_PAYLOAD}),
    ("GET", "/api/v1/employees", {"params": {"limit": 1, "offset": 0}}),
    ("GET", "/api/v1/employees/1", {}),
)


def _request(client: TestClient, method: str, path: str, kwargs: dict):
    return client.request(method, path, **kwargs)


def _assert_unauthenticated(response, *secrets: str) -> None:
    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}
    body = response.text
    for secret in secrets:
        assert secret not in body
    assert "token_hash" not in body.lower()
    assert "revoked" not in body.lower()
    assert "expired" not in body.lower()


@pytest.mark.parametrize("method,path,kwargs", _PROTECTED_REQUESTS)
def test_unauthenticated_employee_routes_return_401(
    api_client: TestClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    _assert_unauthenticated(_request(api_client, method, path, kwargs))


@pytest.mark.parametrize("method,path,kwargs", _PROTECTED_REQUESTS)
def test_unknown_session_cannot_access_employee_routes(
    api_client: TestClient,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    unknown = "unknown-session-token"
    api_client.cookies.set(SESSION_COOKIE_NAME, unknown)
    _assert_unauthenticated(_request(api_client, method, path, kwargs), unknown)


@pytest.mark.parametrize("method,path,kwargs", _PROTECTED_REQUESTS)
def test_expired_session_cannot_access_employee_routes(
    api_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=60,
        now=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    api_client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    _assert_unauthenticated(
        _request(api_client, method, path, kwargs),
        raw_token,
        record.token_hash,
    )


@pytest.mark.parametrize("method,path,kwargs", _PROTECTED_REQUESTS)
def test_revoked_session_cannot_access_employee_routes(
    api_client: TestClient,
    db_session: Session,
    method: str,
    path: str,
    kwargs: dict,
) -> None:
    now = datetime.now(timezone.utc)
    raw_token, record = issue_hr_manager_session(
        db_session,
        lifetime_seconds=3600,
        now=now,
    )
    record.revoked_at = now
    db_session.flush()
    api_client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    _assert_unauthenticated(
        _request(api_client, method, path, kwargs),
        raw_token,
        record.token_hash,
    )


def test_health_remains_public_without_session(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_logout_still_requires_an_active_session(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/auth/logout")
    _assert_unauthenticated(response)


def test_valid_session_can_use_employee_routes(
    authenticated_client: TestClient,
) -> None:
    created = authenticated_client.post("/api/v1/employees", json=EMPLOYEE_PAYLOAD)
    assert created.status_code == 201
    employee_id = created.json()["id"]
    assert SESSION_COOKIE_NAME not in str(created.json()).lower()

    listed = authenticated_client.get("/api/v1/employees")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    fetched = authenticated_client.get(f"/api/v1/employees/{employee_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == employee_id
