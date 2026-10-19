from datetime import date, datetime
from decimal import Decimal
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Currency(StrEnum):
    INR = "INR"
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"
    CAD = "CAD"
    AUD = "AUD"


class PayFrequency(StrEnum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class SalaryRecord(Base):
    __tablename__ = "salary_records"
    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "effective_from",
            name="uq_salary_records_employee_id_effective_from",
        ),
        CheckConstraint("amount > 0", name="ck_salary_records_amount_positive"),
        CheckConstraint(
            "currency IN ('INR', 'USD', 'GBP', 'EUR', 'CAD', 'AUD')",
            name="ck_salary_records_currency",
        ),
        CheckConstraint(
            "pay_frequency IN ('MONTHLY', 'ANNUAL')",
            name="ck_salary_records_pay_frequency",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    employee_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "employees.id",
            ondelete="RESTRICT",
            name="fk_salary_records_employee_id",
        ),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    pay_frequency: Mapped[str] = mapped_column(String(10), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
