from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import CSRF_FAILURE_DETAIL, NOT_AUTHENTICATED_DETAIL
from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.models import (
    AuditAction,
    Employee,
    EmploymentStatus,
    SalaryAuditLog,
    SalaryRecord,
)
from app.schemas.employee import EmployeeCreate
from app.services.csrf import CSRF_COOKIE_NAME, issue_csrf_token
from app.services.employee import create_employee
from app.services.sessions import SESSION_COOKIE_NAME, issue_hr_manager_session

EMPLOYEE_PAYLOAD = {
    "employee_code": "EMP-000001",
    "full_name": "Ada Lovelace",
    "country": "United Kingdom",
    "department": "Engineering",
    "job_title": "Analyst",
    "employment_status": "ACTIVE",
}

SALARY_PAYLOAD = {
    "amount": "1234.56",
    "currency": "INR",
    "pay_frequency": "MONTHLY",
    "effective_from": "2026-01-01",
}


def _create_employee(client: TestClient, **overrides: object) -> int:
    payload = {**EMPLOYEE_PAYLOAD, **overrides}
    response = client.post("/api/v1/employees", json=payload)
    assert response.status_code == 201
    return int(response.json()["id"])


def _salary_count(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(SalaryRecord)) or 0)


def _audit_count(db_session: Session) -> int:
    return int(db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) or 0)


def test_create_salary_returns_201_and_expected_fields(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )

    assert response.status_code == 201
    body = response.json()
    assert body["employee_id"] == employee_id
    assert body["amount"] == "1234.56"
    assert body["currency"] == "INR"
    assert body["pay_frequency"] == "MONTHLY"
    assert body["effective_from"] == "2026-01-01"
    assert body["id"] is not None
    assert SESSION_COOKIE_NAME not in str(body).lower()
    assert get_settings().csrf_signing_secret.get_secret_value() not in response.text


def test_create_salary_persists_create_audit_with_configured_identity(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )

    assert response.status_code == 201
    salary_id = response.json()["id"]
    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == salary_id)
        ).all()
    )
    assert len(logs) == 1
    log = logs[0]
    assert log.action == AuditAction.CREATE.value
    assert log.old_values is None
    assert log.new_values == {
        "amount": "1234.56",
        "currency": "INR",
        "pay_frequency": "MONTHLY",
        "effective_from": "2026-01-01",
    }
    assert log.reason is None
    assert log.changed_by == get_settings().hr_manager_identity


def test_unknown_employee_returns_404_and_creates_no_records(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    response = authenticated_client.post(
        "/api/v1/employees/999999999/salaries",
        json=SALARY_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}
    assert _salary_count(db_session) == 0
    assert _audit_count(db_session) == 0


def test_duplicate_effective_date_returns_409(authenticated_client: TestClient) -> None:
    employee_id = _create_employee(authenticated_client)
    first = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert first.status_code == 201

    duplicate = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "amount": "1500.00"},
    )

    assert duplicate.status_code == 409
    assert duplicate.json() == {
        "detail": "Salary already exists for this effective date"
    }


def test_same_effective_date_allowed_for_different_employees(
    authenticated_client: TestClient,
) -> None:
    first_id = _create_employee(authenticated_client, employee_code="EMP-000001")
    second_id = _create_employee(authenticated_client, employee_code="EMP-000002")

    first = authenticated_client.post(
        f"/api/v1/employees/{first_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    second = authenticated_client.post(
        f"/api/v1/employees/{second_id}/salaries",
        json=SALARY_PAYLOAD,
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]


@pytest.mark.parametrize(
    "payload",
    [
        {**SALARY_PAYLOAD, "currency": "JPY"},
        {**SALARY_PAYLOAD, "pay_frequency": "WEEKLY"},
        {k: v for k, v in SALARY_PAYLOAD.items() if k != "amount"},
        {**SALARY_PAYLOAD, "amount": "0"},
        {**SALARY_PAYLOAD, "amount": "-1.00"},
        {**SALARY_PAYLOAD, "amount": "1.239"},
        {**SALARY_PAYLOAD, "amount": 1234.56},
        {**SALARY_PAYLOAD, "amount": "not-a-decimal"},
    ],
)
def test_invalid_salary_payload_returns_422(
    authenticated_client: TestClient,
    db_session: Session,
    payload: dict,
) -> None:
    employee_id = _create_employee(authenticated_client)
    before_salaries = _salary_count(db_session)
    before_audits = _audit_count(db_session)

    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=payload,
    )

    assert response.status_code == 422
    assert "IntegrityError" not in response.text
    assert _salary_count(db_session) == before_salaries
    assert _audit_count(db_session) == before_audits


def test_unauthenticated_create_salary_returns_401(
    api_client: TestClient,
    db_session: Session,
) -> None:
    response = api_client.post("/api/v1/employees/1/salaries", json=SALARY_PAYLOAD)

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}
    assert _salary_count(db_session) == 0


def test_missing_or_invalid_csrf_on_create_salary_returns_403(
    api_client: TestClient,
    db_session: Session,
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    path = f"/api/v1/employees/{employee_id}/salaries"

    missing_header = api_client.post(path, json=SALARY_PAYLOAD)
    mismatched = api_client.post(
        path,
        json=SALARY_PAYLOAD,
        headers={"X-CSRF-Token": "v1.1.deadbeef.00"},
    )

    assert missing_header.status_code == 403
    assert missing_header.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert mismatched.status_code == 403
    assert mismatched.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert _salary_count(db_session) == 0


def test_audit_failure_does_not_leave_committed_salary(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    employee = create_employee(
        db_session,
        EmployeeCreate(
            employee_code="EMP-000001",
            full_name="Ada Lovelace",
            country="United Kingdom",
            department="Engineering",
            job_title="Analyst",
            employment_status=EmploymentStatus.ACTIVE,
        ),
    )
    employee_id = employee.id
    raw_token, record = issue_hr_manager_session(db_session, lifetime_seconds=3600)
    csrf_token = issue_csrf_token(
        session_id=record.id,
        secret=get_settings().csrf_signing_secret.get_secret_value(),
    )
    db_session.commit()

    def fail_audit(*args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT INTO salary_audit_logs", {}, Exception())

    monkeypatch.setattr("app.services.salary._write_salary_audit", fail_audit)

    def override_get_db() -> Generator[Session, None, None]:
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise

    app.dependency_overrides[get_db] = override_get_db
    try:
        client = TestClient(app, raise_server_exceptions=False)
        client.cookies.set(SESSION_COOKIE_NAME, raw_token)
        client.cookies.set(CSRF_COOKIE_NAME, csrf_token)
        response = client.post(
            f"/api/v1/employees/{employee_id}/salaries",
            json=SALARY_PAYLOAD,
            headers={"X-CSRF-Token": csrf_token},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert "IntegrityError" not in response.text
    assert "salary_audit_logs" not in response.text.lower()
    stored = db_session.get(Employee, employee_id)
    assert stored is not None
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SalaryRecord)
            .where(SalaryRecord.employee_id == employee_id)
        )
        == 0
    )
    assert db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) == 0
