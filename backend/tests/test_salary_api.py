from collections.abc import Generator
from datetime import date, datetime
from decimal import Decimal

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
    Currency,
    Employee,
    EmploymentStatus,
    PayFrequency,
    SalaryAuditLog,
    SalaryRecord,
)
from app.schemas.employee import EmployeeCreate
from app.schemas.salary import SalaryCreate
from app.services.csrf import CSRF_COOKIE_NAME, issue_csrf_token
from app.services.employee import create_employee
from app.services.salary import create_salary
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
    "currency": "GBP",
    "pay_frequency": "MONTHLY",
    "effective_from": "2026-01-01",
}

CORRECTION_PAYLOAD = {
    "amount": "2000.00",
    "currency": "GBP",
    "pay_frequency": "ANNUAL",
    "effective_from": "2026-02-01",
    "reason": "Corrected recorded amount",
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
    assert body["currency"] == "GBP"
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
        "currency": "GBP",
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


def test_list_salaries_returns_all_records_newest_effective_date_first(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    older = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    newer = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "amount": "2000.00", "effective_from": "2026-06-01"},
    )
    assert older.status_code == 201
    assert newer.status_code == 201

    response = authenticated_client.get(f"/api/v1/employees/{employee_id}/salaries")

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body] == [newer.json()["id"], older.json()["id"]]
    assert [item["effective_from"] for item in body] == ["2026-06-01", "2026-01-01"]
    assert body[0]["amount"] == "2000.00"
    assert body[1]["amount"] == "1234.56"
    assert body[0]["employee_id"] == employee_id
    assert body[0]["currency"] == "GBP"
    for item in body:
        assert set(item.keys()) == {
            "id",
            "employee_id",
            "amount",
            "currency",
            "pay_frequency",
            "effective_from",
        }
        assert isinstance(item["amount"], str)


