from datetime import date
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditAction, Currency, SalaryAuditLog, SalaryRecord
from app.models.employee import EmploymentStatus
from app.models.salary import PayFrequency
from app.schemas.employee import EmployeeCreate
from app.schemas.salary import SalaryCorrection, SalaryCreate
from app.services.country_currency import (
    UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL,
    UnsupportedSalaryCurrencyForCountryError,
    normalize_country,
    permitted_currencies_for_country,
    require_currency_permitted_for_country,
)
from app.services.employee import create_employee
from app.services.salary import correct_salary, create_salary

UNKNOWN_COUNTRY_API_DETAIL = UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL


def _create_employee_via_api(client: TestClient, **overrides: object) -> int:
    payload = {
        "employee_code": "EMP-CC-API",
        "full_name": "Ada Lovelace",
        "country": "United Kingdom",
        "department": "Engineering",
        "job_title": "Analyst",
        "employment_status": "ACTIVE",
        **overrides,
    }
    response = client.post("/api/v1/employees", json=payload)
    assert response.status_code == 201
    return int(response.json()["id"])


def _salary_payload(**overrides: object) -> dict:
    payload = {
        "amount": "1234.56",
        "currency": "GBP",
        "pay_frequency": "MONTHLY",
        "effective_from": "2026-01-01",
    }
    payload.update(overrides)
    return payload


def test_normalize_country_collapses_case_and_whitespace() -> None:
    assert normalize_country("  United   KINGDOM ") == "united kingdom"
    assert normalize_country("India") == normalize_country(" india ")


def test_permitted_currencies_for_supported_countries() -> None:
    assert permitted_currencies_for_country("India") == (Currency.INR,)
    assert permitted_currencies_for_country("united states") == (Currency.USD,)
    assert permitted_currencies_for_country("United Kingdom") == (Currency.GBP,)
    assert permitted_currencies_for_country("Canada") == (Currency.CAD,)
    assert permitted_currencies_for_country("Australia") == (Currency.AUD,)
    assert permitted_currencies_for_country("Germany") == (Currency.EUR,)


def test_unknown_country_has_no_policy() -> None:
    assert permitted_currencies_for_country("France") is None
    assert permitted_currencies_for_country("   ") is None


def test_require_currency_accepts_permitted_code() -> None:
    require_currency_permitted_for_country("  germany ", "EUR")


def test_require_currency_rejects_unknown_country() -> None:
    try:
        require_currency_permitted_for_country("Atlantis", "USD")
    except UnsupportedSalaryCurrencyForCountryError as exc:
        assert exc.detail == UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL
    else:
        raise AssertionError("expected UnsupportedSalaryCurrencyForCountryError")


def test_require_currency_rejects_disallowed_code() -> None:
    try:
        require_currency_permitted_for_country("India", "USD")
    except UnsupportedSalaryCurrencyForCountryError as exc:
        assert "USD" in exc.detail
        assert "INR" in exc.detail
        assert "India" in exc.detail
    else:
        raise AssertionError("expected UnsupportedSalaryCurrencyForCountryError")


def _employee(
    db_session: Session,
    *,
    employee_code: str = "EMP-CC-001",
    country: str = "India",
):
    return create_employee(
        db_session,
        EmployeeCreate(
            employee_code=employee_code,
            full_name="Policy Tester",
            country=country,
            department="Engineering",
            job_title="Analyst",
            employment_status=EmploymentStatus.ACTIVE,
        ),
    )


def test_create_salary_accepts_permitted_currency(db_session: Session) -> None:
    employee = _employee(db_session, country="Germany")
    record = create_salary(
        db_session,
        SalaryCreate(
            employee_id=employee.id,
            amount=Decimal("100.00"),
            currency=Currency.EUR,
            pay_frequency=PayFrequency.MONTHLY,
            effective_from=date(2026, 1, 1),
        ),
    )
    assert record.currency == Currency.EUR.value


def test_create_salary_rejects_disallowed_currency_and_writes_nothing(
    db_session: Session,
) -> None:
    employee = _employee(db_session, country="India")
    try:
        create_salary(
            db_session,
            SalaryCreate(
                employee_id=employee.id,
                amount=Decimal("100.00"),
                currency=Currency.USD,
                pay_frequency=PayFrequency.MONTHLY,
                effective_from=date(2026, 1, 1),
            ),
        )
    except UnsupportedSalaryCurrencyForCountryError:
        pass
    else:
        raise AssertionError("expected UnsupportedSalaryCurrencyForCountryError")
    assert db_session.scalar(select(func.count()).select_from(SalaryRecord)) == 0
    assert db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) == 0


def test_create_salary_rejects_unknown_country_policy(db_session: Session) -> None:
    employee = _employee(db_session, country="France")
    try:
        create_salary(
            db_session,
            SalaryCreate(
                employee_id=employee.id,
                amount=Decimal("100.00"),
                currency=Currency.EUR,
                pay_frequency=PayFrequency.MONTHLY,
                effective_from=date(2026, 1, 1),
            ),
        )
    except UnsupportedSalaryCurrencyForCountryError as exc:
        assert exc.detail == UNKNOWN_COUNTRY_CURRENCY_POLICY_DETAIL
    else:
        raise AssertionError("expected UnsupportedSalaryCurrencyForCountryError")


