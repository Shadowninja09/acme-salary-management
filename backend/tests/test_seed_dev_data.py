from datetime import date

import pytest

from app.models.employee import EmploymentStatus
from app.models.salary import PayFrequency
from app.services.country_currency import permitted_currencies_for_country
from scripts.seed_dev_data import (
    COUNTRIES,
    SeedTargetError,
    assert_safe_seed_target,
    build_employee,
    build_salaries,
    employee_code_for,
)

DEV_URL = "postgresql+psycopg://user:secret@localhost:5432/acme_salary"
TEST_URL = "postgresql+psycopg://user:secret@localhost:5432/acme_test"


def test_accepts_acme_salary_when_not_the_test_database() -> None:
    assert_safe_seed_target(DEV_URL, TEST_URL)


def test_rejects_acme_test_database_name() -> None:
    with pytest.raises(SeedTargetError, match="test database"):
        assert_safe_seed_target(TEST_URL, None)


def test_rejects_url_matching_test_database_url() -> None:
    with pytest.raises(SeedTargetError, match="TEST_DATABASE_URL"):
        assert_safe_seed_target(DEV_URL, DEV_URL)


def test_rejects_unexpected_database_name() -> None:
    other = "postgresql+psycopg://user:secret@localhost:5432/postgres"
    with pytest.raises(SeedTargetError, match="unexpected database"):
        assert_safe_seed_target(other, TEST_URL)


def test_guard_error_does_not_include_credentials() -> None:
    with pytest.raises(SeedTargetError) as exc_info:
        assert_safe_seed_target(TEST_URL, None)
    assert "secret" not in str(exc_info.value)
    assert "user:" not in str(exc_info.value)


def test_rejects_same_host_port_database_with_different_credentials() -> None:
    development_url = (
        "postgresql+psycopg://dev_user:dev_secret@localhost:5432/acme_salary"
    )
    test_url = (
        "postgresql+psycopg://test_user:test_secret@localhost:5432/acme_salary"
    )
    with pytest.raises(SeedTargetError) as exc_info:
        assert_safe_seed_target(development_url, test_url)
    message = str(exc_info.value)
    assert "dev_user" not in message
    assert "dev_secret" not in message
    assert "test_user" not in message
    assert "test_secret" not in message


def test_employee_code_for_is_deterministic_and_zero_padded() -> None:
    assert employee_code_for(1) == "EMP-000001"
    assert employee_code_for(10) == "EMP-000010"
    assert employee_code_for(1) == employee_code_for(1)
    assert employee_code_for(1) != employee_code_for(2)


def test_build_employee_is_deterministic_for_the_same_index() -> None:
    first = build_employee(7)
    second = build_employee(7)

    assert first == second
    assert first.employee_code == employee_code_for(7)
    assert first.full_name == "Seed Employee 000007"
    assert first.country == COUNTRIES[7 % len(COUNTRIES)]
    assert first.employment_status in {EmploymentStatus.ACTIVE, EmploymentStatus.INACTIVE}


def test_build_employee_differs_for_different_indexes() -> None:
    first = build_employee(1)
    second = build_employee(2)

    assert first.employee_code != second.employee_code
    assert first != second


def test_build_salaries_count_follows_index_remainder() -> None:
    country = build_employee(1).country
    by_remainder = {
        10: 0,
        1: 1,
        4: 2,
        7: 3,
    }
    for index, expected_count in by_remainder.items():
        payloads = build_salaries(employee_id=1, index=index, country=country)
        assert len(payloads) == expected_count


def test_build_salaries_is_deterministic_and_uses_country_policy() -> None:
    employee = build_employee(4)
    permitted = permitted_currencies_for_country(employee.country)
    assert permitted is not None

    first = build_salaries(employee_id=99, index=4, country=employee.country)
    second = build_salaries(employee_id=99, index=4, country=employee.country)

    assert first == second
    assert len(first) == 2
    seen_dates: set[date] = set()
    for payload in first:
        assert payload.employee_id == 99
        assert payload.currency in permitted
        assert payload.pay_frequency in {PayFrequency.MONTHLY, PayFrequency.ANNUAL}
        assert payload.amount > 0
        assert payload.effective_from not in seen_dates
        seen_dates.add(payload.effective_from)


def test_build_salaries_marks_final_record_future_for_remainder_eight_or_nine() -> None:
    employee = build_employee(8)
    payloads = build_salaries(employee_id=1, index=8, country=employee.country)

    assert len(payloads) == 3
    assert payloads[-1].effective_from >= date(2027, 4, 15)
    assert all(payload.effective_from < date(2027, 4, 15) for payload in payloads[:-1])


def test_build_salaries_rejects_country_without_currency_policy() -> None:
    with pytest.raises(ValueError, match="No salary currency policy"):
        build_salaries(employee_id=1, index=1, country="France")
