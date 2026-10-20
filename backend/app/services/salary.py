from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AuditAction, SalaryAuditLog
from app.models.employee import Employee
from app.models.salary import Currency, PayFrequency, SalaryRecord
from app.schemas.salary import SalaryCorrection, SalaryCreate

SALARY_EFFECTIVE_DATE_UNIQUE_CONSTRAINT = (
    "uq_salary_records_employee_id_effective_from"
)
_TWO_PLACES = Decimal("0.01")
_MAX_AMOUNT = Decimal("9999999999.99")


class EmployeeNotFoundError(Exception):
    pass


class SalaryNotFoundError(Exception):
    pass


class InvalidSalaryAmountError(Exception):
    pass


class InvalidSalaryCurrencyError(Exception):
    pass


class InvalidPayFrequencyError(Exception):
    pass


class DuplicateSalaryEffectiveDateError(Exception):
    pass


class InvalidSalaryCorrectionReasonError(Exception):
    pass


def _is_duplicate_effective_date_violation(exc: IntegrityError) -> bool:
    orig = exc.orig
    if orig is None:
        return False
    diag = getattr(orig, "diag", None)
    constraint_name = getattr(diag, "constraint_name", None) if diag is not None else None
    return constraint_name == SALARY_EFFECTIVE_DATE_UNIQUE_CONSTRAINT


def _normalize_amount(amount: object) -> Decimal:
    if type(amount) is float or not isinstance(amount, Decimal):
        raise InvalidSalaryAmountError
    if not amount.is_finite():
        raise InvalidSalaryAmountError
    if amount <= 0:
        raise InvalidSalaryAmountError
    try:
        if amount > _MAX_AMOUNT:
            raise InvalidSalaryAmountError
        quantized = amount.quantize(_TWO_PLACES)
    except InvalidOperation as exc:
        raise InvalidSalaryAmountError from exc
    if quantized != amount:
        raise InvalidSalaryAmountError
    return quantized


def _validate_currency(currency: Currency | str) -> str:
    value = currency.value if isinstance(currency, Currency) else currency
    try:
        return Currency(value).value
    except ValueError as exc:
        raise InvalidSalaryCurrencyError from exc


def _validate_pay_frequency(pay_frequency: PayFrequency | str) -> str:
    value = pay_frequency.value if isinstance(pay_frequency, PayFrequency) else pay_frequency
    try:
        return PayFrequency(value).value
    except ValueError as exc:
        raise InvalidPayFrequencyError from exc


def _require_employee(db: Session, employee_id: int) -> Employee:
    employee = db.get(Employee, employee_id)
    if employee is None:
        raise EmployeeNotFoundError
    return employee


def _validate_correction_reason(reason: str) -> str:
    if not reason.strip():
        raise InvalidSalaryCorrectionReasonError
    return reason


def _salary_snapshot(record: SalaryRecord) -> dict[str, Any]:
    return {
        "amount": format(record.amount, "f"),
        "currency": record.currency,
        "pay_frequency": record.pay_frequency,
        "effective_from": record.effective_from.isoformat(),
    }


def _write_salary_audit(
    db: Session,
    record: SalaryRecord,
    *,
    action: AuditAction,
    old_values: dict[str, Any] | None,
    reason: str | None,
) -> None:
    db.add(
        SalaryAuditLog(
            salary_record_id=record.id,
            action=action.value,
            old_values=old_values,
            new_values=_salary_snapshot(record),
            reason=reason,
            changed_by=get_settings().hr_manager_identity,
        )
    )
    db.flush()


def create_salary(db: Session, data: SalaryCreate) -> SalaryRecord:
    _require_employee(db, data.employee_id)
    record = SalaryRecord(
        employee_id=data.employee_id,
        amount=_normalize_amount(data.amount),
        currency=_validate_currency(data.currency),
        pay_frequency=_validate_pay_frequency(data.pay_frequency),
        effective_from=data.effective_from,
    )
    db.add(record)
    try:
        db.flush()
    except IntegrityError as exc:
        if _is_duplicate_effective_date_violation(exc):
            raise DuplicateSalaryEffectiveDateError from exc
        raise
    db.refresh(record)
    _write_salary_audit(
        db,
        record,
        action=AuditAction.CREATE,
        old_values=None,
        reason=None,
    )
    return record


def correct_salary(
    db: Session, employee_id: int, salary_id: int, data: SalaryCorrection
) -> SalaryRecord:
    _require_employee(db, employee_id)
    reason = _validate_correction_reason(data.reason)
    amount = _normalize_amount(data.amount)
    currency = _validate_currency(data.currency)
    pay_frequency = _validate_pay_frequency(data.pay_frequency)
    record = db.get(SalaryRecord, salary_id)
    if record is None or record.employee_id != employee_id:
        raise SalaryNotFoundError
    old_values = _salary_snapshot(record)
    record.amount = amount
    record.currency = currency
    record.pay_frequency = pay_frequency
    record.effective_from = data.effective_from
    try:
        db.flush()
    except IntegrityError as exc:
        if _is_duplicate_effective_date_violation(exc):
            raise DuplicateSalaryEffectiveDateError from exc
        raise
    db.refresh(record)
    _write_salary_audit(
        db,
        record,
        action=AuditAction.UPDATE,
        old_values=old_values,
        reason=reason,
    )
    return record


def list_employee_salary_corrections(
    db: Session, employee_id: int
) -> list[SalaryAuditLog]:
    _require_employee(db, employee_id)
    return list(
        db.scalars(
            select(SalaryAuditLog)
            .join(SalaryRecord, SalaryAuditLog.salary_record_id == SalaryRecord.id)
            .where(
                SalaryRecord.employee_id == employee_id,
                SalaryAuditLog.action == AuditAction.UPDATE.value,
            )
            .order_by(SalaryAuditLog.changed_at.desc(), SalaryAuditLog.id.desc())
        ).all()
    )


def list_employee_salaries(db: Session, employee_id: int) -> list[SalaryRecord]:
    _require_employee(db, employee_id)
    return list(
        db.scalars(
            select(SalaryRecord)
            .where(SalaryRecord.employee_id == employee_id)
            .order_by(SalaryRecord.effective_from.desc(), SalaryRecord.id.desc())
        ).all()
    )


def get_applicable_salary(
    db: Session, employee_id: int, as_of: date
) -> SalaryRecord | None:
    _require_employee(db, employee_id)
    return db.scalars(
        select(SalaryRecord)
        .where(
            SalaryRecord.employee_id == employee_id,
            SalaryRecord.effective_from <= as_of,
        )
        .order_by(SalaryRecord.effective_from.desc())
        .limit(1)
    ).first()
