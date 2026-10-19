"""create salary_records table

Revision ID: 0002_create_salary_records
Revises: 0001_create_employees
Create Date: 2026-10-19

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_create_salary_records"
down_revision: Union[str, Sequence[str], None] = "0001_create_employees"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "salary_records",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("employee_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("pay_frequency", sa.String(length=10), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["employees.id"],
            name="fk_salary_records_employee_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "employee_id",
            "effective_from",
            name="uq_salary_records_employee_id_effective_from",
        ),
        sa.CheckConstraint("amount > 0", name="ck_salary_records_amount_positive"),
        sa.CheckConstraint(
            "currency IN ('INR', 'USD', 'GBP', 'EUR', 'CAD', 'AUD')",
            name="ck_salary_records_currency",
        ),
        sa.CheckConstraint(
            "pay_frequency IN ('MONTHLY', 'ANNUAL')",
            name="ck_salary_records_pay_frequency",
        ),
    )


def downgrade() -> None:
    op.drop_table("salary_records")
