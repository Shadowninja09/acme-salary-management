from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.salary import Currency, PayFrequency


class SalaryCreate(BaseModel):
    employee_id: int
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date


class SalaryCorrection(BaseModel):
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date
    reason: str


class SalaryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    amount: Decimal
    currency: Currency
    pay_frequency: PayFrequency
    effective_from: date