def test_create_salary_uses_employee_country_from_database(
    db_session: Session,
) -> None:
    employee = _employee(db_session, country="Canada")
    record = create_salary(
        db_session,
        SalaryCreate(
            employee_id=employee.id,
            amount=Decimal("100.00"),
            currency=Currency.CAD,
            pay_frequency=PayFrequency.ANNUAL,
            effective_from=date(2026, 1, 1),
        ),
    )
    assert record.currency == Currency.CAD.value


def test_correct_salary_rejects_new_disallowed_currency(
    db_session: Session,
) -> None:
    employee = _employee(db_session, country="Australia")
    original = create_salary(
        db_session,
        SalaryCreate(
            employee_id=employee.id,
            amount=Decimal("100.00"),
            currency=Currency.AUD,
            pay_frequency=PayFrequency.MONTHLY,
            effective_from=date(2026, 1, 1),
        ),
    )
    try:
        correct_salary(
            db_session,
            employee.id,
            original.id,
            SalaryCorrection(
                amount=Decimal("120.00"),
                currency=Currency.USD,
                pay_frequency=PayFrequency.MONTHLY,
                effective_from=date(2026, 1, 1),
                reason="Wrong currency",
            ),
        )
    except UnsupportedSalaryCurrencyForCountryError:
        pass
    else:
        raise AssertionError("expected UnsupportedSalaryCurrencyForCountryError")
    stored = db_session.get(SalaryRecord, original.id)
    assert stored is not None
    assert stored.currency == Currency.AUD.value
    assert stored.amount == Decimal("100.00")
    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == original.id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].action == AuditAction.CREATE.value


def test_correct_salary_keeps_legacy_currency_without_rewrite(
    db_session: Session,
) -> None:
    employee = _employee(db_session, country="United Kingdom")
    legacy = SalaryRecord(
        employee_id=employee.id,
        amount=Decimal("100.00"),
        currency=Currency.INR.value,
        pay_frequency=PayFrequency.MONTHLY.value,
        effective_from=date(2026, 1, 1),
    )
    db_session.add(legacy)
    db_session.flush()
    db_session.refresh(legacy)

    updated = correct_salary(
        db_session,
        employee.id,
        legacy.id,
        SalaryCorrection(
            amount=Decimal("150.00"),
            currency=Currency.INR,
            pay_frequency=PayFrequency.MONTHLY,
            effective_from=date(2026, 1, 1),
            reason="Corrected amount only",
        ),
    )
    assert updated.currency == Currency.INR.value
    assert updated.amount == Decimal("150.00")


def test_api_create_valid_country_currency(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee_via_api(
        authenticated_client,
        employee_code="EMP-CC-OK",
        country="India",
    )
    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=_salary_payload(currency="INR"),
    )
    assert response.status_code == 201
    assert response.json()["currency"] == "INR"


def test_api_create_invalid_country_currency_returns_422_and_writes_nothing(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee_via_api(
        authenticated_client,
        employee_code="EMP-CC-BAD",
        country="India",
    )
    before_salaries = int(
        db_session.scalar(select(func.count()).select_from(SalaryRecord)) or 0
    )
    before_audits = int(
        db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) or 0
    )

    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=_salary_payload(currency="USD"),
    )

    assert response.status_code == 422
    assert response.json()["detail"].startswith("Currency USD is not permitted for India.")
    assert int(db_session.scalar(select(func.count()).select_from(SalaryRecord)) or 0) == before_salaries
    assert int(db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) or 0) == before_audits


def test_api_create_unknown_country_policy_returns_422(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee_via_api(
        authenticated_client,
        employee_code="EMP-CC-UNK",
        country="France",
    )
    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=_salary_payload(currency="EUR"),
    )
    assert response.status_code == 422
    assert response.json() == {"detail": UNKNOWN_COUNTRY_API_DETAIL}


def test_api_create_normalizes_country_whitespace_and_case(
    authenticated_client: TestClient,
) -> None:
    employee_id = _create_employee_via_api(
        authenticated_client,
        employee_code="EMP-CC-NORM",
        country="  united   KINGDOM ",
    )
    response = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=_salary_payload(currency="GBP"),
    )
    assert response.status_code == 201
    assert response.json()["currency"] == "GBP"


def test_api_correct_cannot_introduce_disallowed_currency(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _create_employee_via_api(
        authenticated_client,
        employee_code="EMP-CC-COR",
        country="United Kingdom",
    )
    created = authenticated_client.post(
        f"/api/v1/employees/{employee_id}/salaries",
        json=_salary_payload(currency="GBP"),
    )
    assert created.status_code == 201
    salary_id = created.json()["id"]

    response = authenticated_client.patch(
        f"/api/v1/employees/{employee_id}/salaries/{salary_id}",
        json={
            "amount": "2000.00",
            "currency": "USD",
            "pay_frequency": "ANNUAL",
            "effective_from": "2026-02-01",
            "reason": "Switch currency",
        },
    )
    assert response.status_code == 422
    assert "USD" in response.json()["detail"]
    stored = db_session.get(SalaryRecord, salary_id)
    assert stored is not None
    assert stored.currency == "GBP"
    assert str(stored.amount) == "1234.56"
    logs = list(
        db_session.scalars(
            select(SalaryAuditLog).where(SalaryAuditLog.salary_record_id == salary_id)
        ).all()
    )
    assert len(logs) == 1
    assert logs[0].action == AuditAction.CREATE.value


def test_api_unknown_employee_still_returns_404(
    authenticated_client: TestClient,
) -> None:
    response = authenticated_client.post(
        "/api/v1/employees/999999999/salaries",
        json=_salary_payload(),
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Employee not found"}
