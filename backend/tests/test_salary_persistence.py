from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Currency, Employee, EmploymentStatus, PayFrequency, SalaryRecord


def _employee(**overrides: object) -> Employee:
    values = {
        "employee_code": "EMP-000001",
        "full_name": "Ada Lovelace",
        "country": "United Kingdom",
        "department": "Engineering",
        "job_title": "Analyst",
        "employment_status": EmploymentStatus.ACTIVE.value,
    }
    values.update(overrides)
    return Employee(**values)


def _persist_employee(db_session: Session, **overrides: object) -> Employee:
    employee = _employee(**overrides)
    db_session.add(employee)
    db_session.flush()
    db_session.refresh(employee)
    return employee


def _salary(employee_id: int, **overrides: object) -> SalaryRecord:
    values = {
        "employee_id": employee_id,
        "amount": Decimal("1234.56"),
        "currency": Currency.INR.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return SalaryRecord(**values)


def test_insert_and_read_salary_record(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    salary = _salary(employee.id)
    db_session.add(salary)
    db_session.flush()
    db_session.refresh(salary)

    stored = db_session.get(SalaryRecord, salary.id)

    assert stored is not None
    assert stored.employee_id == employee.id
    assert stored.amount == Decimal("1234.56")
    assert isinstance(stored.amount, Decimal)
    assert stored.currency == Currency.INR.value
    assert stored.pay_frequency == PayFrequency.MONTHLY.value
    assert stored.effective_from == date(2026, 1, 1)


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1.00")])
def test_non_positive_amount_is_rejected(
    db_session: Session, amount: Decimal
) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id, amount=amount))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_currency_is_rejected(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id, currency="JPY"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_invalid_pay_frequency_is_rejected(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id, pay_frequency="WEEKLY"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_duplicate_employee_and_effective_from_is_rejected(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id))
    db_session.flush()

    db_session.add(
        _salary(employee.id, amount=Decimal("2000.00"), currency=Currency.USD.value)
    )
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_same_effective_from_allowed_for_different_employees(
    db_session: Session,
) -> None:
    first = _persist_employee(db_session, employee_code="EMP-000001")
    second = _persist_employee(db_session, employee_code="EMP-000002")
    effective_from = date(2026, 6, 1)

    db_session.add(_salary(first.id, effective_from=effective_from))
    db_session.add(_salary(second.id, effective_from=effective_from))
    db_session.flush()

    stored = list(
        db_session.scalars(
            select(SalaryRecord).where(SalaryRecord.effective_from == effective_from)
        ).all()
    )
    assert len(stored) == 2
    assert {row.employee_id for row in stored} == {first.id, second.id}


def test_same_employee_can_have_multiple_effective_dates(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id, effective_from=date(2026, 1, 1)))
    db_session.add(
        _salary(
            employee.id,
            effective_from=date.today() + timedelta(days=365),
            amount=Decimal("1500.00"),
        )
    )
    db_session.flush()

    records = list(
        db_session.scalars(
            select(SalaryRecord).where(SalaryRecord.employee_id == employee.id)
        ).all()
    )
    assert len(records) == 2


def test_salary_requires_existing_employee(db_session: Session) -> None:
    db_session.add(_salary(employee_id=999999999))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_employee_with_salary_history_cannot_be_deleted(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    db_session.add(_salary(employee.id))
    db_session.flush()

    db_session.delete(employee)
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_salary_timestamps_are_initialized_by_the_database(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    salary = _salary(employee.id)
    db_session.add(salary)
    db_session.flush()
    db_session.refresh(salary)

    assert salary.created_at is not None
    assert salary.updated_at is not None
    assert salary.created_at.tzinfo is not None
    assert salary.updated_at.tzinfo is not None
    assert salary.created_at == salary.updated_at
