from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AuditAction,
    Currency,
    Employee,
    EmploymentStatus,
    PayFrequency,
    SalaryAuditLog,
    SalaryRecord,
)
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
    list_employee_salaries,
    list_employee_salary_corrections,
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
        "currency": Currency.GBP,
        "pay_frequency": PayFrequency.MONTHLY,
        "effective_from": date(2026, 1, 1),
    }
    values.update(overrides)
    return SalaryCreate(**values)


def _correction_payload(**overrides: object) -> SalaryCorrection:
    values = {
        "amount": Decimal("2000.00"),
        "currency": Currency.GBP,
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
    assert record.currency == Currency.GBP.value
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

    updated = correct_salary(
        db_session, employee.id, original.id, _correction_payload()
    )

    assert updated.id == original.id
    assert updated.amount == Decimal("2000.00")
    assert updated.currency == Currency.GBP.value
    assert updated.pay_frequency == PayFrequency.ANNUAL.value
    assert updated.effective_from == date(2026, 2, 1)
    unchanged = db_session.get(SalaryRecord, other.id)
    assert unchanged is not None
    assert unchanged.effective_from == date(2026, 3, 1)
    assert unchanged.amount == Decimal("1234.56")


def test_correct_salary_keeps_existing_effective_date(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    original_id = original.id

    updated = correct_salary(
        db_session,
        employee.id,
        original.id,
        _correction_payload(
            amount=Decimal("2000.00"),
            currency=Currency.GBP,
            pay_frequency=PayFrequency.MONTHLY,
            effective_from=date(2026, 1, 1),
        ),
    )
    logs = _audit_rows(db_session, original_id)
    updates = [log for log in logs if log.action == AuditAction.UPDATE.value]

    assert updated.id == original_id
    assert updated.amount == Decimal("2000.00")
    assert updated.currency == Currency.GBP.value
    assert updated.pay_frequency == PayFrequency.MONTHLY.value
    assert updated.effective_from == date(2026, 1, 1)
    assert db_session.scalar(select(func.count()).select_from(SalaryRecord)) == 1
    assert len(logs) == 2
    assert len(updates) == 1
    log = updates[0]
    assert log.old_values == {
        "amount": "1234.56",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": "2026-01-01",
    }
    assert log.new_values == {
        "amount": "2000.00",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": "2026-01-01",
    }
    assert log.reason == "Corrected recorded amount"
    assert log.changed_by == get_settings().hr_manager_identity


@pytest.mark.parametrize("reason", ["", "   "])
def test_correct_salary_requires_non_empty_reason(
    db_session: Session, reason: str
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))

    with pytest.raises(InvalidSalaryCorrectionReasonError):
        correct_salary(
            db_session,
            employee.id,
            original.id,
            _correction_payload(reason=reason),
        )

    stored = db_session.get(SalaryRecord, original.id)
    assert stored is not None
    assert stored.amount == Decimal("1234.56")
    assert stored.effective_from == date(2026, 1, 1)


def test_correct_salary_rejects_unknown_id(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    with pytest.raises(SalaryNotFoundError):
        correct_salary(
            db_session, employee.id, 999999999, _correction_payload()
        )


def test_correct_salary_rejects_unknown_employee(db_session: Session) -> None:
    with pytest.raises(EmployeeNotFoundError):
        correct_salary(db_session, 999999999, 1, _correction_payload())


def test_correct_salary_rejects_salary_owned_by_other_employee(
    db_session: Session,
) -> None:
    owner = _persist_employee(db_session, employee_code="EMP-000001")
    other = _persist_employee(db_session, employee_code="EMP-000002")
    record = create_salary(db_session, _create_payload(owner.id))

    with pytest.raises(SalaryNotFoundError):
        correct_salary(
            db_session, other.id, record.id, _correction_payload()
        )

    stored = db_session.get(SalaryRecord, record.id)
    assert stored is not None
    assert stored.amount == Decimal("1234.56")
    assert stored.effective_from == date(2026, 1, 1)


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

    nested = db_session.begin_nested()
    with pytest.raises(DuplicateSalaryEffectiveDateError):
        try:
            correct_salary(
                db_session,
                employee.id,
                original.id,
                _correction_payload(effective_from=date(2026, 3, 1)),
            )
        except DuplicateSalaryEffectiveDateError:
            nested.rollback()
            raise

    db_session.expire_all()
    stored = db_session.get(SalaryRecord, original.id)
    logs = _audit_rows(db_session, original.id)
    updates = [log for log in logs if log.action == AuditAction.UPDATE.value]

    assert stored is not None
    assert stored.id == original.id
    assert stored.amount == Decimal("1234.56")
    assert stored.currency == Currency.GBP.value
    assert stored.pay_frequency == PayFrequency.MONTHLY.value
    assert stored.effective_from == date(2026, 1, 1)
    assert len(updates) == 0
    assert all(log.action == AuditAction.CREATE.value for log in logs)


def test_invalid_correction_leaves_persisted_salary_unchanged(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    payload = _correction_payload()
    object.__setattr__(payload, "amount", Decimal("1.239"))

    with pytest.raises(InvalidSalaryAmountError):
        correct_salary(db_session, employee.id, original.id, payload)

    stored = db_session.get(SalaryRecord, original.id)
    assert stored is not None
    assert stored.amount == Decimal("1234.56")
    assert stored.currency == Currency.GBP.value
    assert stored.pay_frequency == PayFrequency.MONTHLY.value
    assert stored.effective_from == date(2026, 1, 1)


def test_list_employee_salaries_orders_by_effective_from_desc(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    older = create_salary(
        db_session, _create_payload(employee.id, effective_from=date(2026, 1, 1))
    )
    newer = create_salary(
        db_session,
        _create_payload(
            employee.id,
            amount=Decimal("2000.00"),
            effective_from=date(2026, 6, 1),
        ),
    )

    history = list_employee_salaries(db_session, employee.id)

    assert [record.id for record in history] == [newer.id, older.id]
    assert [record.effective_from for record in history] == [
        date(2026, 6, 1),
        date(2026, 1, 1),
    ]


def test_list_employee_salaries_empty_and_unknown(db_session: Session) -> None:
    employee = _persist_employee(db_session)

    assert list_employee_salaries(db_session, employee.id) == []
    with pytest.raises(EmployeeNotFoundError):
        list_employee_salaries(db_session, 999999999)


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


def _audit_rows(db_session: Session, salary_id: int) -> list[SalaryAuditLog]:
    return list(
        db_session.scalars(
            select(SalaryAuditLog)
            .where(SalaryAuditLog.salary_record_id == salary_id)
            .order_by(SalaryAuditLog.id.asc())
        ).all()
    )


def test_create_salary_writes_create_audit_entry(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    record = create_salary(db_session, _create_payload(employee.id))
    logs = _audit_rows(db_session, record.id)

    assert len(logs) == 1
    log = logs[0]
    assert log.action == AuditAction.CREATE.value
    assert log.old_values is None
    assert log.new_values == {
        "amount": "1234.56",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": "2026-01-01",
    }
    assert log.reason is None
    assert log.changed_by == get_settings().hr_manager_identity
    assert log.salary_record_id == record.id


def test_correct_salary_writes_update_audit_entry(db_session: Session) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    original_id = original.id
    updated = correct_salary(
        db_session, employee.id, original.id, _correction_payload()
    )
    logs = _audit_rows(db_session, original_id)
    updates = [log for log in logs if log.action == AuditAction.UPDATE.value]

    assert updated.id == original_id
    assert db_session.scalar(select(func.count()).select_from(SalaryRecord)) == 1
    assert len(logs) == 2
    assert len(updates) == 1
    log = updates[0]
    assert log.old_values == {
        "amount": "1234.56",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": "2026-01-01",
    }
    assert log.new_values == {
        "amount": "2000.00",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.ANNUAL.value,
        "effective_from": "2026-02-01",
    }
    assert log.reason == "Corrected recorded amount"
    assert log.changed_by == get_settings().hr_manager_identity


def test_audit_flush_failure_does_not_leave_committed_salary(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    real_flush = db_session.flush
    flush_calls = {"count": 0}

    def flush_then_fail_audit(*args: object, **kwargs: object) -> None:
        flush_calls["count"] += 1
        if flush_calls["count"] == 1:
            real_flush(*args, **kwargs)
            return
        raise IntegrityError("INSERT", {}, Exception("audit flush failed"))

    db_session.flush = flush_then_fail_audit  # type: ignore[method-assign]
    try:
        with pytest.raises(IntegrityError):
            create_salary(db_session, _create_payload(employee.id))
    finally:
        db_session.flush = real_flush  # type: ignore[method-assign]

    db_session.rollback()

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(SalaryRecord)
            .where(SalaryRecord.employee_id == employee.id)
        )
        == 0
    )
    assert db_session.scalar(select(func.count()).select_from(SalaryAuditLog)) == 0


def test_list_employee_salary_corrections_empty_when_only_create_audit(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    create_salary(db_session, _create_payload(employee.id))

    assert list_employee_salary_corrections(db_session, employee.id) == []


def test_list_employee_salary_corrections_returns_update_audit(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    correct_salary(
        db_session, employee.id, original.id, _correction_payload()
    )

    corrections = list_employee_salary_corrections(db_session, employee.id)

    assert len(corrections) == 1
    log = corrections[0]
    assert log.salary_record_id == original.id
    assert log.action == AuditAction.UPDATE.value
    assert log.old_values == {
        "amount": "1234.56",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.MONTHLY.value,
        "effective_from": "2026-01-01",
    }
    assert log.new_values == {
        "amount": "2000.00",
        "currency": Currency.GBP.value,
        "pay_frequency": PayFrequency.ANNUAL.value,
        "effective_from": "2026-02-01",
    }
    assert log.reason == "Corrected recorded amount"
    assert log.changed_by == get_settings().hr_manager_identity
    assert log.changed_at.tzinfo is not None


def test_list_employee_salary_corrections_orders_newest_first(
    db_session: Session,
) -> None:
    employee = _persist_employee(db_session)
    original = create_salary(db_session, _create_payload(employee.id))
    first = correct_salary(
        db_session, employee.id, original.id, _correction_payload()
    )
    second = correct_salary(
        db_session,
        employee.id,
        first.id,
        _correction_payload(
            amount=Decimal("3000.00"),
            effective_from=date(2026, 2, 1),
        ),
    )

    corrections = list_employee_salary_corrections(db_session, employee.id)

    assert [log.id for log in corrections] == sorted(
        (log.id for log in corrections), reverse=True
    )
    assert corrections[0].new_values["amount"] == "3000.00"
    assert corrections[1].new_values["amount"] == "2000.00"
    assert corrections[0].salary_record_id == second.id
    assert corrections[1].salary_record_id == first.id
    assert corrections[0].changed_at >= corrections[1].changed_at


def test_list_employee_salary_corrections_rejects_unknown_employee(
    db_session: Session,
) -> None:
    with pytest.raises(EmployeeNotFoundError):
        list_employee_salary_corrections(db_session, 999999999)


def test_list_employee_salary_corrections_excludes_other_employee_audits(
    db_session: Session,
) -> None:
    owner = _persist_employee(db_session, employee_code="EMP-000001")
    other = _persist_employee(db_session, employee_code="EMP-000002")
    owner_salary = create_salary(db_session, _create_payload(owner.id))
    other_salary = create_salary(db_session, _create_payload(other.id))
    correct_salary(db_session, owner.id, owner_salary.id, _correction_payload())
    correct_salary(
        db_session,
        other.id,
        other_salary.id,
        _correction_payload(reason="Other employee correction"),
    )

    corrections = list_employee_salary_corrections(db_session, owner.id)

    assert len(corrections) == 1
    assert corrections[0].salary_record_id == owner_salary.id
    assert corrections[0].reason == "Corrected recorded amount"
