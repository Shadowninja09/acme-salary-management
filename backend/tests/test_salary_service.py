from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Currency, Employee, EmploymentStatus, PayFrequency, SalaryRecord
from app.schemas.salary import SalaryCorrection, SalaryCreate
from app.services.salary import (
    DuplicateSalaryEffectiveDateError,
    EmployeeNotFoundError,
    InvalidSalaryAmountError,
    InvalidSalaryCorrectionReasonError,
    SalaryNotFoundError,
    correct_salary,
    create_salary,
    get_applicable_salary,
)


def _persist_employee(db_session: Session, **overrides: object) -> Employee:
    values = {
        "employee_code": "EMP-000001",
        "full_name": "Ada Lovelace",
        "country": "United Kingdom",
        "department": "Engineering",
        "job_title": "Analyst",
        "employment_status": EmploymentStatus.ACTIVE.value,
    }
    values.update(overrides)
    employee = Employee(**values)
    db_session.add(employee)
    db_session.flush()
    db_session.refresh(employee)
    return employee


def _create_payload(employee_id: int, **overrides: object) -> SalaryCreate:
    values = {
        "employee_id": employee_id,
        "amount": Decimal("1234.56"),
        "currency": Currency.INR,
        "pay_frequency": PayFrequency.MONTHLY,
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return SalaryCreate(**values)


def _correction_payload(**overrides: object) -> SalaryCorrection:
    values = {
        "amount": Decimal("2000.00"),
        "currency": Currency.USD,
        "pay_frequency": PayFrequency.ANNUAL,
        "effective_from": date(2026, 2, 1),
        "reason": "Corrected recorded amount",
    }
    values.update(overrides)
    return SalaryCorrection(**values)


def test_create_salary_succeeds(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    record = create_salary(db_session, _create_payload(employee.id, amount=Decimal("1.230")))

    assert record.id is not None
    assert record.employee_id == employee.id
    assert record.amount == Decimal("1.23")
    assert isinstance(record.amount, Decimal)
    assert record.currency == Currency.INR.value
    assert record.pay_frequency == PayFrequency.MONTHLY.value
    assert record.effective_from == date(2026, 1, 1)


def test_create_salary_rejects_missing_employee(db_session: Session) -> None:
    with pytest.raises(EmployeeNotFoundError):
        create_salary(db_session, _create_payload(999999999))


@pytest.mark.parametrize("amount", [Decimal("0"), Decimal("-1.00")])
def test_create_salary_rejects_non_positive_amount(
    db_session: Session, amount: Decimal
) -> None:
    employee = _persist_employee(db_session)
    with pytest.raises(InvalidSalaryAmountError):
        create_salary(db_session, _create_payload(employee.id, amount=amount))


@pytest.mark.parametrize(
    "amount",
    [Decimal("1.239"), 12.34, Decimal("NaN"), Decimal("Infinity")],
)
def test_create_salary_rejects_invalid_decimal_amount(
    db_session: Session, amount: object
) -> None:
    employee = _persist_employee(db_session)
    payload = _create_payload(employee.id)
    object.__setattr__(payload, "amount", amount)
    with pytest.raises(InvalidSalaryAmountError):
        create_salary(db_session, payload)


def test_create_salary_rejects_amount_exceeding_numeric_limit(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    with pytest.raises(InvalidSalaryAmountError):
        create_salary(
            db_session,
            _create_payload(employee.id, amount=Decimal("10000000000.00")),
        )


def test_create_salary_rejects_duplicate_effective_date(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    create_salary(db_session, _create_payload(employee.id))

    with pytest.raises(DuplicateSalaryEffectiveDateError):
        create_salary(
            db_session,
            _create_payload(employee.id, amount=Decimal("1500.00")),
        )


def test_create_salary_allows_same_date_for_different_employees(
    db_session: Session,
) -> None:
    first = _persist_employee(db_session, employee_code="EMP-000001")
    second = _persist_employee(db_session, employee_code="EMP-000002")
    effective_from = date(2026, 6, 1)

    first_record = create_salary(
        db_session, _create_payload(first.id, effective_from=effective_from)
    )
    second_record = create_salary(
        db_session, _create_payload(second.id, effective_from=effective_from)
    )

    assert first_record.id != second_record.id
    assert first_record.effective_from == second_record.effective_from


def test_correct_salary_replaces_same_row(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    other = create_salary(
        db_session,
        _create_payload(employee.id, effective_from=date(2026, 3, 1)),
    )

    updated = correct_salary(db_session, original.id, _correction_payload())

    assert updated.id == original.id
    assert updated.amount == Decimal("2000.00")
    assert updated.currency == Currency.USD.value
    assert updated.pay_frequency == PayFrequency.ANNUAL.value
    assert updated.effective_from == date(2026, 2, 1)
    unchanged = db_session.get(SalaryRecord, other.id)
    assert unchanged is not None
    assert unchanged.effective_from == date(2026, 3, 1)
    assert unchanged.amount == Decimal("1234.56")


@pytest.mark.parametrize("reason", ["", "   "])
def test_correct_salary_requires_non_empty_reason(
    db_session: Session, reason: str
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))

    with pytest.raises(InvalidSalaryCorrectionReasonError):
        correct_salary(db_session, original.id, _correction_payload(reason=reason))

    stored = db_session.get(SalaryRecord, original.id)
    assert stored is not None
    assert stored.amount == Decimal("1234.56")
    assert stored.effective_from == date(2026, 1, 1)


def test_correct_salary_rejects_unknown_id(db_session: Session) -> None:
    with pytest.raises(SalaryNotFoundError):
        correct_salary(db_session, 999999999, _correction_payload())


def test_correct_salary_rejects_duplicate_effective_date(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(
        db_session, _create_payload(employee.id, effective_from=date(2026, 1, 1))
    )
    create_salary(
        db_session, _create_payload(employee.id, effective_from=date(2026, 3, 1))
    )

    with pytest.raises(DuplicateSalaryEffectiveDateError):
        correct_salary(
            db_session,
            original.id,
            _correction_payload(effective_from=date(2026, 3, 1)),
        )


def test_invalid_correction_leaves_persisted_salary_unchanged(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    payload = _correction_payload()
    object.__setattr__(payload, "amount", Decimal("1.239"))

    with pytest.raises(InvalidSalaryAmountError):
        correct_salary(db_session, original.id, payload)

    stored = db_session.get(SalaryRecord, original.id)
    assert stored is not None
    assert stored.amount == Decimal("1234.56")
    assert stored.currency == Currency.INR.value
    assert stored.pay_frequency == PayFrequency.MONTHLY.value
    assert stored.effective_from == date(2026, 1, 1)


def test_get_applicable_salary_as_of_date(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    january = create_salary(
        db_session, _create_payload(employee.id, effective_from=date(2026, 1, 1))
    )
    create_salary(
        db_session,
        _create_payload(
            employee.id,
            amount=Decimal("3000.00"),
            effective_from=date(2026, 3, 1),
        ),
    )

    applicable = get_applicable_salary(db_session, employee.id, date(2026, 2, 15))
    on_effective_date = get_applicable_salary(
        db_session, employee.id, date(2026, 1, 1)
    )

    assert applicable is not None
    assert applicable.id == january.id
    assert on_effective_date is not None
    assert on_effective_date.id == january.id


def test_future_salary_is_not_applicable_before_effective_date(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    create_salary(
        db_session,
        _create_payload(
            employee.id,
            effective_from=date.today() + timedelta(days=365),
        ),
    )

    assert (
        get_applicable_salary(db_session, employee.id, date.today()) is None
    )


def test_no_applicable_salary_when_employee_has_no_records(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    assert get_applicable_salary(db_session, employee.id, date(2026, 1, 1)) is None


def test_get_applicable_salary_rejects_missing_employee(db_session: Session) -> None:
    with pytest.raises(EmployeeNotFoundError):
        get_applicable_salary(db_session, 999999999, date(2026, 1, 1))


def test_unrelated_integrity_error_is_not_mapped_to_duplicate(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    orig = MagicMock()
    orig.diag.constraint_name = "ck_salary_records_amount_positive"
    error = IntegrityError("INSERT", {}, orig)
    db_session.flush = MagicMock(side_effect=error)

    with pytest.raises(IntegrityError):
        create_salary(db_session, _create_payload(employee.id))
