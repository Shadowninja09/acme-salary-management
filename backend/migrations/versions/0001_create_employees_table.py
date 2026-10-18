"""create employees table

Revision ID: 0001_create_employees
Revises:
Create Date: 2026-10-18

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_create_employees"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "employees",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("employee_code", sa.String(length=20), nullable=False),
        sa.Column("full_name", sa.String(length=150), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("job_title", sa.String(length=150), nullable=False),
        sa.Column("employment_status", sa.String(length=10), nullable=False),
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
        sa.UniqueConstraint("employee_code", name="uq_employees_employee_code"),
        sa.CheckConstraint(
            "employment_status IN ('ACTIVE', 'INACTIVE')",
            name="ck_employees_employment_status",
        ),
    )


def downgrade() -> None:
    op.drop_table("employees")
