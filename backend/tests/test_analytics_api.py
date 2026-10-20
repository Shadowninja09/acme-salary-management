from datetime import date
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import NOT_AUTHENTICATED_DETAIL
from app.models.employee import EmploymentStatus
from app.models.salary import Currency, PayFrequency
from app.schemas.employee import EmployeeCreate
from app.schemas.salary import SalaryCreate
from app.services.employee import create_employee
from app.services.salary import create_salary

ANALYTICS_PATH = "/api/v1/analytics/compensation"
REPORTING_DATE = "2026-06-15"


def _employee(
    db_session: Session,
    employee_code: str,
    *,
    country: str = "India",
    department: str = "Engineering",
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE,
) -> int:
    employee = create_employee(
        db_session,
        EmployeeCreate(
            employee_code=employee_code,
            full_name=f"Name {employee_code}",
            country=country,
            department=department,
            job_title="Engineer",
            employment_status=employment_status,
        ),
    )
    return employee.id


def _salary(
    db_session: Session,
    employee_id: int,
    *,
    amount: str,
    currency: Currency = Currency.INR,
    pay_frequency: PayFrequency = PayFrequency.ANNUAL,
    effective_from: date = date(2026, 1, 1),
) -> None:
    create_salary(
        db_session,
        SalaryCreate(
            employee_id=employee_id,
            amount=Decimal(amount),
            currency=currency,
            pay_frequency=pay_frequency,
            effective_from=effective_from,
        ),
    )


def _get(client: TestClient, reporting_date: str = REPORTING_DATE):
    return client.get(ANALYTICS_PATH, params={"date": reporting_date})


