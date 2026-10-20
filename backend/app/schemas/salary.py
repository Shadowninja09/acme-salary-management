from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel, ConfigDict, field_serializer, field_validator

from app.models.salary import Currency, PayFrequency


def parse_salary_amount(value: object) -> Decimal:
    if isinstance(value, bool) or isinstance(value, float):
        raise ValueError("amount must be a decimal string or integer")
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, str):
        try:
            return Decimal(value)
        except InvalidOperation as exc:
            raise ValueError("amount must be a valid decimal") from exc
    raise ValueError("amount must be a valid decimal")


class SalaryCreateRequest(BaseModel):
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_preserve_decimal_precision(cls, value: object) -> Decimal:
        return parse_salary_amount(value)


class SalaryCreate(BaseModel):
    employee_id: int
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_preserve_decimal_precision(cls, value: object) -> Decimal:
        return parse_salary_amount(value)


class SalaryCorrection(BaseModel):
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date
    reason: str

    @field_validator("amount", mode="before")
    @classmethod
    def amount_must_preserve_decimal_precision(cls, value: object) -> Decimal:
        return parse_salary_amount(value)


class SalaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return format(value, "f")


class SalaryAuditSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: str
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date


class SalaryCorrectionAuditRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    salary_record_id: int
    changed_at: datetime
    changed_by: str
    reason: str
    old_values: SalaryAuditSnapshot
    new_values: SalaryAuditSnapshot