def test_list_salaries_returns_single_record(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201

    response = authenticated_client.get(f"/api/v1/employees/{employee_id}/salaries")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == created.json()["id"]
    assert body[0]["amount"] == "1234.56"
    assert isinstance(body[0]["amount"], str)


def test_list_salaries_empty_for_employee_without_records(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.get(f"/api/v1/employees/{employee_id}/salaries")

    assert response.status_code == 200
    assert response.json() == []


def test_list_salaries_unknown_employee_returns_404(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/employees/999999999/salaries")

    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}


def test_list_salaries_unauthenticated_returns_401(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/employees/1/salaries")

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_list_salary_corrections_returns_update_audit(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]
    corrected = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json=CORRECTION_PAYLOAD,
    )
    assert corrected.status_code == 200

    stored = db_session.scalars(
        select(SalaryAuditLog).where(
            SalaryAuditLog.salary_record_id == salary_id,
            SalaryAuditLog.action == AuditAction.UPDATE.value,
        )
    ).one()

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salary-corrections"
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    item = body[0]
    assert item["salary_record_id"] == salary_id
    assert item["changed_by"] == get_settings().hr_manager_identity
    assert item["reason"] == "Corrected recorded amount"
    assert item["old_values"] == {
        "amount": "1234.56",
        "currency": "GBP",
        "pay_frequency": "MONTHLY",
        "effective_from": "2026-01-01",
    }
    assert item["new_values"] == {
        "amount": "2000.00",
        "currency": "GBP",
        "pay_frequency": "ANNUAL",
        "effective_from": "2026-02-01",
    }
    assert datetime.fromisoformat(item["changed_at"]) == stored.changed_at
    assert set(item.keys()) == {
        "salary_record_id",
        "changed_at",
        "changed_by",
        "reason",
        "old_values",
        "new_values",
    }


def test_list_salary_corrections_empty_when_employee_has_no_updates(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salary-corrections"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_list_salary_corrections_unknown_employee_returns_404(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get("/api/v1/employees/999999999/salary-corrections")

    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}


def test_list_salary_corrections_unauthenticated_returns_401(
    api_client: TestClient,
) -> None:
    response = api_client.get("/api/v1/employees/1/salary-corrections")

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_list_salary_corrections_does_not_require_csrf_header(
    api_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = create_employee(
        db_session,
        EmployeeCreate(
            employee_code="EMP-000001",
            full_name="Ada Lovelace",
            country="United Kingdom",
            department="Engineering",
            job_title="Analyst",
            employment_status=EmploymentStatus.ACTIVE,
        ),
    ).id
    raw_token, _record = issue_hr_manager_session(db_session, lifetime_seconds=3600)
    db_session.commit()
    api_client.cookies.set(SESSION_COOKIE_NAME, raw_token)
    try:
        response = api_client.get(
            f"/api/v1/employees/{employee_id}/salary-corrections"
        )
    finally:
        api_client.cookies.delete(SESSION_COOKIE_NAME)

    assert response.status_code == 200
    assert response.json() == []
    assert "X-CSRF-Token" not in (response.request.headers or {})


def test_list_salary_corrections_omits_create_audits(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salary-corrections"
    )

    assert response.status_code == 200
    assert response.json() == []


def test_applicable_salary_returns_latest_on_or_before_date(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    january = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    june = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "amount": "2000.00", "effective_from": "2026-06-01"},
    )
    assert january.status_code == 201
    assert june.status_code == 201

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params={"date": "2026-03-15"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == january.json()["id"]
    assert body["employee_id"] == employee_id
    assert body["amount"] == "1234.56"
    assert isinstance(body["amount"], str)
    assert body["currency"] == "GBP"
    assert body["pay_frequency"] == "MONTHLY"
    assert body["effective_from"] == "2026-01-01"
    assert set(body.keys()) == {
        "id",
        "employee_id",
        "amount",
        "currency",
        "pay_frequency",
        "effective_from",
    }


def test_applicable_salary_does_not_return_future_dated_record(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    january = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    future = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "amount": "3000.00", "effective_from": "2027-01-01"},
    )
    assert january.status_code == 201
    assert future.status_code == 201

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params={"date": "2026-10-19"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == january.json()["id"]
    assert body["id"] != future.json()["id"]
    assert body["effective_from"] == "2026-01-01"


def test_applicable_salary_includes_record_effective_on_requested_date(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params={"date": "2026-01-01"},
    )

    assert response.status_code == 200
    assert response.json()["id"] == created.json()["id"]
    assert response.json()["amount"] == "1234.56"
    assert isinstance(response.json()["amount"], str)


def test_applicable_salary_null_when_employee_has_no_records(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params={"date": "2026-10-19"},
    )

    assert response.status_code == 200
    assert response.json() is None


def test_applicable_salary_null_when_only_salary_is_in_the_future(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "effective_from": "2027-01-01"},
    )
    assert created.status_code == 201

    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params={"date": "2026-10-19"},
    )

    assert response.status_code == 200
    assert response.json() is None


def test_applicable_salary_unknown_employee_returns_404(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.get(
        "/api/v1/employees/999999999/salaries/as-of",
        params={"date": "2026-10-19"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}


@pytest.mark.parametrize(
    "params",
    [{}, {"date": "not-a-date"}, {"date": "2026-13-40"}],
)
def test_applicable_salary_missing_or_invalid_date_returns_422(
    authenticated_client: TestClient,
    params: dict,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.get(
        f"/api/v1/employees/{employee_id}/salaries/as-of",
        params=params,
    )

    assert response.status_code == 422


def test_applicable_salary_unauthenticated_returns_401(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/employees/1/salaries/as-of",
        params={"date": "2026-10-19"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_correct_salary_updates_existing_record_and_keeps_id(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json=CORRECTION_PAYLOAD,
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == salary_id
    assert body["employee_id"] == employee_id
    assert body["amount"] == "2000.00"
    assert isinstance(body["amount"], str)
    assert body["currency"] == "GBP"
    assert body["pay_frequency"] == "ANNUAL"
    assert body["effective_from"] == "2026-02-01"
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert stored.id == salary_id
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SalaryRecord)
            .where(SalaryRecord.employee_id == employee_id)
        )
        == 1
    )


def test_correct_salary_keeps_existing_effective_date(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json={
            **CORRECTION_PAYLOAD,
            "currency": "GBP",
            "pay_frequency": "MONTHLY",
            "effective_from": "2026-01-01",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == salary_id
    assert body["employee_id"] == employee_id
    assert body["amount"] == "2000.00"
    assert isinstance(body["amount"], str)
    assert body["currency"] == "GBP"
    assert body["pay_frequency"] == "MONTHLY"
    assert body["effective_from"] == "2026-01-01"
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert stored.id == salary_id
    assert stored.effective_from.isoformat() == "2026-01-01"
    assert str(stored.amount) == "2000.00"


def test_correct_salary_writes_update_audit(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json=CORRECTION_PAYLOAD,
    )
    assert response.status_code == 200

    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == salary_id)
        ).all()
    )
    updates = [log for log in logs if log.action == AuditAction.UPDATE.value]
    assert len(logs) == 2
    assert len(updates) == 1
    log = updates[0]
    assert log.old_values == {
        "amount": "1234.56",
        "currency": "GBP",
        "pay_frequency": "MONTHLY",
        "effective_from": "2026-01-01",
    }
    assert log.new_values == {
        "amount": "2000.00",
        "currency": "GBP",
        "pay_frequency": "ANNUAL",
        "effective_from": "2026-02-01",
    }
    assert log.reason == "Corrected recorded amount"
    assert log.changed_by == get_settings().hr_manager_identity


def test_correct_salary_unknown_salary_returns_404(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/999999999",
        json=CORRECTION_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Salary not found"}


def test_correct_salary_unknown_employee_returns_404(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.patch(
        "/api/v1/employees/999999999/salaries/1",
        json=CORRECTION_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}


def test_correct_salary_mismatch_returns_404_and_does_not_modify(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    owner_id = _create_employee(authenticated_client, employee_code="EMP-000001")
    other_id = _create_employee(authenticated_client, employee_code="EMP-000002")
    created = authenticated_client.post(
        f"/api/v1/employees/{owner_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{other_id}/salaries/{salary_id}",
        json=CORRECTION_PAYLOAD,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Salary not found"}
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert stored.employee_id == owner_id
    assert str(stored.amount) == "1234.56"
    assert stored.effective_from.isoformat() == "2026-01-01"


def test_correct_salary_duplicate_effective_date_returns_409(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee(authenticated_client)
    first = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    second = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json={**SALARY_PAYLOAD, "effective_from": "2026-03-01"},
    )
    assert first.status_code == 201
    assert second.status_code == 201
    salary_id = first.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json={**CORRECTION_PAYLOAD, "effective_from": "2026-03-01"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Salary already exists for this effective date"
    }
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert stored.id == salary_id
    assert str(stored.amount) == "1234.56"
    assert stored.currency == "GBP"
    assert stored.pay_frequency == "MONTHLY"
    assert stored.effective_from.isoformat() == "2026-01-01"
    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == salary_id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].action == AuditAction.CREATE.value
    assert not any(log.action == AuditAction.UPDATE.value for log in logs)


@pytest.mark.parametrize(
    "payload",
    [
        {**CORRECTION_PAYLOAD, "currency": "JPY"},
        {**CORRECTION_PAYLOAD, "pay_frequency": "WEEKLY"},
        {**CORRECTION_PAYLOAD, "amount": "0"},
        {**CORRECTION_PAYLOAD, "amount": "-1.00"},
        {**CORRECTION_PAYLOAD, "amount": "1.239"},
        {**CORRECTION_PAYLOAD, "amount": 1234.56},
        {**CORRECTION_PAYLOAD, "amount": "not-a-decimal"},
        {**CORRECTION_PAYLOAD, "reason": ""},
        {**CORRECTION_PAYLOAD, "reason": "   "},
        {k: v for k, v in CORRECTION_PAYLOAD.items() if k != "reason"},
    ],
)
def test_correct_salary_invalid_payload_returns_422(
    authenticated_client: TestClient,
    db_session: Session,
    payload: dict,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json=payload,
    )

    assert response.status_code == 422
    assert "IntegrityError" not in response.text
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert str(stored.amount) == "1234.56"


def test_unauthenticated_correct_salary_returns_401(api_client: TestClient) -> None:
    response = api_client.patch(
        "/api/v1/employees/1/salaries/1",
        json=CORRECTION_PAYLOAD,
    )

    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


def test_missing_or_invalid_csrf_on_correct_salary_returns_403(
    api_client: TestClient,
    db_session: Session,
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee(authenticated_client)
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=SALARY_PAYLOAD,
    )
    assert created.status_code == 201
    path = f"/api/v1/employees/{employee_id}/salaries/{created.json()['id']}"

    missing_header = api_client.patch(path, json=CORRECTION_PAYLOAD)
    mismatched = api_client.patch(
        path,
        json=CORRECTION_PAYLOAD,
        headers={"X-CSRF-Token": "v1.1.deadbeef.00"},
    )

    assert missing_header.status_code == 403
    assert missing_header.json() == {"detail": CSRF_FAILURE_DETAIL}
    assert mismatched.status_code == 403
    assert mismatched.json() == {"detail": CSRF_FAILURE_DETAIL}
    stored = db_session.get(SalaryRecord, created.json()["id"])
    assert stored is not None
    assert str(stored.amount) == "1234.56"


def test_audit_failure_does_not_commit_salary_correction(
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
    record = create_salary(
        db_session,
        SalaryCreate(
            employee_id=employee.id,
            amount=Decimal("1234.56"),
            currency=Currency.GBP,
            pay_frequency=PayFrequency.MONTHLY,
            effective_from=date(2026, 1, 1),
        ),
    )
    employee_id = employee.id
    salary_id = record.id
    raw_token, session_record = issue_hr_manager_session(
        db_session, lifetime_seconds=3600
    )
    csrf_token = issue_csrf_token(
        session_id=session_record.id,
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
        response = client.patch(
            f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
            json=CORRECTION_PAYLOAD,
            headers={"X-CSRF-Token": csrf_token},
        )
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 500
    assert "IntegrityError" not in response.text
    assert "salary_audit_logs" not in response.text.lower()
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert str(stored.amount) == "1234.56"
    assert stored.currency == "GBP"
    assert stored.pay_frequency == "MONTHLY"
    assert stored.effective_from.isoformat() == "2026-01-01"
    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == salary_id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].action == AuditAction.CREATE.value