def test_compensation_analytics_is_documented_in_openapi(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/analytics/compensation" in paths
    operation = paths["/api/v1/analytics/compensation"]["get"]
    assert "date" in {param["name"] for param in operation["parameters"]}


def test_authenticated_request_succeeds(authenticated_client: TestClient) -> None:
    response = _get(authenticated_client)
    assert response.status_code == 200
    body = response.json()
    assert body["reporting_date"] == REPORTING_DATE
    assert body["active_employee_count"] == 0
    assert body["active_employees_with_salary"] == 0
    assert body["active_employees_without_salary"] == 0
    assert body["salary_summary"] == []
    assert body["by_department"] == []
    assert body["by_country"] == []


def test_unauthenticated_request_is_rejected(api_client: TestClient) -> None:
    response = _get(api_client)
    assert response.status_code == 401
    assert response.json() == {"detail": NOT_AUTHENTICATED_DETAIL}


@pytest.mark.parametrize(
    "params",
    [{}, {"date": "not-a-date"}, {"date": "2026-13-40"}],
)
def test_required_reporting_date_validation(
    authenticated_client: TestClient,
    params: dict,
) -> None:
    response = authenticated_client.get(ANALYTICS_PATH, params=params)
    assert response.status_code == 422


def test_empty_dataset_returns_valid_empty_summaries(
    authenticated_client: TestClient,
) -> None:
    response = _get(authenticated_client)
    assert response.status_code == 200
    body = response.json()
    assert body["salary_summary"] == []
    assert body["by_department"] == []
    assert body["by_country"] == []
    assert (
        body["active_employee_count"]
        == body["active_employees_with_salary"]
        + body["active_employees_without_salary"]
    )


def test_salary_effective_on_reporting_date_is_included(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _employee(db_session, "AN-ON-DATE")
    _salary(
        db_session,
        employee_id,
        amount="1000.00",
        effective_from=date(2026, 6, 15),
    )

    body = _get(authenticated_client).json()
    assert body["active_employees_with_salary"] == 1
    assert body["salary_summary"][0]["minimum_salary"] == "1000.00"


def test_future_effective_salary_is_excluded(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _employee(db_session, "AN-FUTURE")
    _salary(
        db_session,
        employee_id,
        amount="9999.00",
        effective_from=date(2026, 6, 16),
    )

    body = _get(authenticated_client).json()
    assert body["active_employee_count"] == 1
    assert body["active_employees_with_salary"] == 0
    assert body["active_employees_without_salary"] == 1
    assert body["salary_summary"] == []


def test_latest_applicable_salary_is_selected_from_history(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    employee_id = _employee(db_session, "AN-HISTORY")
    _salary(
        db_session,
        employee_id,
        amount="1000.00",
        effective_from=date(2026, 1, 1),
    )
    _salary(
        db_session,
        employee_id,
        amount="2500.00",
        effective_from=date(2026, 4, 1),
    )
    _salary(
        db_session,
        employee_id,
        amount="4000.00",
        effective_from=date(2026, 12, 1),
    )

    body = _get(authenticated_client).json()
    assert body["active_employees_with_salary"] == 1
    group = body["salary_summary"][0]
    assert group["employee_count"] == 1
    assert group["average_salary"] == "2500.00"
    assert group["minimum_salary"] == "2500.00"
    assert group["maximum_salary"] == "2500.00"


def test_active_employee_without_salary_is_counted(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    _employee(db_session, "AN-NOSAL")
    paid_id = _employee(db_session, "AN-PAID")
    _salary(db_session, paid_id, amount="100.00")

    body = _get(authenticated_client).json()
    assert body["active_employee_count"] == 2
    assert body["active_employees_with_salary"] == 1
    assert body["active_employees_without_salary"] == 1
    assert body["salary_summary"][0]["employee_count"] == 1


def test_inactive_employees_are_excluded(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    inactive_id = _employee(
        db_session,
        "AN-INACTIVE",
        employment_status=EmploymentStatus.INACTIVE,
    )
    _salary(db_session, inactive_id, amount="8000.00")
    active_id = _employee(db_session, "AN-ACTIVE")
    _salary(db_session, active_id, amount="200.00")

    body = _get(authenticated_client).json()
    assert body["active_employee_count"] == 1
    assert body["active_employees_with_salary"] == 1
    assert body["salary_summary"][0]["minimum_salary"] == "200.00"
    assert body["by_department"][0]["employee_count"] == 1
    assert body["by_country"][0]["employee_count"] == 1


def test_average_minimum_maximum_and_counts(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    first = _employee(db_session, "AN-AVG-1")
    second = _employee(db_session, "AN-AVG-2")
    third = _employee(db_session, "AN-AVG-3")
    _salary(db_session, first, amount="100.00")
    _salary(db_session, second, amount="200.00")
    _salary(db_session, third, amount="300.00")

    body = _get(authenticated_client).json()
    group = body["salary_summary"][0]
    assert group["currency"] == "INR"
    assert group["pay_frequency"] == "ANNUAL"
    assert group["employee_count"] == 3
    assert group["average_salary"] == "200.00"
    assert group["minimum_salary"] == "100.00"
    assert group["maximum_salary"] == "300.00"
    assert (
        body["active_employee_count"]
        == body["active_employees_with_salary"]
        + body["active_employees_without_salary"]
    )


def test_different_currencies_are_never_combined(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    inr_id = _employee(db_session, "AN-INR")
    usd_id = _employee(db_session, "AN-USD")
    _salary(db_session, inr_id, amount="100.00", currency=Currency.INR)
    _salary(db_session, usd_id, amount="200.00", currency=Currency.USD)

    body = _get(authenticated_client).json()
    groups = {(item["currency"], item["pay_frequency"]): item for item in body["salary_summary"]}
    assert set(groups) == {("INR", "ANNUAL"), ("USD", "ANNUAL")}
    assert groups[("INR", "ANNUAL")]["average_salary"] == "100.00"
    assert groups[("USD", "ANNUAL")]["average_salary"] == "200.00"
    assert groups[("INR", "ANNUAL")]["employee_count"] == 1
    assert groups[("USD", "ANNUAL")]["employee_count"] == 1


def test_monthly_and_annual_salaries_are_never_combined(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    monthly_id = _employee(db_session, "AN-MON")
    annual_id = _employee(db_session, "AN-ANN")
    _salary(
        db_session,
        monthly_id,
        amount="100.00",
        pay_frequency=PayFrequency.MONTHLY,
    )
    _salary(
        db_session,
        annual_id,
        amount="1200.00",
        pay_frequency=PayFrequency.ANNUAL,
    )

    body = _get(authenticated_client).json()
    groups = {(item["currency"], item["pay_frequency"]): item for item in body["salary_summary"]}
    assert set(groups) == {("INR", "MONTHLY"), ("INR", "ANNUAL")}
    assert groups[("INR", "MONTHLY")]["average_salary"] == "100.00"
    assert groups[("INR", "ANNUAL")]["average_salary"] == "1200.00"


def test_department_and_country_breakdowns(
    authenticated_client: TestClient,
    db_session: Session,
) -> None:
    eng_in = _employee(
        db_session, "AN-ENG-IN", country="India", department="Engineering"
    )
    sales_in = _employee(
        db_session, "AN-SALES-IN", country="India", department="Sales"
    )
    eng_uk = _employee(
        db_session,
        "AN-ENG-UK",
        country="United Kingdom",
        department="Engineering",
    )
    _salary(db_session, eng_in, amount="100.00")
    _salary(db_session, sales_in, amount="300.00")
    _salary(db_session, eng_uk, amount="500.00")

    body = _get(authenticated_client).json()
    departments = {
        (item["department"], item["currency"], item["pay_frequency"]): item
        for item in body["by_department"]
    }
    countries = {
        (item["country"], item["currency"], item["pay_frequency"]): item
        for item in body["by_country"]
    }

    assert departments[("Engineering", "INR", "ANNUAL")]["employee_count"] == 2
    assert departments[("Engineering", "INR", "ANNUAL")]["average_salary"] == "300.00"
    assert departments[("Engineering", "INR", "ANNUAL")]["minimum_salary"] == "100.00"
    assert departments[("Engineering", "INR", "ANNUAL")]["maximum_salary"] == "500.00"
    assert departments[("Sales", "INR", "ANNUAL")]["employee_count"] == 1
    assert departments[("Sales", "INR", "ANNUAL")]["average_salary"] == "300.00"

    assert countries[("India", "INR", "ANNUAL")]["employee_count"] == 2
    assert countries[("India", "INR", "ANNUAL")]["average_salary"] == "200.00"
    assert countries[("United Kingdom", "INR", "ANNUAL")]["employee_count"] == 1
    assert countries[("United Kingdom", "INR", "ANNUAL")]["average_salary"] == "500.00"
