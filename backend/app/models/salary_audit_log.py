from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AuditAction(StrEnum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"


class SalaryAuditLog(Base):
    __tablename__ = "salary_audit_logs"
    __table_args__ = (
        CheckConstraint(
            "action IN ('CREATE', 'UPDATE')",
            name="ck_salary_audit_logs_action",
        ),
        CheckConstraint(
            "(action = 'CREATE') OR (action = 'UPDATE' AND reason IS NOT NULL AND length(trim(reason)) > 0)",
            name="ck_salary_audit_logs_update_reason",
        ),
        Index("ix_salary_audit_logs_salary_record_id", "salary_record_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    salary_record_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey(
            "salary_records.id",
            ondelete="RESTRICT",
            name="fk_salary_audit_logs_salary_record_id",
        ),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False)
    old_values: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    new_values: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
